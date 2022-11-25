import re
from os.path import join

import pandas as pd

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

from cape.models import Council, CouncilProject


class Command(BaseCommand):
    help = "processing scottish council climate data"

    def handle(self, *args, **options):
        self.options = options

        self.import_projects()

    @transaction.atomic
    def import_projects(self):
        # remove everything as there's no unique id
        CouncilProject.objects.all().delete()

        data = join(settings.SCOTTISH_DIR, "projects_data.csv")
        df = pd.read_csv(data)

        for col in [
            "emission_savings",
            "cost",
            "annual_cost",
            "annual_savings",
            "lifetime",
        ]:
            # remove cruft
            df[col] = df[col].str.replace(",", "", regex=False)
            df[col] = df[col].str.replace("£", "", regex=False)
            df[col] = df[col].str.replace(" ", "", regex=False)
            df[col] = df[col].str.replace("'xa0", "", regex=False)
            df[col] = df[col].fillna(0)

        for col in ["funding_source", "emission_source", "comments", "savings_start"]:
            df[col] = df[col].fillna("")

        for index, row in df.iterrows():
            try:
                council = Council.objects.get(authority_code=row["authority_code"])
            except Council.DoesNotExist as e:
                print(
                    "could not find council matching {}".format(row["authority_code"])
                )

            try:
                start_year = 0
                match = re.match(r"^(?P<start_year>\d+)\D", row["savings_start"])
                if match:
                    start_year = int(match.group("start_year"))

                annual_savings = row["annual_savings"]
                if (
                    type(annual_savings) == str
                    and re.search(r"k", annual_savings, re.I) is not None
                ):
                    annual_savings = re.sub(r"[kK]", "", annual_savings)
                    annual_savings = float(annual_savings) * 1000

                project = CouncilProject.objects.get_or_create(
                    council=council,
                    name=row["project_name"],
                    year=row["start_year"],
                    emission_savings=row["emission_savings"],
                    funding=row["funding_source"],
                    emission_source=row["emission_source"],
                    capital_cost=row["cost"],
                    annual_cost=row["annual_cost"],
                    annual_savings=annual_savings,
                    lifespan=row["lifetime"],
                    measurement_type=row["measurement"],
                    comments=row["comments"],
                    start_year=start_year,
                )
            except Exception as e:
                print(e)
