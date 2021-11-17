# -*- coding: future_fstrings -*-
from os.path import join
from datetime import date
import math

import pandas as pd

from caps.models import Council, PlanDocument, PlanScore, PlanSection, PlanSectionScore

from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from django.template.defaultfilters import pluralize

from django.conf import settings

class Command(BaseCommand):
    help = 'Imports plan scores'

    YEAR = 2021
    SCORES_CSV = join(settings.DATA_DIR, 'council_plan_scores.csv')

    def import_scores(self):
        df = pd.read_csv(self.SCORES_CSV)
        for index, row in df.iterrows():
            if row['section'] == 'overall':
                continue

            weight = PlanDocument.integer_from_text(row['weighting'])
            max_score = PlanDocument.integer_from_text(row['max_score'])

            section, created = PlanSection.objects.get_or_create(
                code=row['section'].replace('&', '_'),
                year=self.YEAR,
            )
            if (created):
                section.description = row['section_name']
                section.max_score = max_score
                section.max_weighted_score = max_score * weight
                section.weight = weight
                section.save()

            try:
                council = Council.objects.get(authority_code=row['council_id'])
            except Council.DoesNotExist:
                continue

            plan, created = PlanScore.objects.get_or_create(
                council=council,
                year=self.YEAR
            )

            score = 0
            if not pd.isnull(row['value']):
                score = PlanDocument.integer_from_text(row['value'])
                weighted_score = score * weight

            section_score, created = PlanSectionScore.objects.get_or_create(
                plan_section=section,
                plan_score=plan,
            )

            section_score.score = score
            section_score.weighted_score = weighted_score
            section_score.save()

            plan.total = plan.total + section_score.score
            plan.weighted_total = plan.weighted_total + section_score.weighted_score
            plan.save()

    def handle(self, *args, **options):
        self.import_scores()
