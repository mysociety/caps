import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from scoring.models import PlanYear, PlanYearConfig


class Command(BaseCommand):
    help = "Update plan year config"

    SCORECARD_DATA_DIR = Path(settings.DATA_DIR, "scorecard_data")

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            action="store",
            required=True,
            help="Year to add the configs to",
        )

        parser.add_argument(
            "--file",
            action="store",
            required=True,
            help="File containing the config",
        )

        parser.add_argument(
            "--previous_year",
            action="store",
            help="Previous scorecards year, for calculating most improved, and linking",
        )

    def handle(self, file: str = None, year: int = None, *args, **options):

        file_path = Path(self.SCORECARD_DATA_DIR, file)

        try:
            plan_year = PlanYear.objects.get(year=year)
        except PlanYear.DoesNotExist:
            self.stderr.write(f"No such year: {year}")
            return

        with open(file_path, "r") as config_file:
            configs = json.load(config_file)

        for label, config in configs.items():
            PlanYearConfig.objects.update_or_create(
                year=plan_year, name=label, defaults={"value": config}
            )
