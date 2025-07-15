import ssl
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from os.path import join
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
import requests
import urllib3
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.transaction import atomic
from mysoc_dataset import get_dataset_url

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PathLike = Union[str, Path]

as_of_date = settings.COUNCILS_AS_OF_DATE


# from https://adamj.eu/tech/2022/10/13/dry-run-mode-for-data-imports-in-django/
class DoRollback(Exception):
    pass


@contextmanager
def rollback_atomic() -> Generator[None, None, None]:
    try:
        with atomic():
            yield
            raise DoRollback()
    except DoRollback:
        pass


@lru_cache
def get_authority_mapping() -> pd.DataFrame:
    """
    Return a dataframe mapping different names to authority code
    """
    url = get_dataset_url(
        repo_name="uk_local_authority_names_and_codes",
        package_name="uk_la_future",
        version_name="1",
        file_name="lookup_name_to_registry.csv",
        done_survey=True,
    )
    return pd.read_csv(url)


def get_date_from_from_string(dates: pd.Series) -> pd.Series:
    """
    convert a series of dates in the format YYYY-MM-DD to a series of
    dates
    """
    return pd.to_datetime(dates).dt.date


@lru_cache
def get_council_df():
    """
    Return a dataframe of councils that are live or historical as of a given date
    """
    url = get_dataset_url(
        repo_name="uk_local_authority_names_and_codes",
        package_name="uk_la_future",
        version_name="1",
        file_name="uk_local_authorities_future.csv",
        done_survey=True,
    )
    df = pd.read_csv(url)

    # remove any with a start date after as_of_date
    df = df.loc[
        (get_date_from_from_string(df["start-date"]) < as_of_date)  # type: ignore
        | df["start-date"].isna()
    ]
    # blank out any replaced-by and end dates after as_of_date
    df.loc[
        get_date_from_from_string(df["end-date"]) >= as_of_date, "replaced-by"  # type: ignore
    ] = np.nan
    df.loc[
        get_date_from_from_string(df["end-date"]) >= as_of_date, "end-date"  # type: ignore
    ] = np.nan
    df["current-authority"] = df["end-date"].isna() & (
        df["start-date"].isna()
        | (get_date_from_from_string(df["start-date"]) < as_of_date)  # type: ignore
        # set the current-authority correctly
    )
    # needs future plannning
    return pd.read_csv(url)


def get_google_sheet_as_csv(
    key: str, outfile: PathLike, sheet_name: Optional[str] = None
):
    """
    Fetch a google sheet csv and output it to a file
    """
    sheet_url = f"https://docs.google.com/spreadsheets/d/{key}/gviz/tq?tqx=out:csv"
    if sheet_name is not None:
        sheet_url = f"{sheet_url}&sheet={sheet_name}"
    r = requests.get(sheet_url)

    with open(outfile, "wb") as outfile:
        outfile.write(r.content)


def replace_csv_headers(
    csv_file: PathLike,
    new_headers: list[str],
    drop_empty_columns: bool = True,
    outfile: Optional[PathLike] = None,
):
    """
    Downloading a google sheet csv will sometimes mess up the headers - needs manual fix
    """
    if outfile is None:
        outfile = csv_file

    df = pd.read_csv(csv_file)
    if drop_empty_columns:
        df = df.dropna(axis="columns", how="all")

    df.columns = new_headers
    df.to_csv(open(outfile, "w"), index=False, header=True)


def add_authority_codes(filename: PathLike):
    """
    Given a csv file with a column called "council", add a column called "authority_code"
    """
    mapping_df = get_authority_mapping()

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


def add_gss_codes(filename: PathLike):
    """
    Given a csv file with a column called "authority_code", add a column called "gss_code"
    """
    authority_df = get_council_df()
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


def add_extra_authority_info(filename: PathLike):
    """
    Import extra authority info from the uk_local_authority_names_and_codes repo
    """

    authority_df = get_council_df()
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
            "start-date",
            "end-date",
            "replaced-by",
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

    is_non_english = df["country"].isin(["Wales", "Scotland"])
    df.loc[is_non_english, "authority_type"] = "UA"

    df.to_csv(filename, index=False, header=True)


class BaseImportCommand(BaseCommand):
    def get_atomic_context(self, commit):
        if commit:
            atomic_context = atomic()
        else:
            atomic_context = rollback_atomic()

        return atomic_context
