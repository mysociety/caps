from os.path import join

import pandas as pd
import requests
from caps.models import Council
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Download file link from https://geoportal.statistics.gov.uk/datasets/local-authority-district-to-combined-authority-december-2019-lookup-in-england
COMBINED_AUTHORITY_MAPPING_URL = "https://opendata.arcgis.com/api/v3/datasets/86b7c99d0fe042a2975880ff9ec51c1c_0/downloads/data?format=csv&spatialRefId=4326&where=1=1"
COMBINED_AUTHORITY_MAPPING_NAME = "council_to_combined_authority.csv"
COMBINED_AUTHORITY_MAPPING = join(settings.DATA_DIR, COMBINED_AUTHORITY_MAPPING_NAME)


def get_data_files():

    data_files = [(COMBINED_AUTHORITY_MAPPING_URL, COMBINED_AUTHORITY_MAPPING)]

    for (source, destination) in data_files:
        r = requests.get(source)
        with open(destination, "wb") as outfile:
            outfile.write(r.content)


def link_combined_authorities():
    combined_authority_df = pd.read_csv(COMBINED_AUTHORITY_MAPPING)
    for index, row in combined_authority_df.iterrows():
        council_gss_code = row["LAD22CD"]
        combined_auth_gss_code = row["CAUTH22CD"]

        council = Council.objects.get(gss_code=council_gss_code)
        combined_authority = Council.objects.get(gss_code=combined_auth_gss_code)

        council.combined_authority = combined_authority
        council.save()


class Command(BaseCommand):
    help = "Adds authority codes to the csv of plans"

    def handle(self, *args, **options):
        print("getting data files")
        get_data_files()
        print("linking combined authorities")
        link_combined_authorities()
