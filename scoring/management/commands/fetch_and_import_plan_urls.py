import os
import re

import pandas as pd

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

from cape.import_utils import get_google_sheet_as_csv

from scoring.models import PlanScore, PlanScoreDocument


SCORED_PLANS_CSV = os.path.join(settings.DATA_DIR, "scored_plans.csv")


def get_scored_plans():
    get_google_sheet_as_csv(
        settings.SCORED_PLANS_CSV_KEY,
        settings.SCORED_PLANS_CSV,
        settings.SCORED_PLANS_CSV_SHEET_NAME,
    )


@transaction.atomic
def import_scored_plans():
    # refresh everything
    PlanScoreDocument.objects.all().delete()

    df = pd.read_csv(settings.SCORED_PLANS_CSV)
    df["Plans Marked in Audit (Final)"] = df["Plans Marked in Audit (Final)"].fillna("")
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
