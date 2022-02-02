from os.path import join, basename, splitext, isfile
import os
import sys


import requests
from urllib.parse import urlparse
import urllib3

import pandas as pd
import numpy

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from caps.models import PlanDocument
from caps.import_utils import get_google_sheet_as_csv, replace_csv_headers

import ssl


ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def set_file_attributes(df, index, content_type, extension):
    content_type = content_type.lower()
    extension = extension.lower()
    content_type_info = content_type.split(";", 2)
    file_type = content_type_info[0].strip()
    if len(content_type_info) > 1:
        charset = content_type_info[1].replace("charset=", "").strip()
        df.at[index, "charset"] = charset

    if file_type == "application/pdf" or extension == ".pdf":
        df.at[index, "file_type"] = "pdf"
    elif file_type == "text/html":
        df.at[index, "file_type"] = "html"
    elif extension == ".docx":
        df.at[index, "file_type"] = "docx"
    elif (
        content_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ):
        df.at[index, "file_type"] = "xlsx"
    elif content_type == "application/vnd.ms-excel.sheet.macroenabled.12":
        df.at[index, "file_type"] = "xlsm"
    else:
        print("Unknown content type: " + content_type)


def get_plan(row, index, df):
    url = row["url"]
    council = row["council"]
    new_filename = PlanDocument.plan_filename(council, url)
    url_parts = urlparse(url)
    filepath, extension = splitext(url_parts.path)
    headers = {
        "User-Agent": "mySociety Council climate action plans search",
    }
    try:
        r = requests.get(url, headers=headers, verify=False)
        r.raise_for_status()
        set_file_attributes(df, index, r.headers.get("content-type"), extension)
        new_filename = new_filename + "." + df.at[index, "file_type"]
        local_path = join(settings.PLANS_DIR, new_filename)
        df.at[index, "plan_path"] = local_path
        with open(local_path, "wb") as outfile:
            outfile.write(r.content)
    except requests.exceptions.RequestException as err:
        print(f"Error {council} {url}: {err}")
        df.at[index, "url"] = numpy.nan


def update_plan(row, index, df, get_all):
    url = row["url"]
    council = row["council"]
    url_hash = PlanDocument.make_url_hash(url)
    new_filename = PlanDocument.plan_filename(council, url)
    if get_all:
        get_plan(row, index, df)
    else:
        # If we've already loaded a document from this URL, don't get the file again
        try:
            plan_document = PlanDocument.objects.get(
                url_hash=url_hash, council__name=council
            )
            df.at[index, "charset"] = plan_document.charset
            df.at[index, "file_type"] = plan_document.file_type
            new_filename = new_filename + "." + plan_document.file_type
            local_path = join(settings.PLANS_DIR, new_filename)
            df.at[index, "plan_path"] = local_path
        except PlanDocument.DoesNotExist:
            get_plan(row, index, df)


def get_individual_plans(get_all):
    df = pd.read_csv(settings.PROCESSED_CSV)
    rows = len(df["council"])

    # add a file column to the CSV
    df["plan_path"] = pd.Series([None] * rows, index=df.index)

    # add a file type and charset column to the CSV
    df["file_type"] = pd.Series([None] * rows, index=df.index)
    df["charset"] = pd.Series([None] * rows, index=df.index)

    rows_with_urls = df["url"].notnull()
    for index, row in df[rows_with_urls].iterrows():
        update_plan(row, index, df, get_all)

    df.to_csv(open(settings.PROCESSED_CSV, "w"), index=False, header=True)


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
            "search_link",
            "unfound",
            "credit",
            "url",
            "date_retrieved",
            "time_period",
            "type",
            "scope",
            "status",
            "homepage_mention",
            "dedicated_page",
            "well_presented",
            "baseline_analysis",
            "notes",
            "plan_due",
            "title",
            "title_checked",
        ],
    )


class Command(BaseCommand):
    help = "Preprocesses plans csv data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Update all data (slower but more thorough)",
        )

    def handle(self, *args, **options):
        get_all = options["all"]
        print("getting the csv")
        get_plans_csv()
        print("replacing headers")
        replace_headers()
        print("getting plans")
        get_individual_plans(get_all)
