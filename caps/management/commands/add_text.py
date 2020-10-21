# -*- coding: future_fstrings -*-
from os.path import join, basename, splitext, isfile
import glob

import pandas as pd

import pdftotext

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

PUBLISH_URL = 'https://council-climate-action-plans.herokuapp.com/static/'

def add_text_to_csv():
    df = pd.read_csv(settings.PROCESSED_CSV)
    rows = len(df['council'])

    # add a text column to the CSV
    df['text'] = pd.Series([None] * rows, index=df.index)

    # convert each PDF to text and add the text to the column
    pdf_rows = df['file_type'] == 'pdf'
    for index, row in df[pdf_rows].iterrows():
        filename = basename(row['plan_path'])
        pdf_path = join(settings.PLANS_DIR, filename)
        with open(pdf_path, "rb") as f:
            pdf_filename = basename(pdf_path)
            index = df[df['plan_path'] == pdf_filename].index.values[0]
            try:
                pdf = pdftotext.PDF(f)
                df.at[index, 'text'] = " ".join(pdf).replace('\n', ' ')
            except pdftotext.Error as err:
                print(f"Error getting PDF text for {pdf_filename}")

    # save the CSV
    df.to_csv(open(settings.PROCESSED_CSV, "w"), index=False, header=True)

class Command(BaseCommand):
    help = 'Adds text to the csv of plans'

    def handle(self, *args, **options):

        print("adding text to the csv")
        add_text_to_csv()
