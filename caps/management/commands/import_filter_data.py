import os
from os.path import join

import pandas as pd
from django.conf import settings

from caps.import_utils import BaseImportCommand
from caps.models import PlanDocument
from scoring.models import PlanScore

FILTER_JSON = join(settings.DATA_DIR, "league_filters.json")

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
BLUE = "\033[36;4m"
NOBOLD = "\033[0m"


class Command(BaseImportCommand):
    help = "fetch council filter data"

    YEAR = settings.PLAN_YEAR

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            action="store",
            help=f"Override default year ({self.YEAR}) to import plans from",
        )

        parser.add_argument(
            "--commit",
            action="store_true",
            help="Make changes to database",
        )

    def get_data(self):
        return pd.read_json(FILTER_JSON, orient="records")

    def import_filters(self):
        ruc_lookup = dict((desc, code) for code, desc in PlanScore.RUC_TYPES)

        updates = []
        df = self.get_data()
        df["council-quintile"] = df["council-quintile"].fillna(0).astype(int)
        df["pop_bucket"] = df["pop_bucket"].fillna("")

        for index, row in df.iterrows():
            try:
                plan_score = PlanScore.objects.get(
                    year=self.YEAR, council__authority_code=row["local-authority-code"]
                )
            except PlanScore.DoesNotExist:
                self.stdout.write(
                    f"{RED}could not find plan score for council {row['local-authority-code']}{NOBOLD}"
                )
                continue

            try:
                cluster = ruc_lookup[row["ruc_cluster"]]
            except KeyError:
                cluster = ""

            plan_score.population = row["pop_bucket"]
            plan_score.deprivation_quintile = row["council-quintile"]
            plan_score.ruc_cluster = cluster
            updates.append(plan_score)

        PlanScore.objects.bulk_update(
            updates,
            ["population", "deprivation_quintile", "ruc_cluster"],
        )

    def handle(self, *args, year: int = None, commit: bool = False, **options):
        print("importing the filters")
        if year:
            self.YEAR = year

        self.stdout.write(f"Updating filter values for {BLUE}{self.YEAR}{NOBOLD}")

        if not commit:
            self.stdout.write(
                f"{YELLOW}Not updating database, call with --commit to do so{NOBOLD}"
            )

        with self.get_atomic_context(commit):
            self.import_filters()
