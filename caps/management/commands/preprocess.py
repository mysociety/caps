import os
import ssl
import sys
from functools import lru_cache
from os.path import basename, isfile, join, splitext
from urllib.parse import urlparse

import numpy
import pandas as pd
import requests
import urllib3
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from caps.import_utils import get_google_sheet_as_csv, replace_csv_headers
from caps.models import PlanDocument

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
    elif content_type == "application/msword":
        df.at[index, "file_type"] = "doc"
    else:
        print("Unknown content type: " + content_type)


@lru_cache
def get_retry_requester():
    """
    Get requests session that will retry on failure
    """
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    return http


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
        r = get_retry_requester().get(url, headers=headers, verify=False, timeout=10)
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
            print(f"fetching: {url} ({url_hash}) ")
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
            "url",
            "date_retrieved",
            "type",
            "title",
            "out_of_date",
        ],
        outfile=settings.PROCESSED_CSV,
    )
    df = pd.read_csv(settings.PROCESSED_CSV)

    # where out of date is true,
    # blank all other columns so we still create the council entry
    is_out_of_date = df["out_of_date"] == True
    df.loc[is_out_of_date, "url"] = None
    df.loc[is_out_of_date, "date_retrieved"] = None
    df.loc[is_out_of_date, "type"] = None
    df.loc[is_out_of_date, "title"] = None

    # there shouldn't be any blank 'council' items, check this
    is_blank_council = df["council"].isnull()
    if is_blank_council.any():
        for index, row in df[is_blank_council].iterrows():
            raise CommandError(f"Blank council name in row {index}")

    # don't use these columns anymore, but creating empty entries for them
    empty_columns = [
        "search_link",
        "unfound",
        "credit",
        "time_period",
        "scope",
        "status",
        "homepage_mention",
        "dedicated_page",
        "well_presented",
        "baseline_analysis",
        "notes",
        "plan_due",
        "title_checked",
    ]

    for column in empty_columns:
        df[column] = pd.Series([None] * len(df["council"]), index=df.index)

    df.to_csv(settings.PROCESSED_CSV, index=False, header=True)


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
        if get_all:
            print("Fetching all files")
        else:
            print("Fetching only new files")
        get_individual_plans(get_all)
