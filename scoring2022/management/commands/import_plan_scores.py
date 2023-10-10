import re
import os
from os.path import join
from datetime import date
import math

import requests
import pandas as pd
from pathlib import Path
from typing import Optional, Union
import shutil
import urllib3
import tempfile
import zipfile

from caps.models import Council
from caps.utils import char_from_text, integer_from_text
from scoring.models import (
    PlanScore,
    PlanSection,
    PlanSectionScore,
    PlanQuestion,
    PlanQuestionScore,
)

from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from django.db.models import F, Sum
from django.template.defaultfilters import pluralize

from django.conf import settings


def download_github_release(
    org: str, repo: str, tag: str, dest: Path, private: bool = False
):
    """
    Get and extract a release zip of a dataset from github.
    If private is true, try to use PERSONAL_ACCESS_TOKEN
    to access the repository. Should only be used as part of testing
    before a dataset is public.
    """

    file = f"https://github.com/{org}/{repo}/archive/refs/tags/{tag}.zip"

    headers = None
    if private:
        token = settings.PERSONAL_ACCESS_TOKEN
        if token is None:
            raise ValueError(
                "Tried to access private repo, but no PERSONAL_ACCESS_TOKEN envkey."
            )
        headers = {"Authorization": "token " + token}

    http = urllib3.PoolManager()
    r = http.request("GET", file, preload_content=False, headers=headers)
    temp_extract_path = tempfile.TemporaryDirectory()
    with tempfile.TemporaryDirectory() as tmpdirname:
        temp_zip_file = Path(tmpdirname, "temporary_zip.zip")
        with open(temp_zip_file, "wb") as out:
            while True:
                data = r.read(64)
                if not data:
                    break
                out.write(data)
        r.release_conn()
        with zipfile.ZipFile(temp_zip_file, "r") as zip_ref:
            zip_ref.extractall(temp_extract_path.name)

    extract_path = Path(temp_extract_path.name, f"{repo}-{tag}")
    if Path(dest).exists():

        shutil.rmtree(dest)
    shutil.copytree(extract_path, dest)


