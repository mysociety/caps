from datetime import date

from django.core.management.base import BaseCommand

from scoring.models import PlanYear


class Command(BaseCommand):
    help = "Initial populate of plan years"

    plan_years = {
        2023: {
            "new": {
                "year": 2023,
                "month": 1,
                "day": 1,
            },
            "old": {
                "year": 2021,
                "month": 4,
                "day": 1,
            },
            "is_current": False,
        },
        2025: {
            "previous_year": 2023,
            "new": {
                "year": 2024,
                "month": 4,
                "day": 1,
            },
            "old": {
                "year": 2023,
                "month": 1,
                "day": 1,
            },
            "is_current": True,
        },
    }

    def handle(self, *args, **options):
        if PlanYear.objects.exists():
            self.stderr.write("Existing plans, not doing anything")
            return

        for year, conf in self.plan_years.items():
            new_council_date = date(
                year=conf["new"]["year"],
                month=conf["new"]["month"],
                day=conf["new"]["day"],
            )
            old_council_date = date(
                year=conf["old"]["year"],
                month=conf["old"]["month"],
                day=conf["old"]["day"],
            )

            if not PlanYear.objects.filter(year=year).exists():
                y = PlanYear.objects.create(
                    year=year,
                    new_council_date=new_council_date,
                    old_council_date=old_council_date,
                    is_current=conf["is_current"],
                )

                if conf.get("previous_year"):
                    py = PlanYear.objects.get(year=conf["previous_year"])
                    y.previous_year = py
                    y.save()

        self.stdout.write("Default plans added")
