from collections import defaultdict
import pandas as pd

from django.core.management.base import BaseCommand
from django.conf import settings

from django.db.models import F

from cape.models import Tag, CouncilTag, Council
from scoring.models import PlanSectionScore, PlanScore, PlanQuestionScore
from cape.import_utils import get_google_sheet_as_csv, replace_csv_headers


def get_tags():
    get_google_sheet_as_csv(settings.TAGS_CSV_KEY, settings.TAGS_CSV)
    get_google_sheet_as_csv(
        settings.TAGS_CSV_KEY,
        settings.COUNCIL_TAGS_CSV,
        sheet_name=settings.COUNCIL_TAGS_CSV_SHEET_NAME,
    )


def replace_headers():
    # remove columns with no header
    df = pd.read_csv(settings.TAGS_CSV)
    empty_cols = [col for col in df.columns if col.startswith("Unnamed")]
    df.drop(empty_cols, axis="columns", inplace=True)
    df.to_csv(open(settings.TAGS_CSV, "w"), index=False, header=True)
    df = pd.read_csv(settings.COUNCIL_TAGS_CSV)
    empty_cols = [col for col in df.columns if col.startswith("Unnamed")]
    df.drop(empty_cols, axis="columns", inplace=True)
    df.to_csv(open(settings.COUNCIL_TAGS_CSV, "w"), index=False, header=True)

    replace_csv_headers(
        settings.TAGS_CSV,
        [
            "name",
            "slug",
            "description_singular",
            "description_plural",
            "colour",
            "image_url",
            "top_scorer",
            "top_section_scorer",
            "full_q_marks",
            "listed",
        ],
        drop_empty_columns=False,
    )

    replace_csv_headers(
        settings.COUNCIL_TAGS_CSV,
        [
            "tag",
            "slug",
            "authority_code",
            "council_name",
        ],
        drop_empty_columns=False,
    )


def get_slug_for_tag(tag):
    # TODO autogenerate this?
    return tag["slug"]


def create_tags():
    df = pd.read_csv(settings.TAGS_CSV)
    for index, row in df.iterrows():
        slug = get_slug_for_tag(row)
        defaults = {
            "name": row["name"],
            "description_singular": row["description_singular"],
            "description_plural": row["description_plural"],
            "colour": row["colour"],
            "image_url": row["image_url"],
        }

        try:
            tag = Tag.objects.get(slug=slug)
            for key, value in defaults.items():
                setattr(tag, key, value)
            tag.save()
        except Tag.DoesNotExist:
            Tag.objects.create(slug=slug, **defaults)


def tag_to_council_map():
    df = pd.read_csv(settings.COUNCIL_TAGS_CSV)
    tag_map = defaultdict(list)
    df["slug"] = df["slug"].fillna("")
    df["authority_code"] = df["authority_code"].fillna("")

    for index, row in df.iterrows():
        if row["slug"] != "":
            tag_map[row["tag"]].append({"slug": row["slug"]})
        else:
            tag_map[row["tag"]].append({"authority_code": row["authority_code"]})

    return tag_map


def create_council_tags():
    df = pd.read_csv(settings.TAGS_CSV)
    tag_map = tag_to_council_map()

    df["top_scorer"] = df["top_scorer"].fillna(0).astype(int)
    df["top_section_scorer"] = df["top_section_scorer"].fillna("")
    df["full_q_marks"] = df["full_q_marks"].fillna("")
    df["listed"] = df["listed"].fillna(0).astype(int)

    for index, row in df.iterrows():
        slug = get_slug_for_tag(row)
        try:
            tag_qs = Tag.objects.get(slug=slug)
        except Tag.DoesNotExist:
            print("no tag found matching {}".format(slug))
            continue

        top = row["top_scorer"]
        section = row["top_section_scorer"]
        listed = row["listed"]
        full_q_marks = row["full_q_marks"]

        if section != "":
            top_scorers = PlanSectionScore.objects.filter(
                plan_section__code=row["top_section_scorer"],
                score=F("max_score"),
            ).select_related("plan_score__council")

            for scorer in top_scorers.all():
                CouncilTag.objects.get_or_create(
                    council=scorer.plan_score.council,
                    tag=tag_qs,
                )

        if top == 1:
            top_scorers = PlanScore.objects.exclude(
                top_performer__exact="",
            ).select_related("council")

            for scorer in top_scorers.all():
                CouncilTag.objects.get_or_create(
                    council=scorer.council,
                    tag=tag_qs,
                )

        if full_q_marks != "":
            full_marks = PlanQuestionScore.objects.filter(
                plan_question__code=full_q_marks, score=F("plan_question__max_score")
            ).select_related("plan_score__council")

            for scorer in full_marks.all():
                CouncilTag.objects.get_or_create(
                    council=scorer.plan_score.council,
                    tag=tag_qs,
                )

        if listed == 1:
            for filter in tag_map[slug]:
                try:
                    council = Council.objects.get(**filter)
                except Council.DoesNotExist:
                    print(
                        "could not find council matching {} for tag {}".format(
                            filter, slug
                        )
                    )
                    continue

                CouncilTag.objects.get_or_create(council=council, tag=tag_qs)


class Command(BaseCommand):
    help = "create tags and council tags"

    def handle(self, *args, **options):
        get_tags()
        replace_headers()
        create_tags()
        create_council_tags()
