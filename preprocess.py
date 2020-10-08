from os.path import join, basename, splitext, isfile
import os
import sys
import glob
import hashlib

import requests
from urllib.parse import urlparse

import pandas as pd

from slugify import slugify
import pdftotext

import ssl


DATA_DIR = 'data'
PLANS_CSV_KEY = '1tEnjJRaWsdXtCkMwA25-ZZ8D75zAY6c2GOOeUchZsnU'
SHEET_NAME = 'Councils'
RAW_CSV_NAME = 'raw_plans.csv'
RAW_CSV = join(DATA_DIR, RAW_CSV_NAME)
PROCESSED_CSV_NAME = 'plans.csv'
PROCESSED_CSV = join(DATA_DIR, PROCESSED_CSV_NAME)
DB_NAME = 'plans.db'
DB = join(DATA_DIR, DB_NAME)
PLANS_DIR = join(DATA_DIR, 'plans')
PUBLISH_URL = 'https://council-climate-action-plans.herokuapp.com/static/'

ssl._create_default_https_context = ssl._create_unverified_context

def get_url_hash(url):
  return hashlib.md5(url.encode('utf-8')).hexdigest()[:7]


def get_plan_filename(row):
  return f"{slugify(row['council'])}-{get_url_hash(row['url'])}"

def get_individual_plans():
    df = pd.read_csv(PROCESSED_CSV)
    rows = len(df['council'])

    # add a file column to the CSV
    df['plan_link'] = pd.Series([None] * rows, index=df.index)

    rows_with_urls = df['url'].notnull()
    for index, row in df[rows_with_urls].iterrows():
        url = urlparse(row['url'])
        filepath, extension = splitext(url.path)
        filename = basename(url.path)
        new_filename = get_plan_filename(row) + extension
        local_path = join(PLANS_DIR, new_filename)
        if not os.path.isfile(local_path):
            print(f"Trying {row['url']} for {row['council']} {new_filename}")
            try:
                headers = {
                    'User-Agent': 'mySociety Council climate action plans search',
                }

                r = requests.get(row['url'], headers=headers)
                r.raise_for_status()
                with open(local_path, 'wb') as outfile:
                    outfile.write(r.content)
            except requests.exceptions.HTTPError as err:
                print(f"Error with {row['council']} {row['url']}: {err}")

        df.at[index, 'plan_link'] = PUBLISH_URL + new_filename



    df.to_csv(open(PROCESSED_CSV, "w"), index=False, header=True)


def add_text_to_csv():
    df = pd.read_csv(PROCESSED_CSV)
    rows = len(df['council'])

    # add a text column to the CSV
    df['text'] = pd.Series([None] * rows, index=df.index)


    # convert each PDF to text and add the text to the column
    for pdf_path in glob.glob(join(PLANS_DIR, "*.pdf")):
        with open(pdf_path, "rb") as f:
            pdf_filename = basename(pdf_path)
            index = df[df['plan_link'] == PUBLISH_URL + pdf_filename].index.values[0]
            try:
                pdf = pdftotext.PDF(f)
                df.at[index, 'text'] = " ".join(pdf).replace('\n', ' ')
            except pdftotext.Error as err:
                print(f"Error getting PDF text for {pdf_filename}")

    # save the CSV
    df.to_csv(open(PROCESSED_CSV, "w"), index=False, header=True)

def get_plans_csv():
    # Get the google doc as a CSV file
    sheet_url = f"https://docs.google.com/spreadsheets/d/{PLANS_CSV_KEY}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
    r = requests.get(sheet_url)
    with open(RAW_CSV, 'wb') as outfile:
        outfile.write(r.content)

# Replace the column header lines
def replace_headers():
    df = pd.read_csv(RAW_CSV)
    df = df.dropna('columns', 'all')

    #strip the first two rows
    df = df.iloc[2:]
    df.columns = ['council',
                  'search_link',
                  'unfound',
                  'credit',
                  'url',
                  'date_retrieved',
                  'type',
                  'scope',
                  'status',
                  'well_presented',
                  'baseline_analysis',
                  'notes',
                  'plan_due']
    df.to_csv(open(PROCESSED_CSV, "w"), index=False, header=True)

def convert_csv_to_sqlite():
    os.remove(DB)
    os.system(f"csvs-to-sqlite {PROCESSED_CSV} {DB} -f text")


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

print("getting the csv")
get_plans_csv()
print("replacing headers")
replace_headers()
print('getting plans')
get_individual_plans()
print('adding authority codes')
add_authority_codes()
print('adding authority info')
add_extra_authority_info()
print("adding text to the csv")
add_text_to_csv()
print("converting to sqlite")
convert_csv_to_sqlite()

