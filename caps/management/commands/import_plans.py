# -*- coding: future_fstrings -*-
from os.path import join
from datetime import date
import math

import pandas as pd

from caps.models import Council, PlanDocument

from django.core.management.base import BaseCommand, CommandError
from django.core.files import File

from django.conf import settings

class Command(BaseCommand):
    help = 'Imports data from data/plans into the database'

    changes = False

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm_changes',
            action='store_true',
            help='make updates to database'
        )

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity')

        self.get_changes()
        if options['confirm_changes'] == True:
            self.update_database()
        elif self.changes == True:
            self.print_change("call with --confirm_changes to update database")

    def get_changes(self):
        df = pd.read_csv(settings.PROCESSED_CSV)
        council_add_count = 0
        plan_add_count = 0
        plan_update_count = 0
        for index, row in df.iterrows():
            council_exists = Council.objects.filter(
                gss_code = PlanDocument.char_from_text(row['gss_code'])
            ).exists()

            if not council_exists:
                council_add_count += 1
                self.print_change("adding new council: %s", row['council'], verbosity=2)
                if not pd.isnull(row['url']):
                    plan_add_count += 1
                    self.print_change("adding new plan for %s", row['council'], verbosity=2)
            elif not pd.isnull(row['url']):
                council = Council.objects.get(
                    gss_code = PlanDocument.char_from_text(row['gss_code'])
                )
                plan_exists = PlanDocument.objects.filter(
                    council=council,
                    url=row['url']
                ).exists()

                if not plan_exists:
                    plan_add_count += 1
                    self.print_change("adding new plan for %s", row['council'], verbosity=2)
                else:
                    plan = PlanDocument.objects.get(
                        council=council,
                        url=row['url']
                    )
                    diffs = 0
                    for key, value in self.get_plan_defaults_from_row(row).items():
                        if getattr(plan, key) != value:
                            diffs = 1

                    if diffs != 0:
                        plan_update_count += 1
                        self.print_change("updating plan for %s", row['council'], verbosity=2)

        if council_add_count > 0:
            self.print_change("%d councils will be added", council_add_count)
        if plan_add_count > 0:
            self.print_change("%d plans will be added", plan_add_count)
        if plan_update_count > 0:
            self.print_change("%d plans will be updated", plan_update_count)


    def update_database(self):
        df = pd.read_csv(settings.PROCESSED_CSV)
        for index, row in df.iterrows():
            council, created = Council.objects.get_or_create(
                name = row['council'],
                slug = PlanDocument.council_slug(row['council']),
                authority_code = PlanDocument.char_from_text(row['authority_code']),
                authority_type = PlanDocument.char_from_text(row['authority_type']),
                gss_code = PlanDocument.char_from_text(row['gss_code']),
                country = Council.country_code(row['country']),
                defaults = {
                            'whatdotheyknow_id': PlanDocument.integer_from_text(row['wdtk_id']),
                            'mapit_area_code': PlanDocument.char_from_text(row['mapit_area_code']),
                            'website_url': PlanDocument.char_from_text(row['website_url'])
                }
            )

            if not pd.isnull(row['url']):
                document_file = open(row['plan_path'], "rb")
                file_object = File(document_file)
                defaults = {
                            'date_last_found': date.today(),
                            'file': file_object
                            }
                defaults.update(self.get_plan_defaults_from_row(row))

                plan_document = PlanDocument.objects.update_or_create(
                    url=row['url'],
                    url_hash=PlanDocument.make_url_hash(row['url']),
                    council = council,
                    defaults = defaults
                )

    def get_plan_defaults_from_row(self, row):
        (start_year, end_year) = PlanDocument.start_and_end_year_from_time_period(row['time_period'])
        defaults = {
                    'document_type': PlanDocument.document_type_code(row['type']),
                    'scope': PlanDocument.scope_code(row['scope']),
                    'status': PlanDocument.status_code(row['status']),
                    'well_presented': PlanDocument.boolean_from_text(row['well_presented']),
                    'baseline_analysis': PlanDocument.boolean_from_text(row['baseline_analysis']),
                    'notes': PlanDocument.char_from_text(row['notes']),
                    'file_type': PlanDocument.char_from_text(row['file_type']),
                    'charset': PlanDocument.char_from_text(row['charset']),
                    'text': PlanDocument.char_from_text(row['text']),
                    'start_year': start_year,
                    'end_year': end_year,
                    'date_first_found': PlanDocument.date_from_text(row['date_retrieved']),
                    }
        return defaults;

    def print_change(self, text, *args, **kwargs):
        self.changes = True
        verbosity = kwargs.get('verbosity', 1)
        if self.verbosity >= verbosity:
            self.stdout.write(text % args)
