"""
Import local authority_emissions
"""
import pandas as pd
from caps.models import Council, DataPoint, DataType
from django.core.management.base import BaseCommand
from django.db.models import Count
from mysoc_dataset import get_dataset_url
from functools import lru_cache, wraps


def cache_and_wrap(func):
    cached_function = lru_cache(func)

    @wraps(func)
    def inner(*args, **kwargs):
        return cached_function(*args, **kwargs)

    return inner


@cache_and_wrap
def get_emissions_url() -> str:
    emissions_df = get_dataset_url(
        repo_name="la-emissions-data",
        package_name="uk_local_authority_emissions_data",
        version_name="1",
        file_name="local_authority_emissions.csv",
        done_survey=True,
    )
    return emissions_df


@cache_and_wrap
def get_emissions_data() -> pd.DataFrame:
    return pd.read_csv(get_emissions_url())


def create_data_types():
    """
    Create the DataType objects associated with the emissions data
    """

    df = get_emissions_data()
    source_url = get_emissions_url()

    emission_types = [x for x in df.columns if ":" in x]

    for etype in emission_types:
        name, unit = etype.split(":")
        data_type, created = DataType.objects.get_or_create(
            name=name, source_url=source_url, name_in_source=name, unit=unit
        )


def check_completeness():
    """
    Check all councils have emissions data associated with them
    """

    authority_types_without_expected_data = []
    councils_with_no_data = (
        Council.objects.exclude(
            authority_type__in=authority_types_without_expected_data
        )
        .annotate(num_datapoints=Count("datapoint"))
        .filter(num_datapoints__lt=1)
    )
    for council in councils_with_no_data:
        print(f"No data for {council.name} {council.gss_code}")


def import_emissions_data() -> None:
    """
    Load information from BEIS data into DataPoints in the database
    """

    councils = {x.authority_code: x for x in Council.objects.all()}
    data_types = {
        x.name: x for x in DataType.objects.filter(source_url=get_emissions_url())
    }

    df = (
        get_emissions_data()
        .drop(columns=["official-name"])
        .melt(
            ["Year", "local-authority-code"],
            var_name="name_and_unit",
            value_name="value",
        )
    )

    # create column with the council objects and remove any rows without a council in the database
    df["council_obj"] = df["local-authority-code"].apply(
        lambda x: councils.get(x, None)
    )
    df = df[~df["council_obj"].isna()]

    # get the DataType object
    df["data_type_obj"] = df["name_and_unit"].apply(
        lambda x: data_types[x.split(":")[0]]
    )

    # get series with data points
    def create_data_point(row: pd.Series) -> DataPoint:
        return DataPoint(
            year=row["Year"],
            value=row["value"],
            council=row["council_obj"],
            data_type=row["data_type_obj"],
        )

    data_points = df.apply(create_data_point, axis="columns")

    # delete and create data points in bulk
    print("Deleting and creating DataPoints")
    DataPoint.objects.filter(data_type__source_url=get_emissions_url()).delete()
    DataPoint.objects.bulk_create(data_points.tolist(), batch_size=1000)


class Command(BaseCommand):
    help = "Imports emissions data by council"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Update all data (slower but more thorough)",
        )
        # useful for when new data comes out and we want to replace it all
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Remove and replace all data (e.g post new source)",
        )

    def handle(self, *args, **options):
        get_all = options["all"]
        replace = options["replace"]
        if replace:
            print("Removing and replacing all data")
            DataPoint.objects.all().delete()
            DataType.objects.all().delete()
        if not get_all and DataPoint.objects.count() > 0:
            print("Emissions data exists, skipping")
        else:
            print("Creating data types")
            create_data_types()
            print("Importing emissions data")
            import_emissions_data()
            print("Checking completeness")
            check_completeness()
