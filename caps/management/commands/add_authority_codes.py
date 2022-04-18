from os.path import join, basename, splitext, isfile

import requests

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


from caps.import_utils import (
    get_data_files,
    add_extra_authority_info,
    add_authority_codes,
)


def check_missing_authorities():
    plans_df = pd.read_csv(settings.PROCESSED_CSV)

    mask = plans_df["authority_code"].isnull()
    missing_councils = plans_df["council"][mask].tolist()

    print(f"Councils without authority codes {len(missing_councils)}")
    if len(missing_councils):
        print(missing_councils)


class Command(BaseCommand):
    help = "Adds authority codes to the csv of plans"

    def handle(self, *args, **options):
        print("getting data files")
        get_data_files()
        print("adding authority codes")
        add_authority_codes(settings.PROCESSED_CSV)
        print("adding authority info")
        add_extra_authority_info(settings.PROCESSED_CSV)
        print("check for missing authorities")
        check_missing_authorities()
