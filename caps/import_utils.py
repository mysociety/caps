from os.path import join

import requests
import urllib3

import pandas as pd

from django.conf import settings

import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


AUTHORITY_MAPPING_URL = "https://raw.githubusercontent.com/mysociety/uk_local_authority_names_and_codes/main/data/lookup_name_to_registry.csv"
AUTHORITY_MAPPING_NAME = "lookup_name_to_registry.csv"
AUTHORITY_MAPPING = join(settings.DATA_DIR, AUTHORITY_MAPPING_NAME)

AUTHORITY_DATA_URL = "https://raw.githubusercontent.com/mysociety/uk_local_authority_names_and_codes/main/data/uk_local_authorities.csv"
AUTHORITY_DATA_NAME = "uk_local_authorities.csv"
AUTHORITY_DATA = join(settings.DATA_DIR, AUTHORITY_DATA_NAME)


def get_google_sheet_as_csv(key, outfile, sheet_name=None):
    sheet_url = f"https://docs.google.com/spreadsheets/d/{key}/gviz/tq?tqx=out:csv"
    if sheet_name is not None:
        sheet_url = f"{sheet_url}&sheet={sheet_name}"
    r = requests.get(sheet_url)

    with open(outfile, "wb") as outfile:
        outfile.write(r.content)


def replace_csv_headers(csv_file, new_headers, drop_empty_columns=True, outfile=None):
    if outfile is None:
        outfile = csv_file

    df = pd.read_csv(csv_file)
    if drop_empty_columns:
        df = df.dropna(axis="columns", how="all")

    df.columns = new_headers
    df.to_csv(open(outfile, "w"), index=False, header=True)


def get_data_files():

    data_files = [
        (AUTHORITY_MAPPING_URL, AUTHORITY_MAPPING),
        (AUTHORITY_DATA_URL, AUTHORITY_DATA),
    ]

    for (source, destination) in data_files:
        r = requests.get(source)
        with open(destination, "wb") as outfile:
            outfile.write(r.content)


def add_authority_codes(filename):
    mapping_df = pd.read_csv(AUTHORITY_MAPPING)

    plans_df = pd.read_csv(filename)

    rows = len(plans_df["council"])

    plans_df["authority_code"] = pd.Series([None] * rows, index=plans_df.index)

    names_to_codes = {}
    for index, row in mapping_df.iterrows():
        names_to_codes[row["la-name"].lower()] = row["local-authority-code"]

    for index, row in plans_df.iterrows():
        council = row["council"].lower()

        name_versions = [
            council,
            council.replace("council", "").strip(),
            council.replace("- unitary", "").replace("(unitary)", "").strip(),
        ]
        for version in name_versions:
            if version in names_to_codes:
                plans_df.at[index, "authority_code"] = names_to_codes[version]
                break
    plans_df.to_csv(open(filename, "w"), index=False, header=True)


def add_gss_codes(filename):

    authority_df = pd.read_csv(AUTHORITY_DATA)
    plans_df = pd.read_csv(filename)

    rows = len(plans_df["council"])
    plans_df["gss_code"] = pd.Series([None] * rows, index=plans_df.index)

    for index, row in plans_df.iterrows():
        authority_code = row["authority_code"]
        if not pd.isnull(authority_code):
            authority_match = authority_df[
                authority_df["local-authority-code"] == authority_code
            ]
            plans_df.at[index, "gss_code"] = authority_match["gss-code"].values[0]

    plans_df.to_csv(open(filename, "w"), index=False, header=True)


def add_extra_authority_info(filename):

    authority_df = pd.read_csv(AUTHORITY_DATA)
    plans_df = pd.read_csv(filename)

    df = authority_df[
        [
            "local-authority-code",
            "local-authority-type",
            "wdtk-id",
            "mapit-area-code",
            "nation",
            "gss-code",
            "county-la",
            "region",
            "pop-2020",
        ]
    ]

    df = df.rename(
        columns={
            "local-authority-code": "authority_code",
            "local-authority-type": "authority_type",
            "wdtk-id": "wdtk_id",
            "mapit-area-code": "mapit_area_code",
            "nation": "country",
            "gss-code": "gss_code",
            "region": "region",
            "county-la": "county",
            "pop-2020": "population",
        }
    )

    # the info sheet may contain updated version of columns previously
    # loaded to sheet, need to drop them before the merge
    # ignore errors in case columns are not present
    columns_to_drop = [x for x in df.columns if x != "authority_code"]
    plans_df = plans_df.drop(columns=columns_to_drop, errors="ignore")

    # merge two dataframes using the authority_code as the common reference
    df = plans_df.merge(df, on="authority_code", how="left")

    is_non_english = df["country"].isin(["Wales", "Scotland", "Northern Ireland"])
    df.loc[is_non_english, "authority_type"] = "UA"

    df.to_csv(filename, index=False, header=True)
