# -*- coding: future_fstrings -*-
import re
from os.path import join
from datetime import date
import math

import requests
import pandas as pd

from caps.models import Council, PlanDocument
from scoring.models import PlanScore, PlanSection, PlanSectionScore, PlanQuestion, PlanQuestionScore

from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from django.template.defaultfilters import pluralize

from django.conf import settings

class Command(BaseCommand):
    help = 'Imports plan scores'

    YEAR = settings.PLAN_YEAR
    SECTION_SCORES_CSV = join(settings.DATA_DIR, settings.PLAN_SECTION_SCORES_CSV_NAME)
    QUESTIONS_CSV = join(settings.DATA_DIR, settings.PLAN_SCORE_QUESTIONS_CSV_NAME)
    ANSWERS_CSV = join(settings.DATA_DIR, settings.PLAN_SCORE_ANSWERS_CSV_NAME)

    def get_files(self):
        # other files manually downloaded for now
        sheet_url = f"https://docs.google.com/spreadsheets/d/{settings.PLAN_SCORE_QUESTIONS_CSV_KEY}/export?format=csv&gid={settings.PLAN_SCORE_QUESTIONS_CSV_TAB}"
        r = requests.get(sheet_url)
        with open(self.QUESTIONS_CSV, 'wb') as outfile:
            outfile.write(r.content)


    def normalise_section_code(self, code):
        normalised = code.replace('&', '_')
        return normalised

    def import_section_scores(self):
        council_scores = {}

        df = pd.read_csv(self.SECTION_SCORES_CSV)
        for index, row in df.iterrows():
            if row['section'] == 'overall':
                continue

            weight = PlanDocument.integer_from_text(row['weighting'])
            max_score = PlanDocument.integer_from_text(row['max_score'])

            # create the sections as we go
            # rather than populate the sections in advance we assume that
            # if there's a section in the scores that's not in the database
            # we should create it
            section, created = PlanSection.objects.get_or_create(
                code=self.normalise_section_code(row['section']),
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
                print("Did not find council in db: {}".format(row['council_id']))
                continue

            plan_score, created = PlanScore.objects.get_or_create(
                council=council,
                year=self.YEAR
            )

            score = 0
            if not pd.isnull(row['value']):
                score = PlanDocument.integer_from_text(row['value'])
                weighted_score = score * weight

            section_score, created = PlanSectionScore.objects.get_or_create(
                plan_section=section,
                plan_score=plan_score,
            )

            section_score.score = score
            section_score.weighted_score = weighted_score
            section_score.save()

            totals = council_scores.get(council.authority_code, {'total': 0, 'weighted_total': 0})
            totals['total'] = totals['total'] + section_score.score
            totals['weighted_total'] = totals['weighted_total'] + section_score.weighted_score
            council_scores[council.authority_code] = totals

        for authority_code, totals in council_scores.items():
            plan = PlanScore.objects.get(
                council__authority_code=authority_code,
                year=self.YEAR,
            )
            plan.total = totals['total']
            plan.weighted_total = totals['weighted_total']
            plan.save()


    def import_questions(self):
        df = pd.read_csv(self.QUESTIONS_CSV)
        # pandas thinks this is a float which is unhelpful
        df['Scores'] = df['Scores'].astype(str)

        for index, row in df.iterrows():
            q_type = 'Other'
            if row['Options'] in ('HEADER', 'CHECKBOX'):
                q_type = row['Options']

            code = self.normalise_section_code(row['question_id'])
            section = re.sub(r'(.*)_q[0-9].*', r'\1', code)
            plan_section = None
            try:
                plan_section = PlanSection.objects.get(code=section, year=self.YEAR)
            except PlanSection.DoesNotExist:
                print('no section found for q {}, section {}'.format(code, section))
                continue

            question, created = PlanQuestion.objects.get_or_create(
                code=code,
                section=plan_section
            )
            if created:
                max_score = 0
                if q_type != 'HEADER':
                    scores = PlanDocument.char_from_text(row['Scores'])
                    scores = scores.split(',')
                    max_score = max(scores)
                question.max_score = int(float(max_score))
                question.text = row['Question description']
                question.question_type = q_type
                question.save()


    def import_question_scores(self):
        df = pd.read_csv(self.ANSWERS_CSV)
        for index, row in df.iterrows():
            code = self.normalise_section_code(row['question_id'])
            council_code = row['answer_id']
            council_code = re.sub(r'^([^_]*)_.*', r'\1', council_code)

            try:
                council = Council.objects.get(authority_code=council_code)
                plan_score = PlanScore.objects.get(council=council, year=self.YEAR)
                question = PlanQuestion.objects.get(code=code)
            except Council.DoesNotExist as e:
                print('failed to match council {}'.format(council_code))
                continue
            except PlanScore.DoesNotExist as e:
                print('failed to match plan score for {}'.format(council.name))
                continue
            except PlanQuestion.DoesNotExist as e:
                print('failed to match question {}'.format(code))
                continue

            answer, created = PlanQuestionScore.objects.get_or_create(
                plan_score = plan_score,
                plan_question = question
            )

            if created:
                answer.score = row['score']
                answer.answer = row['answer']
                answer.save()


    def handle(self, *args, **options):
        self.get_files()
        self.import_section_scores()
        self.import_questions()
        self.import_question_scores()