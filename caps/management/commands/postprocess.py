from os.path import join, basename, splitext, isfile
from shutil import copy
import os
import sys

import pandas as pd
import numpy

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from caps.models import PlanDocument


def remove_internal_data():
    out_csv = join(settings.MEDIA_ROOT, "data", settings.PROCESSED_CSV_NAME)
    df = pd.read_csv(settings.PROCESSED_CSV)
    df = df.drop(
        columns=["text", "unfound", "charset", "wdtk_id", "mapit_area_code", "credit"]
    )

    df.to_csv(open(out_csv, "w"), index=False, header=True)

    out_csv = join(settings.MEDIA_ROOT, "data", settings.DECLARATIONS_CSV_NAME)
    df = pd.read_csv(settings.DECLARATIONS_CSV)
    df = df.drop(
        columns=[
            "control_at_declaration",
            "control_now",
            "leader",
            "proposer",
        ]
    )

    df.to_csv(open(out_csv, "w"), index=False, header=True)


def add_last_update():
    out_csv = join(settings.MEDIA_ROOT, "data", settings.PROCESSED_CSV_NAME)
    df = pd.read_csv(out_csv)

    rows = len(df["council"])
    df["last_update"] = pd.Series([None] * rows, index=df.index)

    for index, row in df.iterrows():
        if not pd.isnull(row["url"]):
            plan = PlanDocument.objects.get(
                url=row["url"], council__gss_code=row["gss_code"]
            )
            df.loc[index, "last_update"] = plan.updated_at.isoformat()

    df.to_csv(open(out_csv, "w"), index=False, header=True)


def copy_files_to_media():
    files = [settings.PROMISES_CSV]

    for file in files:
        file_name = basename(file)
        dst = join(settings.MEDIA_ROOT, "data", file_name)
        copy(file, dst)


class Command(BaseCommand):
    help = "Post processes plans csv data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Update all data (slower but more thorough)",
        )

    def handle(self, *args, **options):
        print("removing internal data")
        remove_internal_data()
        print("add last update to csv file")
        add_last_update()
        print("copy files to media directory")
        copy_files_to_media()
