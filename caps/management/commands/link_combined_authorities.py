# -*- coding: future_fstrings -*-
from os.path import join

import requests

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import pandas as pd

from caps.models import Council

# Download file link from https://geoportal.statistics.gov.uk/datasets/local-authority-district-to-combined-authority-december-2019-lookup-in-england
COMBINED_AUTHORITY_MAPPING_URL = 'https://prod-hub-indexer.s3.amazonaws.com/files/db4f8bae6bfa41babfafea3ec8a38c0e/0/full/4326/db4f8bae6bfa41babfafea3ec8a38c0e_0_full_4326.csv'
COMBINED_AUTHORITY_MAPPING_NAME = 'council_to_combined_authority.csv'
COMBINED_AUTHORITY_MAPPING = join(settings.DATA_DIR, COMBINED_AUTHORITY_MAPPING_NAME)

def get_data_files():

    data_files = [(COMBINED_AUTHORITY_MAPPING_URL, COMBINED_AUTHORITY_MAPPING)]

    for (source, destination) in data_files:
        r = requests.get(source)
        with open(destination, 'wb') as outfile:
            outfile.write(r.content)

def link_combined_authorities():
    combined_authority_df = pd.read_csv(COMBINED_AUTHORITY_MAPPING)
    for index, row in combined_authority_df.iterrows():
        council_gss_code = row['LAD19CD']
        combined_auth_gss_code = row['CAUTH19CD']

        council = Council.objects.get(gss_code=council_gss_code)
        combined_authority = Council.objects.get(gss_code=combined_auth_gss_code)

        council.combined_authority = combined_authority
        council.save()

class Command(BaseCommand):
    help = 'Adds authority codes to the csv of plans'

    def handle(self, *args, **options):
        print('getting data files')
        get_data_files()
        print('linking combined authorities')
        link_combined_authorities()
