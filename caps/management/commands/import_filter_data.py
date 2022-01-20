import os
import pandas as pd

import requests
import urllib3

import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from os.path import join

from scoring.models import PlanScore
from caps.models import PlanDocument

FILTER_DATA_URL = "https://raw.githubusercontent.com/mysociety/climate_league_filter_datasets/main/data/outputs/all_filters.csv"
FILTER_CSV = join(settings.DATA_DIR, "all_filters.csv")

YEAR = settings.PLAN_YEAR


def get_data():
    token = os.environ.get("PERSONAL_ACCESS_TOKEN", None)
    headers = {"Authorization": "token " + token}
    r = requests.get(FILTER_DATA_URL, headers=headers)
    with open(FILTER_CSV, "wb") as outfile:
        outfile.write(r.content)


def import_filters():
    ruc_lookup = dict((desc, code) for code, desc in PlanScore.RUC_TYPES)

    updates = []
    df = pd.read_csv(FILTER_CSV)
    df["council-quintile"] = df["council-quintile"].fillna(0).astype(int)
    df["pop_bucket"] = df["pop_bucket"].fillna("")
    df["political_control"] = df["political_control"].fillna("")

    for index, row in df.iterrows():
        try:
            plan_score = PlanScore.objects.get(
                year=YEAR, council__authority_code=row["local-authority-code"]
            )
        except PlanScore.DoesNotExist:
            print(
                "could not find plan score for council {}".format(
                    row["local-authority-code"]
                )
            )
            continue

        try:
            cluster = ruc_lookup[row["ruc_cluster"]]
        except KeyError:
            cluster = ""

        plan_score.population = row["pop_bucket"]
        plan_score.deprivation_quintile = row["council-quintile"]
        plan_score.political_control = row["political_control"]
        plan_score.ruc_cluster = cluster
        updates.append(plan_score)

    PlanScore.objects.bulk_update(
        updates,
        ["population", "deprivation_quintile", "political_control", "ruc_cluster"],
    )


class Command(BaseCommand):
    help = "fetch council filter data"

    def handle(self, *args, **options):
        print("getting the filter csv")
        get_data()
        print("importing the filters")
        import_filters()
