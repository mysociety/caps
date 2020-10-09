from os.path import join, basename, splitext, isfile
import glob

import pandas as pd

import pdftotext

DATA_DIR = 'data'
PROCESSED_CSV_NAME = 'plans.csv'
PROCESSED_CSV = join(DATA_DIR, PROCESSED_CSV_NAME)
PLANS_DIR = join(DATA_DIR, 'plans')
PUBLISH_URL = 'https://council-climate-action-plans.herokuapp.com/static/'

def add_text_to_csv():
    df = pd.read_csv(PROCESSED_CSV)
    rows = len(df['council'])

    # add a text column to the CSV
    df['text'] = pd.Series([None] * rows, index=df.index)

    # convert each PDF to text and add the text to the column
    pdf_rows = df['file_type'] == 'pdf'
    for index, row in df[pdf_rows].iterrows():
        filename = basename(row['plan_link'])
        pdf_path = join(PLANS_DIR, filename)
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

print("adding text to the csv")
add_text_to_csv()
