from os.path import join, basename, splitext, isfile
import os
import sys
import glob

import urllib.request
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
        # TODO: Need a solution for multiple rows per council but
        # row index will change if rows are inserted in original sheet
        new_filename = f"{index}-{slugify(row['council'])}" + extension
        try:
            local_path = join(PLANS_DIR, new_filename)
            if not os.path.isfile(local_path):
                urllib.request.urlretrieve(row['url'], local_path)
            df.at[index, 'plan_link'] = PUBLISH_URL + new_filename

        except (urllib.error.HTTPError, urllib.error.URLError) as err:
            print(f"Error with {row['council']} {row['url']}: {err}")

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
            index = int(pdf_filename.split('-')[0])
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
    filename, headers = urllib.request.urlretrieve(sheet_url, RAW_CSV)

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
    os.system(f"csvs-to-sqlite {PROCESSED_CSV} {DB} -f text")


get_plans_csv()
replace_headers()
get_individual_plans()
add_text_to_csv()
convert_csv_to_sqlite()

