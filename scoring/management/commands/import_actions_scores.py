import math
import os
import re
import shutil
import tempfile
import zipfile
from datetime import date
from os.path import join
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import requests
import urllib3
from caps.models import Council
from caps.utils import char_from_text, integer_from_text
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Sum
from django.template.defaultfilters import pluralize
from scoring.models import (
    PlanQuestion,
    PlanQuestionScore,
    PlanScore,
    PlanSection,
    PlanSectionScore,
)


class Command(BaseCommand):
    help = "Imports plan scores"

    YEAR = 2023  # settings.PLAN_YEAR
    SCORECARD_DATA_DIR = Path(settings.DATA_DIR, "scorecard_data", str(YEAR))
    SECTION_SCORES_CSV = Path(SCORECARD_DATA_DIR, "raw_section_marks.csv")
    OVERALL_SCORES_CSV = Path(SCORECARD_DATA_DIR, "all_section_scores.csv")
    QUESTIONS_CSV = Path(SCORECARD_DATA_DIR, "question_data.csv")
    ANSWERS_CSV = Path(SCORECARD_DATA_DIR, "all_answer_data.csv")

    DEFAULT_TOP_PERFORMER_COUNT = 10
    TOP_PERFORMER_COUNT = {
        "district": 3,
        "county": 1,
        "single": 3,
        "northern-ireland": 0,
        "combined": 1,
    }

    SKIP_SECTION_PERFORMERS = ["s6_cb"]

    SECTIONS = {
        "s1_b_h": "Buildings & Heating",
        "s2_tran": "Transport",
        "s3_p_lu": "Planning & Land Use",
        "s4_g_f": "Governance & Finance",
        "s5_bio": "Biodiversity",
        "s6_c_e": "Collaboration & Engagement",
        "s7_wr_f": "Waste Reduction & Food",
        "s1_b_h_gs_ca": "Buildings & Heating & Green Skills (CA)",
        "s2_tran_ca": "Transport (CA)",
        "s3_p_b_ca": "Planning & Biodiversity (CA)",
        "s4_g_f_ca": "Governance & Finance (CA)",
        "s5_c_e_ca": "Collaboration & Engagement (CA)",
    }

    def create_sections(self):
        for code, desc in self.SECTIONS.items():
            section, created = PlanSection.objects.get_or_create(
                code=code,
                description=desc,
                year=self.YEAR,
            )

    def import_section_scores(self):
        council_scores = {}

        df = pd.read_csv(self.SECTION_SCORES_CSV)
        for index, row in df.iterrows():
            if row["section"] == "overall":
                continue

            # update the section max_score as we go
            section = PlanSection.objects.get(
                description=row["section"],
            )

            try:
                council = Council.objects.get(gss_code=row["gss"])
            except Council.DoesNotExist:
                print("Did not find council in db: {}".format(row["gss"]))
                continue

            plan_score, created = PlanScore.objects.get_or_create(
                council=council, year=self.YEAR
            )

            score = 0
            if not pd.isnull(row["score"]):
                score = integer_from_text(row["score"])

            max_score = integer_from_text(row["max_score"])

            section_score, created = PlanSectionScore.objects.get_or_create(
                plan_section=section,
                plan_score=plan_score,
            )

            section_score.max_score = max_score
            section_score.score = score
            section_score.save()

    def import_overall_scores(self):
        df = pd.read_csv(self.OVERALL_SCORES_CSV)
        for index, row in df.iterrows():
            try:
                council = Council.objects.get(gss_code=row["gss"])
            except Council.DoesNotExist:
                print("Did not find council in db: {}".format(row["name"]))
                continue

            plan_score, created = PlanScore.objects.get_or_create(
                council=council, year=self.YEAR
            )

            plan_score.total = round(row["raw_total"] * 100, 3)
            plan_score.weighted_total = round(row["weighted_total"] * 100, 3)
            plan_score.save()

            for desc in self.SECTIONS.values():
                if not pd.isnull(row[desc]):
                    section = PlanSection.objects.get(description=desc)

                    section_score, created = PlanSectionScore.objects.get_or_create(
                        plan_section=section,
                        plan_score=plan_score,
                    )

                    section_score.weighted_score = round(row[desc] * 100)
                    section_score.save()

    def label_top_performers(self):
        plan_sections = PlanSection.objects.filter(year=2021)

        # reset top performers
        PlanScore.objects.update(top_performer="")
        PlanSectionScore.objects.update(top_performer="")

        for group in Council.SCORING_GROUP_CHOICES:
            group_tag = group[0]

            count = self.TOP_PERFORMER_COUNT.get(
                group_tag, self.DEFAULT_TOP_PERFORMER_COUNT
            )
            if count == 0:
                continue

            group_params = Council.SCORING_GROUPS[group_tag]

            top_plan_scores = PlanScore.objects.filter(
                council__authority_type__in=group_params["types"],
                council__country__in=group_params["countries"],
                weighted_total__gt=0,
            ).order_by("-weighted_total")

            for plan_score in top_plan_scores.all()[:count]:
                plan_score.top_performer = group_tag
                plan_score.save()

        for section in plan_sections.all():
            if section.code in self.SKIP_SECTION_PERFORMERS:
                continue

            top_section_scores = PlanSectionScore.objects.filter(
                plan_section=section, score=F("max_score")
            )

            for section_score in top_section_scores.all():
                section_score.top_performer = section.code
                section_score.save()

    def import_questions(self):
        df = pd.read_csv(self.QUESTIONS_CSV)

        section_codes = {name: code for code, name in self.SECTIONS.items()}

        for index, row in df.iterrows():
            code = section_codes[row["section"]] + "_q" + row["question_number"]

            section = re.sub(r"(.*)_q[0-9].*", r"\1", code)
            plan_section = None
            try:
                plan_section = PlanSection.objects.get(code=section, year=self.YEAR)
            except PlanSection.DoesNotExist:
                print("no section found for q {}, section {}".format(code, section))
                continue

            question, created = PlanQuestion.objects.get_or_create(
                code=code, section=plan_section
            )

            question.max_score = row["max_score"]
            question.text = row["description"]
            question.question_type = row["type"]
            question.weighting = row["weighting"]
            question.how_marked = row["how_marked"]
            question.save()

    def import_question_scores(self):
        # import related fields in bulk at the start
        councils = {x.gss_code: x for x in Council.objects.all()}
        plan_scores = {x.council: x for x in PlanScore.objects.filter(year=self.YEAR)}
        questions = {x.code: x for x in PlanQuestion.objects.all()}

        section_codes = {name: code for code, name in self.SECTIONS.items()}

        df = pd.read_csv(self.ANSWERS_CSV)

        # can fix at series level rather than testing individual entries
        df["score"] = df["score"].fillna(0)
        to_create = []

        # more efficent just to delete everything and quickly reload
        PlanQuestionScore.objects.filter(plan_score__year=self.YEAR).delete()

        for index, row in df.iterrows():
            code = section_codes[row["section"]] + "_q" + row["question-number"]

            council = councils.get(row["local-authority-gss-code"], None)
            plan_score = plan_scores.get(council, None)
            question = questions.get(code, None)

            if council is None:
                print(
                    "failed to match council {}".format(row["local-authority-gss-code"])
                )
                continue
            if plan_score is None:
                print("failed to match plan score for {}".format(council.name))
                continue
            if question is None:
                print("failed to match question {}".format(code))
                continue

            links = ""
            if not pd.isna(row["evidence"]):
                links = row["evidence"]

            score_obj = PlanQuestionScore(
                plan_score=plan_score,
                plan_question=question,
                score=row["score"],
                answer=row["answer"],
                evidence_links=links,
            )
            to_create.append(score_obj)
        PlanQuestionScore.objects.bulk_create(to_create)

    def handle(self, *args, **options):
        self.create_sections()
        self.import_section_scores()
        self.import_overall_scores()
        self.label_top_performers()
        self.import_questions()
        self.import_question_scores()