from os.path import join, basename, splitext, isfile
import glob

import pandas as pd

import pdftotext

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from caps.models import PlanDocument


def generate_text(pdf_path, df, index):

    with open(pdf_path, "rb") as f:
        pdf_filename = basename(pdf_path)
        try:
            pdf = pdftotext.PDF(f)
            df.at[index, "text"] = " ".join(pdf).replace("\n", " ")
        except pdftotext.Error as err:
            print(f"Error getting PDF text for {pdf_filename}")


def add_text_to_csv(get_all):
    df = pd.read_csv(settings.PROCESSED_CSV)
    rows = len(df["council"])

    # add a text column to the CSV
    df["text"] = pd.Series([None] * rows, index=df.index)

    # convert each PDF to text and add the text to the column
    pdf_rows = df["file_type"] == "pdf"
    for index, row in df[pdf_rows].iterrows():
        filename = basename(row["plan_path"])
        url = row["url"]
        url_hash = PlanDocument.make_url_hash(url)
        council = row["council"]
        pdf_path = join(settings.PLANS_DIR, filename)
        if get_all:
            generate_text(pdf_path, df, index)
        else:
            try:
                plan_document = PlanDocument.objects.get(
                    url_hash=url_hash, council__name=council
                )
                df.at[index, "text"] = plan_document.text
            except PlanDocument.DoesNotExist:
                generate_text(pdf_path, df, index)

    # save the CSV
    df.to_csv(open(settings.PROCESSED_CSV, "w"), index=False, header=True)


class Command(BaseCommand):
    help = "Adds text to the csv of plans"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Update all data (slower but more thorough)",
        )

    def handle(self, *args, **options):
        get_all = options["all"]
        print("adding text to the csv")
        add_text_to_csv(get_all)
