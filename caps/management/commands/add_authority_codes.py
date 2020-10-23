# -*- coding: future_fstrings -*-
from os.path import join, basename, splitext, isfile

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

AUTHORITY_MAPPING_NAME = 'lookup_name_to_registry.csv'
AUTHORITY_MAPPING = join(settings.DATA_DIR, AUTHORITY_MAPPING_NAME)

AUTHORITY_DATA_NAME = 'uk_local_authorities.csv'
AUTHORITY_DATA = join(settings.DATA_DIR, AUTHORITY_DATA_NAME)

def add_authority_codes():
    mapping_df = pd.read_csv(AUTHORITY_MAPPING)

    plans_df = pd.read_csv(settings.PROCESSED_CSV)

    rows = len(plans_df['council'])

    plans_df['authority_code'] = pd.Series([None] * rows, index=plans_df.index)

    names_to_codes = {}
    for index, row in mapping_df.iterrows():
        names_to_codes[row['la name'].lower()] = row['local-authority-code']

    for index, row in plans_df.iterrows():
        council = row['council'].lower()

        name_versions = [council, council.rstrip('council').strip(), council.rstrip('- unitary').rstrip('(unitary)').strip()]
        for version in name_versions:
            if version in names_to_codes:
                plans_df.at[index, 'authority_code'] = names_to_codes[version]
                break
    plans_df.to_csv(open(settings.PROCESSED_CSV, "w"), index=False, header=True)


def add_extra_authority_info():

    authority_df = pd.read_csv(AUTHORITY_DATA)
    plans_df = pd.read_csv(settings.PROCESSED_CSV)

    rows = len(plans_df['council'])
    plans_df['authority_type'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['wdtk_id'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['mapit_area_code'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['country'] = pd.Series([None] * rows, index=plans_df.index)

    for index, row in plans_df.iterrows():
        authority_code = row['authority_code']
        if not pd.isnull(authority_code):
            authority_match = authority_df[authority_df['local-authority-code'] == authority_code]
            country = None
            register = authority_match['register'].values[0]
            if register == 'principal-local-authority':
                country = "Wales"
            elif register == 'local-authority-sct':
                country = "Scotland"
            elif register == 'local-authority-eng':
                country = "England"
            elif register == 'local-authority-nir':
                country = "Northern Ireland"
            else:
                raise Exception(f'Unknown register type: {register}')

            plans_df.at[index, 'authority_type'] = authority_match['local-authority-type'].values[0]
            plans_df.at[index, 'wdtk_id'] = authority_match['wdtk_ids'].values[0]
            plans_df.at[index, 'mapit_area_code'] = authority_match['mapit_area_code'].values[0]
            plans_df.at[index, 'country'] = country
    plans_df.to_csv(open(settings.PROCESSED_CSV, "w"), index=False, header=True)

def add_missing_authorities():
    plans_df = pd.read_csv(settings.PROCESSED_CSV)
    manual_codes = { 'West Yorkshire Combined Authority': ['WYCA', 'COMB', '52339', 'England'],
                     'North East Combined Authority': ['NECA', 'COMB', '52428', 'England'],
                     'Newcastle Upon Tyne, North Tyneside and Northumberland Combined Authority': ['NTCA', 'COMB', '91532', 'England']
                    }

    missing_councils = []
    for index, row in plans_df[plans_df['authority_code'].isnull()].iterrows():
        council = row['council']
        authority_code = row['authority_code']

        if council in manual_codes:
            plans_df.at[index, 'authority_code'] = manual_codes[council][0]
            plans_df.at[index, 'authority_type'] = manual_codes[council][1]
            plans_df.at[index, 'wdtk_id'] = manual_codes[council][2]
            plans_df.at[index, 'country'] = manual_codes[council][3]
        else:
            missing_councils.append(council)

    plans_df.to_csv(open(settings.PROCESSED_CSV, "w"), index=False, header=True)
    print(f"Councils without authority codes {len(missing_councils)}")
    print(missing_councils)

class Command(BaseCommand):
    help = 'Adds authority codes to the csv of plans'

    def handle(self, *args, **options):
        print('adding authority codes')
        add_authority_codes()
        print('adding authority info')
        add_extra_authority_info()
        print('adding missing authorities')
        add_missing_authorities()
