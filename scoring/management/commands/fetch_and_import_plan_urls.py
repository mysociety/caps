import os
import re
import requests
import urllib3

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

from caps.import_utils import add_authority_codes, add_gss_codes

from scoring.models import PlanScore, PlanScoreDocument

import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCORED_PLANS_CSV = os.path.join(settings.DATA_DIR, "scored_plans.csv")


def get_scored_plans():
    # Get the google doc as a CSV file
    sheet_url = f"https://docs.google.com/spreadsheets/d/{settings.SCORED_PLANS_CSV_KEY}/gviz/tq?tqx=out:csv&sheet={settings.SCORED_PLANS_CSV_SHEET_NAME}"
    r = requests.get(sheet_url)
    with open(settings.SCORED_PLANS_CSV, "wb") as outfile:
        outfile.write(r.content)


@transaction.atomic
def import_scored_plans():
    # refresh everything
    PlanScoreDocument.objects.all().delete()

    df = pd.read_csv(settings.SCORED_PLANS_CSV)
    df["Plans"] = df["Plans"].fillna("")
    documents = []

    # avoid matching URLs in the middle of other URLs
    pattern = re.compile(r"(?:^http|(?<=\s)http)", re.MULTILINE)
    for index, row in df.iterrows():
        audited = row["Completed - Audited"]
        if audited != "Yes":
            continue
        try:
            plan_score = PlanScore.objects.get(
                council__authority_code=row["code"], year=settings.PLAN_YEAR
            )
        except PlanScore.DoesNotExist:
            print("Could not find plan score for council {}".format(row["code"]))
            continue

        plans = row["Plans Marked in Audit (Final)"]

        # plans is a free text list of URLs so split on http and then
        # reconstitute
        plan_urls = re.split(pattern, plans)
        plan_urls = [("http" + url).strip() for url in plan_urls if url != ""]

        for url in plan_urls:
            document = PlanScoreDocument(plan_score=plan_score, plan_url=url)

            documents.append(document)

    PlanScoreDocument.objects.bulk_create(documents)


class Command(BaseCommand):
    help = "fetch and import urls of scored plans"

    def handle(self, *args, **options):
        print("fetch and import the scored plans data")
        get_scored_plans()
        import_scored_plans()
