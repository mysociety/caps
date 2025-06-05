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
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, OuterRef, Subquery, Sum
from django.template.defaultfilters import pluralize

from caps.models import Council
from caps.utils import char_from_text, integer_from_text
from scoring.models import (
    PlanQuestion,
    PlanQuestionGroup,
    PlanQuestionScore,
    PlanScore,
    PlanSection,
    PlanSectionScore,
)

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "Imports plan scores"

    YEAR = settings.PLAN_YEAR
    SCORECARD_DATA_DIR = Path(settings.DATA_DIR, "scorecard_data", str(YEAR))
    SECTION_SCORES_CSV = Path(SCORECARD_DATA_DIR, "raw_section_marks.csv")
    OVERALL_SCORES_CSV = Path(SCORECARD_DATA_DIR, "all_section_scores.csv")
    QUESTIONS_CSV = Path(SCORECARD_DATA_DIR, "question_data.csv")
    ANSWERS_CSV = Path(SCORECARD_DATA_DIR, "all_answer_data.csv")

    DEFAULT_TOP_PERFORMER_COUNT = 1
    TOP_PERFORMER_COUNT = {
        "combined": 2,
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

    CONTROL_MAP = {
        "GRN": "Green",
        "CON": "Conservative",
        "LAB": "Labour",
        "LD": "Liberal Democrat",
        "PC": "Plaid Cymru",
        "IND": "Independent",
    }

    previous_year = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--update_questions",
            action="store_true",
            help="Updates/creates the text of questions",
        )

        parser.add_argument(
            "--update_political_control",
            action="store_true",
            help="Updates poltical control",
        )

        parser.add_argument(
            "--previous_year",
            action="store",
            help="Previous scorecards year, for calculating most improved, and linking",
        )

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
                year=self.YEAR,
            )

            try:
                council = Council.objects.get(gss_code=row["gss"])
            except Council.DoesNotExist:
                print("Did not find council in db: {}".format(row["gss"]))
                continue

            plan_score, created = PlanScore.objects.get_or_create(
                council=council, year=self.YEAR
            )

            if self.previous_year:
                try:
                    prev = PlanScore.objects.get(
                        council=council, year=self.previous_year
                    )
                    plan_score.previous_year = prev
                    plan_score.save()
                except PlanScore.DoesNotExist:
                    pass

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
                print("Did not find council in db: {}".format(row["council"]))
                continue

            plan_score, created = PlanScore.objects.get_or_create(
                council=council, year=self.YEAR
            )

            plan_score.total = round(row["raw_total"] * 100, 3)
            plan_score.weighted_total = round(row["weighted_total"] * 100, 3)
            if self.update_control and not pd.isna(row["political_control"]):
                plan_score.political_control = self.CONTROL_MAP.get(
                    row["political_control"], row["political_control"]
                )
            plan_score.save()

            for desc in self.SECTIONS.values():
                if not pd.isnull(row[desc]):
                    section = PlanSection.objects.get(year=self.YEAR, description=desc)

                    section_score, created = PlanSectionScore.objects.get_or_create(
                        plan_section=section,
                        plan_score=plan_score,
                    )

                    section_score.weighted_score = round(row[desc] * 100)
                    section_score.save()

    def label_top_performers(self):
        plan_sections = PlanSection.objects.filter(year=self.YEAR)

        # reset top performers
        PlanScore.objects.filter(year=self.YEAR).update(top_performer="")
        PlanSectionScore.objects.filter(plan_score__year=self.YEAR).update(
            top_performer=""
        )

        for group in Council.SCORING_GROUP_CHOICES:
            group_tag = group[0]

            count = self.TOP_PERFORMER_COUNT.get(
                group_tag, self.DEFAULT_TOP_PERFORMER_COUNT
            )
            if count == 0:
                continue

            group_params = Council.SCORING_GROUPS[group_tag]

            top_plan_scores = PlanScore.objects.filter(
                year=self.YEAR,
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
                plan_score__year=self.YEAR,
                plan_section=section,
                weighted_score__gte=80,
            )

            for section_score in top_section_scores.all():
                section_score.top_performer = section.code
                section_score.save()

    def label_most_improved(self, previous_year):
        if not previous_year:
            self.stderr.write("Can't calculate most improved, need previous year")
            return

        plan_sections = PlanSection.objects.filter(year=self.YEAR)

        # reset top performers
        PlanScore.objects.filter(year=self.YEAR).update(most_improved="")
        PlanSectionScore.objects.filter(plan_score__year=self.YEAR).update(
            most_improved=""
        )

        for group in Council.SCORING_GROUP_CHOICES:
            group_tag = group[0]
            group_params = Council.SCORING_GROUPS[group_tag]

            score_differences = (
                PlanScore.objects.filter(
                    year=self.YEAR,
                    council__authority_type__in=group_params["types"],
                    council__country__in=group_params["countries"],
                    weighted_total__gt=0,
                )
                .annotate(
                    previous_score=Subquery(
                        PlanScore.objects.filter(
                            year=previous_year, council_id=OuterRef("council_id")
                        ).values("weighted_total")
                    )
                )
                .annotate(difference=(F("weighted_total") - F("previous_score")))
                .order_by("-difference")
            )

            most_improved = score_differences.first()
            most_improved.most_improved = group_tag
            most_improved.save()

        for section in plan_sections.all():
            if section.code in self.SKIP_SECTION_PERFORMERS:
                continue

            differences = (
                PlanSectionScore.objects.filter(
                    plan_score__year=self.YEAR,
                    plan_section=section,
                )
                .annotate(
                    previous_score=Subquery(
                        PlanSectionScore.objects.filter(
                            plan_score__year=previous_year,
                            plan_section__code=section.code,
                            plan_score__council_id=OuterRef("plan_score__council_id"),
                        ).values("weighted_score")
                    )
                )
                .annotate(difference=(F("weighted_score") - F("previous_score")))
                .order_by("-difference")
            )

            most_improved = differences.first()
            most_improved.most_improved = section.code
            most_improved.save()

        score_differences = (
            PlanScore.objects.filter(
                year=self.YEAR,
                weighted_total__gt=0,
            )
            .annotate(
                previous_score=Subquery(
                    PlanScore.objects.filter(
                        year=previous_year, council_id=OuterRef("council_id")
                    ).values("weighted_total")
                )
            )
            .annotate(difference=(F("weighted_total") - F("previous_score")))
            .order_by("-difference")
        )

        most_improved = score_differences.first()
        most_improved.most_improved = "overall"
        most_improved.save()

    def import_questions(self):
        df = pd.read_csv(self.QUESTIONS_CSV)

        group_map = {
            "single tier": "single",
            "northern ireland": "northern-ireland",
            "combined authority": "combined",
        }
        groups = ["single", "district", "county", "northern-ireland", "combined"]
        q_groups = {}
        for group in groups:
            g, _ = PlanQuestionGroup.objects.get_or_create(description=group)
            q_groups[group] = g

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
            question.criteria = row["criteria"]
            question.topic = row["topic"]
            question.clarifications = row["clarifications"]

            if not pd.isna(row["previous_year_question"]):
                try:
                    prev_q = PlanQuestion.objects.get(
                        section__year=self.previous_year,
                        code=f"{section}_q{row['previous_year_question']}",
                    )
                    question.previous_question = prev_q
                except PlanQuestion.DoesNotExist:
                    print(
                        f"no previous question found for {code} - {row['previous_year_question']}"
                    )

            if not pd.isna(row["groups"]):
                for group in row["groups"].split(","):
                    group = group.lower()
                    question.questiongroup.add(q_groups[group_map.get(group, group)])

            question.save()

    def import_question_scores(self):
        # import related fields in bulk at the start
        councils = {x.gss_code: x for x in Council.objects.all()}
        plan_scores = {x.council: x for x in PlanScore.objects.filter(year=self.YEAR)}
        questions = {
            x.code: x for x in PlanQuestion.objects.filter(section__year=self.YEAR)
        }

        section_codes = {name: code for code, name in self.SECTIONS.items()}

        df = pd.read_csv(self.ANSWERS_CSV)

        # can fix at series level rather than testing individual entries
        df["score"] = df["score"].fillna(0)
        df["score"] = df["score"].astype("string")
        df["score"] = df["score"].str.replace("-", "0")
        df["score"] = df["score"].astype("float")
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
                max_score=row["max_score"],
            )
            to_create.append(score_obj)
        PlanQuestionScore.objects.bulk_create(to_create)

    def handle(
        self,
        update_questions: bool = False,
        update_political_control: bool = False,
        previous_year: int = None,
        *args,
        **options,
    ):
        self.update_control = update_political_control
        self.previous_year = previous_year
        self.stdout.write(f"Importing council action scores for {self.YEAR}")
        if not update_questions:
            self.stdout.write(
                f"{YELLOW}Not creating or updating questions, call with --update_questions to do so{NOBOLD}"
            )
        self.create_sections()
        self.import_section_scores()
        self.import_overall_scores()
        self.label_top_performers()
        if update_questions:
            self.import_questions()
        self.import_question_scores()
        self.label_most_improved(previous_year)
