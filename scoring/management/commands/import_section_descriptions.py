from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from scoring.models import PlanSection


class Command(BaseCommand):
    help = "Imports section descriptions"

    YEAR = 2023  # settings.PLAN_YEAR
    SCORECARD_DATA_DIR = Path(settings.DATA_DIR, "scorecard_data", str(YEAR))
    SECTION_DESC_CSV = Path(SCORECARD_DATA_DIR, "section_descriptions.csv")

    def add_section_long_description(self):
        df = pd.read_csv(self.SECTION_DESC_CSV)
        for _, row in df.iterrows():
            section_code = row["code"]
            section_desc = row["description"]

            try:
                section = PlanSection.objects.get(code=section_code, year=self.YEAR)
                section.long_description = section_desc
                section.save()
            except PlanSection.DoesNotExist:
                self.stderr.write(f"no section found with code {row['code']}")

    def handle(self, *args, **options):
        self.add_section_long_description()
