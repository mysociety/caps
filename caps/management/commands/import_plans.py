import math
from datetime import date
from os.path import join

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from django.template.defaultfilters import pluralize

from caps.models import Council, PlanDocument
from caps.utils import (
    boolean_from_text,
    char_from_text,
    date_from_text,
    integer_from_text,
)


class Command(BaseCommand):
    help = "Imports data from data/plans into the database"

    changes = False
    plans_to_delete = (
        {}
    )  # per council list of plan urls that are no longer in the sheet
    councils_in_sheet = set()  # set of gss codes of councils in sheet
    councils_with_plan_in_sheet = (
        set()
    )  # set of gss codes of councils with at least one plan
    plans_to_process = {}
    start_council_plan_count = 0
    end_council_plan_count = 0
    start_plan_count = 0
    end_plan_count = 0

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm_changes", action="store_true", help="make updates to database"
        )

    def handle(self, *args, **options):
        self.verbosity = options.get("verbosity")

        self.get_changes()
        if options["confirm_changes"] == True:
            self.update_database()
            self.print_summary()
        elif self.changes == True:
            self.print_change("call with --confirm_changes to update database")

    def get_changes(self):
        self.plans_to_process = {}
        df = pd.read_csv(settings.PROCESSED_CSV)
        council_add_count = 0
        plan_add_count = 0
        plan_update_count = 0
        plans_to_import = {}
        councils_in_sheet = set()
        councils_with_plan_in_sheet = set()

        self.start_council_plan_count = (
            Council.objects.annotate(num_plans=Count("plandocument"))
            .filter(
                Q(plandocument__document_type=PlanDocument.ACTION_PLAN)
                | Q(plandocument__document_type=PlanDocument.CLIMATE_STRATEGY),
                num_plans__gt=0,
            )
            .count()
        )
        self.start_document_count = PlanDocument.objects.count()
        self.start_plan_count = PlanDocument.objects.filter(
            Q(document_type=PlanDocument.ACTION_PLAN)
            | Q(document_type=PlanDocument.CLIMATE_STRATEGY)
        ).count()

        for index, row in df.iterrows():
            gss_code = char_from_text(row["gss_code"])
            councils_in_sheet.update([gss_code])

            council_exists = Council.objects.filter(gss_code=gss_code).exists()

            if not council_exists:
                council_add_count += 1
                self.print_change("adding new council: %s", row["council"], verbosity=2)
                if not pd.isnull(row["url"]):
                    self.plans_to_process[index] = "new_council"
                    councils_with_plan_in_sheet.update([gss_code])
                    plan_add_count += 1
                    self.print_change(
                        "adding new plan for %s", row["council"], verbosity=2
                    )
            elif not pd.isnull(row["url"]):
                councils_with_plan_in_sheet.update([gss_code])
                council = Council.objects.get(gss_code=gss_code)
                plan_exists = PlanDocument.objects.filter(
                    council=council, url=row["url"]
                ).exists()

                council_plans = plans_to_import.get(gss_code, set())
                council_plans.update([row["url"]])
                plans_to_import[gss_code] = council_plans
                if not plan_exists:
                    self.plans_to_process[index] = "add"
                    plan_add_count += 1
                    self.print_change(
                        "adding new plan for %s", row["council"], verbosity=2
                    )
                else:
                    plan = PlanDocument.objects.get(council=council, url=row["url"])
                    diffs = 0
                    diff_keys = []
                    for key, value in self.get_plan_defaults_from_row(row).items():
                        if getattr(plan, key) != value:
                            diffs = 1
                            diff_keys.append(key)

                    if diffs != 0:
                        self.plans_to_process[index] = "update"
                        plan_update_count += 1
                        self.print_change(
                            "updating plan for %s (%s changed)",
                            row["council"],
                            ", ".join(diff_keys),
                            verbosity=2,
                        )

        plans_to_delete = {}
        plans_to_delete_count = 0
        for council_code in plans_to_import.keys():
            council = Council.objects.get(gss_code=council_code)
            plans = (
                PlanDocument.objects.filter(
                    council=council,
                )
                .exclude(
                    url__in=plans_to_import[council_code],
                )
                .exclude(
                    document_type=PlanDocument.CITIZENS_ASSEMBLY,
                )
            )
            for plan in plans:
                plans_to_delete_count += 1
                council_plans = plans_to_delete.get(council_code, set())
                council_plans.update([plan.url])
                self.print_change(
                    "deleting plan for %s - %s (%s)",
                    council.name,
                    plan.title,
                    plan.document_type,
                    verbosity=2,
                )
                plans_to_delete[council_code] = council_plans

        # if a council isn't in the sheet we should remove it entirely from the database
        councils_to_remove = Council.objects.exclude(gss_code__in=councils_in_sheet)
        councils_to_remove_count = councils_to_remove.count()

        # if a council is going to be removed completely then exclude it from the
        # list of councils where we're going to remove the plans
        councils_with_plans_to_remove = set(
            [council.gss_code for council in councils_to_remove]
        )
        if councils_with_plans_to_remove:
            councils_with_plan_in_sheet.update(councils_with_plans_to_remove)

        # if a council is in the sheet but no longer has a plan we should remove all
        # their plans
        plans_from_removed_councils = PlanDocument.objects.exclude(
            council__gss_code__in=councils_with_plan_in_sheet
        )
        plans_from_removed_councils_count = plans_from_removed_councils.count()

        if self.verbosity >= 2:
            councils = councils_to_remove.all()
            for council in councils:
                self.print_change("%s will be completely removed" % council.name)

            councils = plans_from_removed_councils.distinct("council__gss_code")
            for council in councils:
                self.print_change(
                    "%s will have all plans removed" % council.council.name
                )

        self.plans_to_delete = plans_to_delete
        self.councils_in_sheet = councils_in_sheet
        self.councils_with_plan_in_sheet = councils_with_plan_in_sheet

        if council_add_count > 0:
            self.print_change(
                "%d council%s will be added",
                council_add_count,
                pluralize(council_add_count),
            )
        if plan_add_count > 0:
            self.print_change(
                "%d plan%s will be added", plan_add_count, pluralize(plan_add_count)
            )
        if plan_update_count > 0:
            self.print_change(
                "%d plan%s will be updated",
                plan_update_count,
                pluralize(plan_update_count),
            )
        if plans_to_delete_count > 0:
            self.print_change(
                "%d plan%s will be deleted",
                plans_to_delete_count,
                pluralize(plans_to_delete_count),
            )
        if plans_from_removed_councils_count > 0:
            self.print_change(
                "%d council%s will have all plans removed",
                plans_from_removed_councils_count,
                pluralize(plans_from_removed_councils_count),
            )

    def update_database(self):
        df = pd.read_csv(settings.PROCESSED_CSV)

        df["start-date"] = (
            pd.to_datetime(df["start-date"])
            .dt.date.fillna(np.nan)
            .replace([np.nan], [None])
        )
        df["end-date"] = (
            pd.to_datetime(df["end-date"])
            .dt.date.fillna(np.nan)
            .replace([np.nan], [None])
        )

        # where gss-code is blank, use the authority code
        df["gss_code"] = df["gss_code"].fillna("temp" + df["authority_code"])
        for index, row in df.iterrows():
            council_url = char_from_text(row["website_url"])
            twitter_url = char_from_text(row["twitter_url"])
            twitter_name = char_from_text(row["twitter_name"])
            region = char_from_text(row["region"])
            county = char_from_text(row["county"])
            population = integer_from_text(row["population"]) or 0
            council, created = Council.objects.get_or_create(
                authority_code=char_from_text(row["authority_code"]),
                country=Council.country_code(row["country"]),
                defaults={
                    "authority_type": char_from_text(row["authority_type"]),
                    "name": row["council"],
                    "slug": PlanDocument.council_slug(row["council"]),
                    "gss_code": char_from_text(row["gss_code"]),
                    "whatdotheyknow_id": integer_from_text(row["wdtk_id"]),
                    "mapit_area_code": char_from_text(row["mapit_area_code"]),
                    "website_url": council_url,
                    "twitter_url": twitter_url,
                    "twitter_name": twitter_name,
                    "county": county,
                    "region": region,
                    "population": population,
                    "start_date": row["start-date"],
                    "end_date": row["end-date"],
                    "replaced_by": char_from_text(row["replaced-by"]),
                },
            )

            # check the council things that might change
            changed = False

            if char_from_text(row["authority_type"]) != council.authority_type:
                council.authority_type = char_from_text(row["authority_type"])
                changed = True

            if char_from_text(row["replaced-by"]) != council.replaced_by:
                council.replaced_by = char_from_text(row["replaced-by"])
                changed = True

            if row["start-date"] != council.start_date:
                council.start_date = row["start-date"]
                changed = True

            if row["end-date"] != council.start_date:
                council.end_date = row["end-date"]
                changed = True

            if row["council"] != council.name:
                council.name = row["council"]
                council.slug = PlanDocument.council_slug(row["council"])
                changed = True

            if char_from_text(row["gss_code"]) != council.gss_code:
                council.gss_code = char_from_text(row["gss_code"])
                changed = True

            if council_url != "" and council.website_url != council_url:
                council.website_url = council_url
                changed = True

            if (
                council.twitter_name != ""
                or council.twitter_name != twitter_name
                or council.twitter_url != twitter_url
            ):
                council.twitter_url = twitter_url
                council.twitter_name = twitter_name
                changed = True

            if council.region != region:
                council.region = region
                changed = True

            if council.county != county:
                council.county = county
                changed = True

            if council.population != population:
                council.population = population
                changed = True

            if changed is True:
                council.save()

            if not pd.isnull(row["url"]) and index in self.plans_to_process:
                document_file = open(row["plan_path"], "rb")
                file_object = File(document_file)
                defaults = {"file": file_object}
                defaults.update(self.get_plan_defaults_from_row(row))

                plan_document, created = PlanDocument.objects.update_or_create(
                    url=row["url"],
                    url_hash=PlanDocument.make_url_hash(row["url"]),
                    council=council,
                    defaults=defaults,
                )
                if created:
                    plan_document.date_first_found = date_from_text(
                        row["date_retrieved"]
                    )
                    plan_document.save()

        PlanDocument.objects.exclude(
            council__gss_code__in=self.councils_with_plan_in_sheet
        ).delete()

        for council_code in self.plans_to_delete.keys():
            council = Council.objects.get(gss_code=council_code)
            plans = PlanDocument.objects.filter(
                council=council, url__in=self.plans_to_delete[council_code]
            ).delete()

        # Delete all plans if the council has been removed from the sheet
        # But do not delete the council itself (councils without plans are fine)
        PlanDocument.objects.exclude(
            council__gss_code__in=self.councils_in_sheet
        ).delete()

        self.end_council_plan_count = (
            Council.objects.annotate(num_plans=Count("plandocument"))
            .filter(
                Q(plandocument__document_type=PlanDocument.ACTION_PLAN)
                | Q(plandocument__document_type=PlanDocument.CLIMATE_STRATEGY),
                num_plans__gt=0,
            )
            .count()
        )
        self.end_document_count = PlanDocument.objects.count()
        self.end_plan_count = PlanDocument.objects.filter(
            Q(document_type=PlanDocument.ACTION_PLAN)
            | Q(document_type=PlanDocument.CLIMATE_STRATEGY)
        ).count()

    def get_plan_defaults_from_row(self, row):
        (start_year, end_year) = PlanDocument.start_and_end_year_from_time_period(
            row["time_period"]
        )
        defaults = {
            "document_type": PlanDocument.document_type_code(row["type"]),
            "scope": PlanDocument.scope_code(row["scope"]),
            "status": PlanDocument.status_code(row["status"]),
            "well_presented": boolean_from_text(row["well_presented"]),
            "baseline_analysis": boolean_from_text(row["baseline_analysis"]),
            "notes": char_from_text(row["notes"]),
            "file_type": char_from_text(row["file_type"]),
            "charset": char_from_text(row["charset"]),
            "start_year": start_year,
            "end_year": end_year,
            "date_last_found": date_from_text(row["date_retrieved"]),
            "title": char_from_text(row["title"]),
        }

        return defaults

    def print_change(self, text, *args, **kwargs):
        self.changes = True
        verbosity = kwargs.get("verbosity", 1)
        if self.verbosity >= verbosity:
            self.stdout.write(text % args)

    def print_summary(self):
        if self.start_council_plan_count == self.end_council_plan_count:
            self.print_change(
                "Councils with a plan is unchanged at %d", self.end_council_plan_count
            )
        else:
            self.print_change(
                "Councils with a plan went from %d to %d",
                self.start_council_plan_count,
                self.end_council_plan_count,
            )

        if self.start_document_count == self.end_document_count:
            self.print_change(
                "Number of documents is unchanged at %d", self.end_document_count
            )
        else:
            self.print_change(
                "Number of documents went from %d to %d",
                self.start_document_count,
                self.end_document_count,
            )

        if self.start_plan_count == self.end_plan_count:
            self.print_change("Number of plans is unchanged at %d", self.end_plan_count)
        else:
            self.print_change(
                "Number of plans went from %d to %d",
                self.start_plan_count,
                self.end_plan_count,
            )
