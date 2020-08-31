from os.path import join

import pandas as pd


DATA_DIR = 'data'
PROCESSED_CSV_NAME = 'plans.csv'
PROCESSED_CSV = join(DATA_DIR, PROCESSED_CSV_NAME)

AUTHORITY_MAPPING_NAME = 'lookup_name_to_registry.csv'
AUTHORITY_MAPPING = join(DATA_DIR, AUTHORITY_MAPPING_NAME)

AUTHORITY_DATA_NAME = 'uk_local_authorities.csv'
AUTHORITY_DATA = join(DATA_DIR, AUTHORITY_DATA_NAME)

def add_authority_codes():
    mapping_df = pd.read_csv(AUTHORITY_MAPPING)

    plans_df = pd.read_csv(PROCESSED_CSV)

    rows = len(plans_df['council'])

    plans_df['authority_code'] = pd.Series([None] * rows, index=plans_df.index)

    names_to_codes = {}
    for index, row in mapping_df.iterrows():
        names_to_codes[row['la name'].lower()] = row['local-authority-code']

    missing_councils = []
    for index, row in plans_df.iterrows():
        council = row['council'].lower()
        found = False
        name_versions = [council, council.rstrip('council').strip(), council.rstrip('- unitary').rstrip('(unitary)').strip()]
        for version in name_versions:
            if version in names_to_codes:
                plans_df.at[index, 'authority_code'] = names_to_codes[version]
                found = True
                break
        if found == False:
            missing_councils.append(council)
    plans_df.to_csv(open(PROCESSED_CSV, "w"), index=False, header=True)

    print(len(missing_councils))

def add_extra_authority_info():

    authority_df = pd.read_csv(AUTHORITY_DATA)
    plans_df = pd.read_csv(PROCESSED_CSV)

    rows = len(plans_df['council'])

    plans_df['authority_type'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['wdtk_id'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['mapit_id'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['lat'] = pd.Series([None] * rows, index=plans_df.index)
    plans_df['lon'] = pd.Series([None] * rows, index=plans_df.index)

    for index, row in plans_df.iterrows():
        authority_code = row['authority_code']
        if not pd.isnull(authority_code):
            authority_match = authority_df[authority_df['local-authority-code'] == authority_code]
            plans_df.at[index, 'authority_type'] = authority_match['local-authority-type'].values[0]
            plans_df.at[index, 'wdtk_id'] = authority_match['wdtk_ids'].values[0]
            plans_df.at[index, 'mapit_id'] = authority_match['mapit_area_code'].values[0]
            plans_df.at[index, 'lat'] = authority_match['lat'].values[0]
            plans_df.at[index, 'lon'] = authority_match['long'].values[0]
    plans_df.to_csv(open(PROCESSED_CSV, "w"), index=False, header=True)

add_authority_codes()
add_extra_authority_info()
