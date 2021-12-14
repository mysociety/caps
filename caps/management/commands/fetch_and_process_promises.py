import requests
import urllib3

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from caps.import_utils import add_authority_codes, add_gss_codes

import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_promises():
    # Get the google doc as a CSV file
    sheet_url = f"https://docs.google.com/spreadsheets/d/{settings.PROMISES_CSV_KEY}/gviz/tq?tqx=out:csv&sheet={settings.PROMISES_CSV_SHEET_NAME}"
    r = requests.get(sheet_url)
    with open(settings.PROMISES_CSV, "wb") as outfile:
        outfile.write(r.content)


# Replace the column header lines
def replace_headers():
    df = pd.read_csv(settings.PROMISES_CSV)
    df = df.dropna(axis="columns", how="all")

    df.columns = [
        "council",
        "scope",
        "target",
        "wording",
        "source_url",
        "source_name",
        "notes",
    ]
    df.to_csv(open(settings.PROMISES_CSV, "w"), index=False, header=True)


class Command(BaseCommand):
    help = "fetch and import promises data"

    def handle(self, *args, **options):
        print("getting the promises csv")
        get_promises()
        print("replacing promises headers")
        replace_headers()
        print("adding council codes to promises")
        add_authority_codes(settings.PROMISES_CSV)
        add_gss_codes(settings.PROMISES_CSV)
