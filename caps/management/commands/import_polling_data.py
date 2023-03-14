"""
Import local authority_emissions
"""
import pandas as pd
from caps.models import Council, DataPoint, DataType
from django.core.management.base import BaseCommand
from django.db.models import Count
from mysoc_dataset import get_dataset_url, get_dataset_df


def create_data_types():
    """
    Create data types to capture the local authority polling
    """
    url = get_dataset_url(
        repo_name="climate_mrp_polling",
        package_name="local_authority_climate_polling",
        version_name="latest",
        file_name="local_authority_climate_polling_guide.csv",
        done_survey=True,
    )

    df = pd.read_csv(url)

    data_types = []
    print("Creating data types")
    for index, row in df.iterrows():
        d = DataType(
            name=row["short"],
            source_url=url,
            name_in_source=row["source"],
            unit="percentage",
            collection=DataType.DataCollection.POLLING,
        )
        data_types.append(d)

    print("Loading to database")
    DataType.objects.filter(collection=DataType.DataCollection.POLLING).delete()
    DataType.objects.bulk_create(data_types)


def import_polling_data():
    """
    Load polling data for local authorities
    """

    df = get_dataset_df(
        repo_name="climate_mrp_polling",
        package_name="local_authority_climate_polling",
        version_name="latest",
        file_name="local_authority_climate_polling.csv",
        done_survey=True,
    )

    councils = {x.authority_code: x for x in Council.objects.all()}
    types = {f"{x.name_in_source}-{x.name}": x for x in DataType.objects.all()}

    new_points = []
    print("Creating data points")
    for index, row in df.iterrows():
        lookup_id = f"{row['source']}-{row['question']}"
        council = councils.get(row["local-authority-code"], None)
        if council is None:
            print(f"Skipping {row['local-authority-code']}")
            continue
        data_type = types[lookup_id]
        d = DataPoint(
            year=2022, council=council, data_type=data_type, value=row["percentage"]
        )
        new_points.append(d)
    print("Loading to database")

    polling_types = DataType.objects.filter(collection=DataType.DataCollection.POLLING)
    polling_points = DataPoint.objects.filter(data_type__in=polling_types)
    polling_points.delete()
    DataPoint.objects.bulk_create(new_points)


class Command(BaseCommand):
    help = "Imports polling data for local authorities"

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
        polling_types = DataType.objects.filter(
            collection=DataType.DataCollection.POLLING
        )
        polling_points = DataPoint.objects.filter(data_type__in=polling_types)
        if replace:
            print("Removing and replacing all data")
            polling_points.delete()
            polling_types.delete()

        if not get_all and polling_points.count() > 0:
            print("Polling data exists, skipping")
        else:
            print("Creating data types")
            create_data_types()
            print("Importing polling data")
            import_polling_data()