class Command(BaseCommand):
    help = "Imports plan scores"

    YEAR = 2021
    SCORECARD_DATA_DIR = Path(settings.DATA_DIR, "scorecard_data", str(YEAR))
    QUESTIONS_CSV = Path(SCORECARD_DATA_DIR, "questions.csv")
    ANSWERS_CSV = Path(SCORECARD_DATA_DIR, "individual_answers.csv")
    SECTION_SCORES_CSV = Path(SCORECARD_DATA_DIR, "raw_section_marks.csv")
    OVERALL_SCORES_CSV = Path(SCORECARD_DATA_DIR, "all_section_scores.csv")

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
        "s1_gov": "Governance, development and funding",
        "s2_m&a": "Mitigation and adaptation",
        "s3_c&a": "Commitment and integration",
        "s4_coms": "Community, engagement and communications",
        "s5_mset": "Measuring and setting emissions targets",
        "s6_cb": "Co-benefits",
        "s7_dsi": "Diversity and inclusion",
        "s8_est": "Education, skills and training",
        "s9_ee": "Ecological emergency",
    }

    def get_files(self):
        download_github_release(
            **settings.PLAN_SCORECARD_DATASET_DETAILS,
            dest=Path(settings.DATA_DIR, "scorecard_data"),
        )

    def normalise_section_code(self, code):
        normalised = code.replace("&", "_")
        return normalised

    def create_sections(self):
        for code, desc in self.SECTIONS.items():
            section, created = PlanSection.objects.get_or_create(
                code=self.normalise_section_code(code),
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
                year=self.YEAR,
                code=self.normalise_section_code(row["section"]),
            )

            try:
                council = Council.objects.get(
                    authority_code=row["local-authority-code"]
                )
            except Council.DoesNotExist:
                print(
                    "Did not find council in db: {}".format(row["local-authority-code"])
                )
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
                council = Council.objects.get(
                    authority_code=row["local-authority-code"]
                )
            except Council.DoesNotExist:
                print(
                    "Did not find council in db: {}".format(row["local-authority-code"])
                )
                continue

            plan_score, created = PlanScore.objects.get_or_create(
                council=council, year=self.YEAR
            )

            plan_score.total = round(row["raw_total"] * 100, 3)
            plan_score.weighted_total = round(row["weighted_total"] * 100, 3)
            plan_score.save()

            for code in self.SECTIONS.keys():
                if not pd.isnull(row[code]):
                    section = PlanSection.objects.get(
                        year=self.YEAR, code=self.normalise_section_code(code)
                    )

                    section_score, created = PlanSectionScore.objects.get_or_create(
                        plan_section=section,
                        plan_score=plan_score,
                    )

                    section_score.weighted_score = round(row[code] * 100)
                    section_score.save()

    def import_questions(self):
        df = pd.read_csv(self.QUESTIONS_CSV)
        # pandas thinks this is a float which is unhelpful
        df["Scores"] = df["Scores"].astype(str)

        for index, row in df.iterrows():
            q_type = "Other"
            if row["Options"] in ("HEADER", "CHECKBOX"):
                q_type = row["Options"]

            code = self.normalise_section_code(row["question_id"])
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
            max_score = 0
            if q_type != "HEADER":
                scores = char_from_text(row["Scores"])
                scores = scores.split(",")
                max_score = max(scores)
                parent = re.sub(r"([^q]*q[0-9]*).*", r"\1", code)
                question.parent = parent
            question.max_score = int(float(max_score))
            question.text = row["Question description"]
            question.question_type = q_type
            question.save()

    def import_question_scores(self):
        # import related fields in bulk at the start
        councils = {x.authority_code: x for x in Council.objects.all()}
        plan_scores = {x.council: x for x in PlanScore.objects.filter(year=self.YEAR)}
        questions = {x.code: x for x in PlanQuestion.objects.all()}

        df = pd.read_csv(self.ANSWERS_CSV)

        # can fix at series level rather than testing individual entries
        df["score"] = df["score"].fillna(0)
        to_create = []

        # more efficent just to delete everything and quickly reload
        PlanQuestionScore.objects.filter(plan_score__year=self.YEAR).delete()

        for index, row in df.iterrows():
            code = self.normalise_section_code(row["question_id"])

            council = councils.get(row["local-authority-code"], None)
            plan_score = plan_scores.get(council, None)
            question = questions.get(code, None)

            if council is None:
                print("failed to match council {}".format(row["local-authority-code"]))
                continue
            if plan_score is None:
                print("failed to match plan score for {}".format(council.name))
                continue
            if question is None:
                print("failed to match question {}".format(code))
                continue

            score_obj = PlanQuestionScore(
                plan_score=plan_score,
                plan_question=question,
                score=row["score"],
                answer=row["audited_answer"],
            )
            to_create.append(score_obj)
        PlanQuestionScore.objects.bulk_create(to_create)

    def create_header_scores(self):
        plan_questions = {}
        questions = PlanQuestion.objects.all()
        for question in questions:
            plan_questions[question.code] = question

        header_totals = PlanQuestionScore.objects.values(
            "plan_score", "plan_question__parent"
        ).annotate(total=Sum("score"), max_total=Sum("plan_question__max_score"))

        header_scores = []
        for total in header_totals.all():
            q = PlanQuestionScore(
                plan_score_id=total["plan_score"],
                plan_question=plan_questions[total["plan_question__parent"]],
                score=total["total"],
                max_score=total["max_total"],
            )

            header_scores.append(q)

        PlanQuestionScore.objects.bulk_create(header_scores)

    def label_top_performers(self):
        plan_sections = PlanSection.objects.filter(year=2021)

        # reset top performers
        PlanScore.objects.filter(year=self.YEAR).update(top_performer="")
        PlanSectionScore.objects.filter(year=self.YEAR).update(top_performer="")

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
                plan_section=section, score=F("max_score")
            )

            for section_score in top_section_scores.all():
                section_score.top_performer = section.code
                section_score.save()

    def handle(self, *args, **options):
        self.get_files()
        self.create_sections()
        self.import_section_scores()
        self.import_overall_scores()
        self.import_questions()
        self.import_question_scores()
        self.create_header_scores()
        self.label_top_performers()
