import os

import numpy as np
import pandas as pd
from caps.import_utils import (add_authority_codes, add_extra_authority_info,
                               get_google_sheet_as_csv, replace_csv_headers)
from caps.models import Council, PlanDocument
from caps.utils import char_from_text, date_from_text, integer_from_text
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# from os.path import basename, isfile, join, splitext


outfile = os.path.join(settings.DATA_DIR, "council_data.csv")


def get_plans_csv():
    get_google_sheet_as_csv(
        settings.PLANS_CSV_KEY,
        settings.RAW_CSV,
        sheet_name=settings.PLANS_CSV_SHEET_NAME,
    )


# Replace the column header lines
def replace_headers():
    replace_csv_headers(
        settings.RAW_CSV,
        [
            "council",
            "url",
            "date_retrieved",
            "type",
            "title",
            "out_of_date",
        ],
        outfile=outfile,
    )


def update_database():
    df = pd.read_csv(outfile)

    df["start-date"] = (
        pd.to_datetime(df["start-date"])
        .dt.date.fillna(np.nan)
        .replace([np.nan], [None])
    )
    df["end-date"] = (
        pd.to_datetime(df["end-date"]).dt.date.fillna(np.nan).replace([np.nan], [None])
    )

    df["gss_code"] = df["gss_code"].fillna("temp" + df["authority_code"])
    for index, row in df.iterrows():
        region = char_from_text(row["region"])
        county = char_from_text(row["county"])
        population = integer_from_text(row["population"]) or 0
        council, created = Council.objects.get_or_create(
            authority_code=char_from_text(row["authority_code"]),
            country=Council.country_code(row["country"]),
            defaults={
                "authority_type": char_from_text(row["authority_type"]),
                "name": row["council"],
                "slug": PlanDocument.council_slug(row["council"]),
                "gss_code": char_from_text(row["gss_code"]),
                "whatdotheyknow_id": integer_from_text(row["wdtk_id"]),
                "mapit_area_code": char_from_text(row["mapit_area_code"]),
                "county": county,
                "region": region,
                "population": population,
                "start_date": row["start-date"],
                "end_date": row["end-date"],
                "replaced_by": char_from_text(row["replaced-by"]),
            },
        )


class Command(BaseCommand):
    help = "Populate council data for scorecards"

    def handle(self, *args, **options):
        get_plans_csv()
        print("replacing headers")
        replace_headers()
        add_authority_codes(outfile)
        add_extra_authority_info(outfile)
        update_database()
