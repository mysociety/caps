from os.path import join

import requests
import urllib3

import pandas as pd

from django.conf import settings

import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AUTHORITY_MAPPING_URL = 'https://raw.githubusercontent.com/crowbot/uk_local_authority_names_and_codes/master/lookup_name_to_registry.csv'
AUTHORITY_MAPPING_NAME = 'lookup_name_to_registry.csv'
AUTHORITY_MAPPING = join(settings.DATA_DIR, AUTHORITY_MAPPING_NAME)

AUTHORITY_DATA_URL = 'https://raw.githubusercontent.com/crowbot/uk_local_authority_names_and_codes/master/uk_local_authorities.csv'
AUTHORITY_DATA_NAME = 'uk_local_authorities.csv'
AUTHORITY_DATA = join(settings.DATA_DIR, AUTHORITY_DATA_NAME)

COMBINED_AUTHORITY_DATA_URL = 'http://geoportal1-ons.opendata.arcgis.com/datasets/43d30f924b29452b881e1820dcf897f9_0.csv'
COMBINED_AUTHORITY_DATA_NAME = 'combined_authorities.csv'
COMBINED_AUTHORITY_DATA = join(settings.DATA_DIR, COMBINED_AUTHORITY_DATA_NAME)

def get_data_files():

    data_files = [(AUTHORITY_MAPPING_URL, AUTHORITY_MAPPING),
                  (AUTHORITY_DATA_URL, AUTHORITY_DATA),
                  (COMBINED_AUTHORITY_DATA_URL, COMBINED_AUTHORITY_DATA)]

    for (source, destination) in data_files:
        r = requests.get(source)
        with open(destination, 'wb') as outfile:
            outfile.write(r.content)

def add_authority_codes(filename):
    mapping_df = pd.read_csv(AUTHORITY_MAPPING)

    plans_df = pd.read_csv(filename)

    rows = len(plans_df['council'])

    plans_df['authority_code'] = pd.Series([None] * rows, index=plans_df.index)

    names_to_codes = {}
    for index, row in mapping_df.iterrows():
        names_to_codes[row['la name'].lower()] = row['local-authority-code']

    for index, row in plans_df.iterrows():
        council = row['council'].lower()

        name_versions = [council, council.replace('council', '').strip(), council.replace('- unitary', '').replace('(unitary)', '').strip()]
        for version in name_versions:
            if version in names_to_codes:
                plans_df.at[index, 'authority_code'] = names_to_codes[version]
                break
    plans_df.to_csv(open(filename, "w"), index=False, header=True)

def add_gss_codes(filename):

    authority_df = pd.read_csv(AUTHORITY_DATA)
    plans_df = pd.read_csv(filename)

    rows = len(plans_df['council'])
    plans_df['gss_code'] = pd.Series([None] * rows, index=plans_df.index)

    for index, row in plans_df.iterrows():
        authority_code = row['authority_code']
        if not pd.isnull(authority_code):
            authority_match = authority_df[authority_df['local-authority-code'] == authority_code]
            plans_df.at[index, 'gss_code'] = authority_match['gss-code'].values[0]

    plans_df.to_csv(open(filename, "w"), index=False, header=True)

def add_extra_authority_info(filename):

    authority_df = pd.read_csv(AUTHORITY_DATA)
    plans_df = pd.read_csv(filename)

    rows = len(plans_df['council'])
    plans_df['authority_type'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['wdtk_id'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['mapit_area_code'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['country'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['gss_code'] = pd.Series([None] * rows, index=plans_df.index)

    for index, row in plans_df.iterrows():
        authority_code = row['authority_code']
        if not pd.isnull(authority_code):
            authority_match = authority_df[authority_df['local-authority-code'] == authority_code]
            country = None
            country = authority_match['nation'].values[0]
            plans_df.at[index, 'authority_type'] = authority_match['local-authority-type'].values[0]
            plans_df.at[index, 'wdtk_id'] = authority_match['wdtk_ids'].values[0]
            plans_df.at[index, 'mapit_area_code'] = authority_match['mapit_area_code'].values[0]
            plans_df.at[index, 'country'] = country
            plans_df.at[index, 'gss_code'] = authority_match['gss-code'].values[0]

            # All authorities in Wales, Scotland and Northern Ireland are unitary
            if country in ['Wales', 'Scotland', 'Northern Ireland']:
                plans_df.at[index, 'authority_type'] = 'UA'
    plans_df.to_csv(open(filename, "w"), index=False, header=True)

def add_combined_authority_gss_codes(filename):
    plans_df = pd.read_csv(filename)
    combined_authority_df = pd.read_csv(COMBINED_AUTHORITY_DATA)

    aliases = {'newcastle upon tyne, north tyneside and northumberland combined authority': 'north of tyne'}

    names_to_codes = {}
    for index, row in combined_authority_df.iterrows():
        names_to_codes[row['CAUTH19NM'].lower()] = row['CAUTH19CD']
    for index, row in plans_df.iterrows():
        council = row['council'].lower()
        if row['authority_type'] == 'COMB':
            name_versions = [council, council.replace('combined authority', '').strip()]
            if council in aliases:
                name_versions.append(aliases[council])
            for version in name_versions:
                if version in names_to_codes:
                    plans_df.at[index, 'gss_code'] = names_to_codes[version]
                    break

    plans_df.to_csv(open(filename, "w"), index=False, header=True)

