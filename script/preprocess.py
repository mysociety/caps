from os.path import join, basename, splitext, isfile
import os
import sys
import hashlib

import requests
from urllib.parse import urlparse

import pandas as pd

from slugify import slugify

import ssl

DATA_DIR = 'data'
PLANS_CSV_KEY = '1tEnjJRaWsdXtCkMwA25-ZZ8D75zAY6c2GOOeUchZsnU'
SHEET_NAME = 'Councils'
RAW_CSV_NAME = 'raw_plans.csv'
RAW_CSV = join(DATA_DIR, RAW_CSV_NAME)
PROCESSED_CSV_NAME = 'plans.csv'
PROCESSED_CSV = join(DATA_DIR, PROCESSED_CSV_NAME)

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
                  'time_period',
                  'type',
                  'scope',
                  'status',
                  'well_presented',
                  'baseline_analysis',
                  'notes',
                  'plan_due']
    df.to_csv(open(PROCESSED_CSV, "w"), index=False, header=True)

print("getting the csv")
get_plans_csv()
print("replacing headers")
replace_headers()
print('getting plans')
get_individual_plans()


