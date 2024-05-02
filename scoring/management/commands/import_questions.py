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
from django.db.models import F, Sum
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

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            action="store",
            help="year to assign questions to",
        )

    def create_sections(self):
        for code, desc in self.SECTIONS.items():
            section, created = PlanSection.objects.get_or_create(
                code=code,
                description=desc,
                year=self.YEAR,
            )

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

            if not pd.isna(row["groups"]):
                for group in row["groups"].split(","):
                    group = group.lower()
                    question.questiongroup.add(q_groups[group_map.get(group, group)])

            question.save()

    def handle(self, year: int = None, *args, **options):
        if year is None:
            self.stdout.write(f"{RED}Please provide a year{NOBOLD}")

        self.YEAR = year
        self.SCORECARD_DATA_DIR = Path(settings.DATA_DIR, "scorecard_data", str(year))
        self.QUESTIONS_CSV = Path(self.SCORECARD_DATA_DIR, "question_data.csv")

        self.create_sections()
        self.import_questions()
