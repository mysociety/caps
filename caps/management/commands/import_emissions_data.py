from os.path import join

import requests

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.db.models import Count

from caps.models import Council, DataType, DataPoint
import caps.dataframe.la

EMISSIONS_XLS_URL = "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/996057/2005-19_UK_local_and_regional_CO2_emissions.xlsx"

EMISSIONS_XLS_NAME = "2005-19_UK_local_and_regional_CO2_emissions.xlsx"
EMISSIONS_XLS = join(settings.DATA_DIR, EMISSIONS_XLS_NAME)
EMISSIONS_SHEET = "Subset dataset"

EMISSIONS_DATA_NAME = "emissions.csv"
EMISSIONS_DATA = join(settings.DATA_DIR, EMISSIONS_DATA_NAME)


def get_data_files():

    data_files = [(EMISSIONS_XLS_URL, EMISSIONS_XLS)]

    for (source, destination) in data_files:
        r = requests.get(source)
        with open(destination, "wb") as outfile:
            outfile.write(r.content)


def columns_to_names_and_units() -> dict:
    return {
        # these headers are sadly specific to a year so may need updated
        # when new data comes out
        "Industry Electricity": ("Industry and Commercial Electricity", "kt CO2"),
        "Industry Gas ": ("Industry and Commercial Gas", "kt CO2"),
        "Large Industrial Installations": ("Large Industrial Installations", "kt CO2"),
        "Industry 'Other Fuels'": ("Industrial and Commercial Other Fuels", "kt CO2"),
        "Agriculture": ("Agriculture", "kt CO2"),
        "Industry Total": ("Industry and Commercial Total", "kt CO2"),
        "Commercial Electricity": ("Commercial Electricity", "kt CO2"),
        "Commercial Gas ": ("Commercial Gas", "kt CO2"),
        "Commercial 'Other Fuels'": ("Commercial Other Fuels", "kt CO2"),
        "Commercial Total": ("Commercial Total", "kt CO2"),
        "Public Sector Electricity": ("Public Sector Electricity", "kt CO2"),
        "Public Sector Gas ": ("Public Sector Gas", "kt CO2"),
        "Public Sector 'Other Fuels'": ("Public Sector Other Fuels", "kt CO2"),
        "Public Sector Total": ("Public Sector Total", "kt CO2"),
        "Domestic Electricity": ("Domestic Electricity", "kt CO2"),
        "Domestic Gas": ("Domestic Gas", "kt CO2"),
        "Domestic 'Other Fuels'": ("Domestic Other Fuels", "kt CO2"),
        "Domestic Total": ("Domestic Total", "kt CO2"),
        "Road Transport (A roads)": ("Road Transport (A roads)", "kt CO2"),
        "Road Transport (Minor roads)": ("Road Transport (Minor roads)", "kt CO2"),
        "Transport Other": ("Transport Other", "kt CO2"),
        "Transport Total": ("Transport Total", "kt CO2"),
        "Grand Total": ("Total Emissions", "kt CO2"),
        "Population                                              ('000s, mid-year estimate)": (
            "Population",
            "000s",
        ),
        "Per Capita Emissions (t)": ("Per Capita Emissions", "t"),
        "Area (km2)": ("Area", "km2"),
        "Emissions per km2 (kt)": ("Emissions per km2", "kt"),
    }


def create_data_types():
    emissions_df = pd.read_csv(EMISSIONS_DATA)

    cols_to_names_and_units = columns_to_names_and_units()
    for column in emissions_df.columns[5:]:
        (name, unit) = cols_to_names_and_units[column]
        data_type, created = DataType.objects.get_or_create(
            name=name, source_url=EMISSIONS_XLS_URL, name_in_source=column, unit=unit
        )


def check_completeness():

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

    cols_to_names_and_units = columns_to_names_and_units()

    councils = {x.authority_code: x for x in Council.objects.all()}
    data_types = {
        x.name: x for x in DataType.objects.filter(source_url=EMISSIONS_XLS_URL)
    }

    # get df
    print("loading and reducing")
    df = pd.read_csv(EMISSIONS_DATA)
    df = df[~df["Code"].isnull()]

    df = df.rename(columns={x: y[0] for x, y in cols_to_names_and_units.items()})

    print("getting la codes")
    df.la.create_code_column(from_type="gss", source_col="Code").drop(
        columns=["Code", "Local Authority"]
    )

    # BEIS data will rarely be up to date enough to have the correct data for all councils
    # We need to add up new councils (generally unitaries created from a set of other councils)

    def update_to_modern(df: pd.DataFrame) -> pd.DataFrame:
        """
        return the input dataframe with modern councils calculcated from the input
        """

        # convert to modern lower tier/unitary councils
        df = df.la.to_current().la.just_lower_tier()

        # get higher geographies from lower geographies
        county_df = df.la.to_higher(aggfunc="sum")
        combined_df = df.la.to_higher(
            aggfunc="sum", comparison_column="combined-authority"
        )

        # need to recreate because cannot be calculated from sum

        for hdf in [county_df, combined_df]:
            # both total emissions and population are stored in 1000s, so this keeps to tons
            hdf["Per Capita Emissions"] = hdf["Total Emissions"] / hdf["Population"]
            hdf["Emissions per km2"] = hdf["Total Emissions"] / hdf["Area"]

        return pd.concat([df, county_df, combined_df]).drop(columns=["Year"])

    print("updating to modern councils")
    df = df.groupby("Year").apply(update_to_modern).reset_index()

    # convert from wide to long format
    df = df.melt(
        ["local-authority-code", "Year"], var_name="emissions_type", value_name="value"
    )

    overall_values = ["Per Capita Emissions", "Emissions per km2", "Total Emissions"]

    # only want the grand total and overall values
    df = df[
        df["emissions_type"].str.endswith("Total")
        | df["emissions_type"].isin(overall_values)
    ]

    # create column with the council objects and remove any rows without a council in the database
    df["council_obj"] = df["local-authority-code"].apply(
        lambda x: councils.get(x, None)
    )
    df = df[~df["council_obj"].isna()]

    # get the DataType object
    df["data_type_obj"] = df["emissions_type"].apply(data_types.get)

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
    DataPoint.objects.filter(data_type__source_url=EMISSIONS_XLS_URL).delete()
    DataPoint.objects.bulk_create(data_points.tolist())


def convert_emissions_data():

    emissions_df = pd.read_excel(EMISSIONS_XLS, sheet_name=EMISSIONS_SHEET)
    emissions_df.to_csv(EMISSIONS_DATA, index=False, header=False)


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
            print("removing and replacing all data")
            DataPoint.objects.all().delete()
            DataType.objects.all().delete()
        if not get_all and DataPoint.objects.count() > 0:
            print("emissions data exists, skipping")
        else:
            print("getting data files")
            get_data_files()
            print("converting emissions data")
            convert_emissions_data()
            print("creating data types")
            create_data_types()
            print("importing emissions data")
            import_emissions_data()
            print("checking completeness")
            check_completeness()
