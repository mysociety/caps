import re
from collections import defaultdict
from copy import deepcopy
from datetime import date
from operator import itemgetter

from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Avg, Count, F, Max, Min, OuterRef, Subquery, Sum
from django.shortcuts import get_object_or_404, resolve_url, reverse
from django.templatetags.static import static
from django.utils.decorators import method_decorator
from django.utils.text import Truncator
from django.views.decorators.cache import cache_control
from django.views.generic import DetailView, TemplateView
from django_filters.views import FilterView

from caps.models import Council, PlanDocument, Promise
from caps.utils import gen_natsort_lamda
from caps.views import BaseLocationResultsView
from scoring.filters import PlanScoreFilter, QuestionScoreFilter
from scoring.forms import ScoringSort, ScoringSortCA
from scoring.mixins import (
    AdvancedFilterMixin,
    CheckForDownPageMixin,
    SearchAutocompleteMixin,
)
from scoring.models import (
    PlanQuestion,
    PlanQuestionScore,
    PlanScore,
    PlanScoreDocument,
    PlanSection,
    PlanSectionScore,
)

cache_settings = {
    "max-age": 60,
    "s-maxage": 3600,
}


class DownPageView(TemplateView):
    template_name = "scoring/down.html"


class LoginView(LoginView):
    next_page = "scoring:home"
    template_name = "scoring/login.html"

    def get_success_url(self):
        return resolve_url(self.next_page)


class LogoutView(LogoutView):
    next_page = "scoring:home"


class PrivacyView(TemplateView):
    template_name = "scoring/privacy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Privacy Policy"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HomePageView(
    CheckForDownPageMixin, SearchAutocompleteMixin, AdvancedFilterMixin, FilterView
):
    filterset_class = PlanScoreFilter

    def get_template_names(self):
        authority_type = self.get_authority_type()["slug"]
        if authority_type == "combined":
            return ["scoring/home_combined.html"]

        return ["scoring/home.html"]

    def get_authority_type(self):
        authority_type = self.kwargs.get("council_type", "")
        try:
            group = Council.SCORING_GROUPS[authority_type]
        except:
            group = Council.SCORING_GROUPS["single"]

        return group

    def get_queryset(self):
        authority_type = self.get_authority_type()
        filters = {
            "year": settings.PLAN_YEAR,
            "council__authority_type__in": authority_type["types"],
        }

        if self.request.GET.get("country", None) is None:
            filters["council__country__in"] = authority_type["countries"]

        qs = (
            PlanScore.objects.filter(**filters)
            .annotate(
                score=F("weighted_total"),
                name=F("council__name"),
                slug=F("council__slug"),
                authority_code=F("council__authority_code"),
            )
            .order_by(F("weighted_total").desc(nulls_last=True))
        )

        return qs

    def get_missing_councils(self, council_ids, authority_type):
        filter_params = ["region", "county"]

        filters = {
            "authority_type__in": authority_type["types"],
            "end_date__isnull": True,
        }

        for f in filter_params:
            if self.request.GET.get(f, None) is not None:
                filters[f] = self.request.GET[f]

        if self.request.GET.get("country", None) is None:
            filters["country__in"] = authority_type["countries"]
        else:
            filters["country__in"] = self.request.GET["country"]

        missing_councils = Council.objects.exclude(id__in=council_ids).filter(**filters)

        return missing_councils

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        authority_type = self.get_authority_type()

        councils = context["object_list"].values()
        context["plan_sections"] = PlanSection.objects.filter(
            year=settings.PLAN_YEAR
        ).all()

        context = self.setup_filter_context(context, context["filter"], authority_type)

        averages = PlanSection.get_average_scores(
            authority_type["slug"], filter=context.get("filter_params", None)
        )
        all_scores = PlanSectionScore.get_all_council_scores()

        councils = list(councils.all())
        council_ids = []
        for council in councils:
            council_ids.append(council["council_id"])
            council["all_scores"] = all_scores[council["council_id"]]
            if council["score"] is not None:
                council["percentage"] = council["score"]
            else:
                council["percentage"] = 0

        missing_councils = self.get_missing_councils(council_ids, authority_type)

        for council in missing_councils:
            councils.append(
                {
                    "score": None,
                    "name": council.name,
                    "slug": council.slug,
                    "authority_code": council.authority_code,
                    "top_performer": None,
                }
            )
        codes = PlanSection.section_codes()

        if authority_type["slug"] == "combined":
            form_class = ScoringSortCA
        else:
            form_class = ScoringSort

        form = form_class(self.request.GET)
        sorted_by = None
        if form.is_valid():
            sort = form.cleaned_data["sort_by"]
            if sort != "":
                sorted_by = sort
                councils = sorted(
                    councils,
                    key=lambda council: 0
                    if council["score"] == 0 or council["score"] is None
                    else council["all_scores"][sort]["score"],
                    reverse=True,
                )
                councils = sorted(councils, key=itemgetter("slug"))
        else:
            form = form_class()

        context["authority_type"] = authority_type["slug"]
        context["authority_type_label"] = authority_type["name"]

        context["form"] = form
        context["sorted_by"] = sorted_by
        context["council_data"] = councils
        context["averages"] = averages

        title_format_strings = {
            "single": "Council Climate Action Scorecards",
            "district": "{name} Councils’ Climate Action Scorecards",
            "county": "{name} Councils’ Climate Action Scorecards",
            "combined": "{name} Climate Action Scorecards",
            "northern-ireland": "{name} Councils’ Climate Action Scorecards",
        }

        context["page_title"] = title_format_strings[authority_type["slug"]].format(
            name=authority_type["name"]
        )
        context["site_title"] = "Climate Emergency UK"

        context["current_page"] = "home-page"

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class CouncilView(CheckForDownPageMixin, SearchAutocompleteMixin, DetailView):
    model = Council
    context_object_name = "council"
    template_name = "scoring/council.html"

    def make_question_obj(self, question):
        q = {
            "code": question.code,
            "pretty_code": question.pretty_code(),
            "display_code": question.code.replace(
                "{}_".format(question.section_code), "", 1
            ),
            "question": question.text,
            "criteria": question.criteria,
            "type": question.question_type,
            "max": question.max_score,
            "section": question.section_code,
            "answer": question.answer or "-",
            "score": question.score or 0,
            "negative": question.question_type == "negative",
            # need to do this to make the JS work
            "how_marked": question.how_marked.replace("_", "-"),
            "how_marked_display": question.get_how_marked_display(),
            "is_council_operations_only": question.is_council_operations_only,
            "weighting": question.get_weighting_display(),
            "evidence_links": question.evidence_links.splitlines(),
        }
        if question.question_type == "HEADER":
            q["max"] = question.header_max

        return q

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council = context.get("council")
        group = council.get_scoring_group()

        new_council_date = date(year=2023, month=1, day=1)
        if council.start_date is not None and council.start_date >= new_council_date:
            context["authority_type"] = group
            context["new_council"] = True
            return context

        old_council_date = date(year=2021, month=4, day=1)
        if council.end_date is not None and council.end_date <= old_council_date:
            context["authority_type"] = group
            context["old_council"] = True
            return context

        promises = Promise.objects.filter(council=council).all()

        target = None
        for promise in promises:
            if target is None:
                target = promise
            elif target is not None and promise.scope == PlanDocument.WHOLE_AREA:
                target = promise
        context["target"] = target

        try:
            plan_score = PlanScore.objects.get(council=council, year=settings.PLAN_YEAR)
        except PlanScore.DoesNotExist:
            context["no_plan"] = True
            return context

        plan_urls = PlanScoreDocument.objects.filter(plan_score=plan_score)
        sections = PlanSectionScore.sections_for_council(
            council=council, plan_year=settings.PLAN_YEAR
        )

        try:
            previous_score = PlanScore.objects.get(council=council, year=2021)
            context["previous_score"] = previous_score
        except PlanScore.DoesNotExist:
            context["previous_score"] = False

        for section in sections.keys():
            sections[section]["non_negative_max"] = sections[section]["score"]
            sections[section]["negative_points"] = 0

        # get average section scores for authorities of the same type
        section_avgs = PlanSectionScore.get_all_section_averages(
            council_group=group, plan_year=settings.PLAN_YEAR
        )
        for section in section_avgs.all():
            sections[section["plan_section__code"]]["avg"] = round(
                section["avg_score"], 1
            )

        section_top_marks = PlanSectionScore.get_all_section_top_mark_counts(
            council_group=group, plan_year=settings.PLAN_YEAR
        )
        for section in section_top_marks.all():
            sections[section["plan_section__code"]]["max_count"] = section[
                "max_score_count"
            ]

        question_max_counts = PlanQuestionScore.all_question_max_score_counts(
            council_group=group, plan_year=settings.PLAN_YEAR
        )

        comparison_slugs = self.request.GET.getlist("comparisons")
        comparisons = None
        comparison_answers = defaultdict(dict)
        if comparison_slugs:
            comparisons = (
                PlanScore.objects.select_related("council")
                .filter(council__slug__in=comparison_slugs, year=settings.PLAN_YEAR)
                .order_by("council__name")
            )
            comparison_sections = PlanSectionScore.sections_for_plans(
                plans=comparisons, plan_year=settings.PLAN_YEAR
            )
            for section, details in comparison_sections.items():
                sections[section]["comparisons"] = details

            comparison_ids = [p.id for p in comparisons]
            if len(comparison_ids) > 0:
                for question in PlanScore.questions_answered_for_councils(
                    plan_ids=comparison_ids, plan_year=settings.PLAN_YEAR
                ):
                    q = self.make_question_obj(question)
                    comparison_answers[question.code][question.council_name] = q

        for question in plan_score.questions_answered():
            section = question.section_code

            q = self.make_question_obj(question)
            q["council_count"] = question_max_counts.get(question.code, 0)
            q["comparisons"] = []
            # not all councils have answers for all questions so make sure we
            # display something
            if comparisons is not None:
                for c in comparisons:
                    q["comparisons"].append(
                        comparison_answers[question.code].get(
                            c.council.name, {"score": "-", "max": "-"}
                        )
                    )

            if q["negative"] and q["score"] < 0:
                sections[section]["negative_points"] += q["score"]
                sections[section]["non_negative_max"] -= q["score"]
                sections[section]["has_negative_points"] = True

            sections[section]["answers"].append(q)

        natsort = gen_natsort_lamda(lambda k: k["code"])
        for section, data in sections.items():
            if data.get("has_negative_points", False):
                if data["non_negative_max"] != 0:
                    data["negative_percent"] = (
                        data["negative_points"] / data["non_negative_max"]
                    ) * -100
                else:
                    data["only_negative"] = True
            data["answers"] = sorted(data["answers"], key=natsort)

        council_count = Council.objects.filter(
            authority_type__in=group["types"],
            country__in=group["countries"],
        ).count()

        context["council_count"] = council_count
        context["authority_type"] = group
        context["plan_score"] = plan_score
        context["plan_urls"] = plan_urls
        context["sections"] = sorted(
            sections.values(), key=lambda section: section["code"]
        )
        context["page_title"] = "{name} Climate Plan Scorecards".format(
            name=council.name
        )

        context["comparisons"] = comparisons
        context[
            "page_description"
        ] = "Want to know how effective {name}’s climate plans are? Check out {name}’s Council Climate Scorecard to understand how their climate plans compare to local authorities across the UK.".format(
            name=council.name
        )
        context[
            "twitter_tweet_text"
        ] = "Up to 30% of the UK’s transition to zero carbon is within the influence of local councils - that’s why I’m checking {name}’s Climate Action Plan on 📋 #CouncilClimateScorecards".format(
            name=(
                "@{}".format(council.twitter_name)
                if council.twitter_name
                else council.name
            )
        )
        context[
            "og_image_path"
        ] = f"{settings.MEDIA_URL}scoring/og-images/councils/{council.slug}.png"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class CouncilPreview(DetailView):
    model = Council
    context_object_name = "council"
    template_name = "scoring/council-preview.html"

    def get_high_low_scores(self, plan_score):
        max_score = {"score": 0, "section": None}
        min_score = {"score": 100, "section": None}

        for section in PlanSectionScore.objects.filter(plan_score=plan_score):
            score = section.weighted_score

            if score > max_score["score"]:
                max_score = {"score": score, "section": section}

            if score < min_score["score"]:
                min_score = {"score": score, "section": section}

        return max_score, min_score

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council = context.get("council")
        plan_score = PlanScore.objects.get(council=council, year=settings.PLAN_YEAR)
        max_score, min_score = self.get_high_low_scores(plan_score)

        context["page_title"] = council.name
        context["plan_score"] = plan_score
        context["authority_type"] = council.get_scoring_group()
        context["max_score"] = max_score
        context["min_score"] = min_score
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class CouncilTypeTopPerformerView(TemplateView):
    template_name = "scoring/council-top-performer-overall-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council_type = self.kwargs["council_type"]
        group = Council.SCORING_GROUPS[council_type]
        scores = PlanScore.objects.filter(
            year=settings.PLAN_YEAR,
            council__authority_type__in=group["types"],
            council__country__in=group["countries"],
        ).order_by("-weighted_total")

        top = scores.first()
        council = top.council

        context["page_title"] = council.name
        context["authority_type"] = group
        context["council"] = council
        context["score"] = top.weighted_total

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class CouncilPreviewTopPerfomer(DetailView):
    model = Council
    context_object_name = "council"
    template_name = "scoring/council-top-performer-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council = context.get("council")
        context["page_title"] = council.name
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionView(CheckForDownPageMixin, SearchAutocompleteMixin, DetailView):
    model = PlanSection
    context_object_name = "section"
    template_name = "scoring/section.html"

    combined_alt_map = {
        "s1_b_h": "s1_b_h_gs_ca",
        "s2_tran": "s2_tran_ca",
        "s3_p_lu": "s3_p_b_ca",
        "s4_g_f": "s5_g_f_ca",
        "s6_c_e": "s6_c_e_ca",
    }

    alt_map = dict((ca, non_ca) for non_ca, ca in combined_alt_map.items())

    def get_object(self):
        return get_object_or_404(PlanSection, code=self.kwargs["code"])

    def add_comparisons(self, context, comparison_slugs, comparison_questions):
        section = context["section"]
        comparisons = None
        if comparison_slugs:
            comparisons = (
                PlanScore.objects.select_related("council")
                .filter(year=settings.PLAN_YEAR, council__slug__in=comparison_slugs)
                .order_by("council__name")
            )
            comparison_sections = PlanSectionScore.sections_for_plans(
                plans=comparisons,
                plan_year=2023,  # settings.PLAN_YEAR,
                plan_sections=PlanSection.objects.filter(code=section.code),
            )

            comparison_scores = comparison_sections[section.code]

            for score in comparison_scores:
                answers = {
                    answer.plan_question.code: answer
                    for answer in score["section_score"].questions_answered()
                }
                for code in comparison_questions.keys():
                    if answers.get(code, None) is not None:
                        answer = answers[code]
                        comparison_questions[code]["comparisons"].append(answer)
                        if answer.score < 0:
                            score["negative_points"] += answer.score
                            score["non_negative_max"] -= answer.score
                    else:
                        comparison_questions[code]["comparisons"].append({"score": "-"})

                if score["negative_points"] < 0:
                    score["negative_percent"] = (
                        round((score["negative_points"] / score["max_score"]) * 100, 0)
                        * -1
                    )

            context["comparison_councils"] = comparisons
            context["comparison_scores"] = comparison_scores

    def get_questions(self, context):
        section = context["section"]

        # fix sorting to not have 1, 11, 2
        natsort = lambda q: [
            int(t) if t.isdigit() else t.lower() for t in re.split("(\d+)", q)
        ]

        council = self.request.GET.get("council", None)
        if council is not None:
            try:
                council = Council.objects.get(slug=council)
                council_type = council.get_scoring_group()
            except Council.DoesNotExist:
                council_type = None
        elif section.is_combined:
            council_type = Council.SCORING_GROUPS["combined"]
        else:
            council_type = Council.SCORING_GROUPS.get(
                self.request.GET.get("type", None), None
            )

        if council_type is not None:
            comparison_questions = {}

            context["council_type"] = council_type

            council_count = Council.objects.filter(
                authority_type__in=council_type["types"],
                country__in=council_type["countries"],
            ).count()
            context["council_count"] = council_count

            questions = PlanQuestion.objects.filter(section=section)
            for question in questions:
                comparison_questions[question.code] = {
                    "details": question,
                    "comparisons": [],
                }

            question_max_counts = PlanQuestionScore.all_question_max_score_counts(
                council_group=council_type, plan_year=settings.PLAN_YEAR
            )

            for q in comparison_questions.keys():
                comparison_questions[q]["scored_max"] = question_max_counts.get(q, None)

            comparison_slugs = self.request.GET.getlist("comparisons")
            if council is not None:
                comparison_slugs.insert(0, council.slug)

            self.add_comparisons(context, comparison_slugs, comparison_questions)

            context["questions"] = [
                comparison_questions[k]
                for k in sorted(comparison_questions.keys(), key=natsort)
            ]
            context["council_type"] = council_type

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        section = context["section"]
        context["page_title"] = section.description

        alt = section.get_alternative
        if alt is not None:
            context["alternative"] = {
                "name": alt.description,
                "url": reverse("scoring:section", args=(alt.code,)),
            }

        self.get_questions(context)

        avgs = section.get_averages_by_council_group()
        avgs["ni"] = avgs["northern-ireland"]
        context["averages"] = avgs
        if context.get("council_type", None) is not None:
            context["council_type_avg"] = avgs[context["council_type"]["slug"]]
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionsView(CheckForDownPageMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/sections.html"

    sections = [
        "s1_b_h",
        "s2_tran",
        "s3_p_lu",
        "s4_g_f",
        "s5_bio",
        "s6_c_e",
        "s7_wr_f",
    ]
    ca_sections = [
        "s1_b_h_gs_ca",
        "s2_tran_ca",
        "s3_p_b_ca",
        "s4_g_f_ca",
        "s5_c_e_ca",
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Sections"
        context["sections"] = []
        context["ca_sections"] = []
        for section in PlanSection.objects.all():
            details = {
                "name": section.description,
                "url": reverse("scoring:section", args=(section.code,)),
                "description": section.long_description,
            }
            if section.code in self.sections:
                context["sections"].append(details)
            elif section.code in self.ca_sections:
                context["ca_sections"].append(details)

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionPreview(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/section-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]
        council_type = self.kwargs["type"]

        group = Council.SCORING_GROUPS[council_type]

        section = PlanSection.objects.get(code=code)

        scores = PlanSectionScore.objects.filter(
            plan_section=section,
            plan_score__year=settings.PLAN_YEAR,
            plan_score__council__authority_type__in=group["types"],
            plan_score__council__country__in=group["countries"],
        ).aggregate(
            maximum=Max("weighted_score"),
            minimum=Min("weighted_score"),
            average=Avg("weighted_score"),
        )

        context["section"] = section
        context["authority_type"] = group
        context["scores"] = scores

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionTopPerformerPreview(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/council-top-performer-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]

        section = PlanSection.objects.get(code=code)

        scores = PlanSectionScore.objects.filter(
            plan_section=section,
            plan_score__year=settings.PLAN_YEAR,
        ).order_by("-weighted_score")

        top = scores.first()

        context["section"] = section
        context["score"] = top.weighted_score
        context["council"] = top.plan_score.council

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionCouncilTopPerformerPreview(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/council-top-performer-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]
        council = self.kwargs["council"]

        section = PlanSection.objects.get(code=code)

        scores = get_object_or_404(
            PlanSectionScore,
            plan_section=section,
            top_performer=code,
            plan_score__year=settings.PLAN_YEAR,
            plan_score__council__slug=council,
        )

        context["section"] = section
        context["score"] = scores.weighted_score
        context["council"] = scores.plan_score.council

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class LocationResultsView(CheckForDownPageMixin, BaseLocationResultsView):
    template_name = "scoring/location_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Choose a council"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class AboutView(CheckForDownPageMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "About"
        context["current_page"] = "about-page"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class MethodologyView(CheckForDownPageMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/methodology.html"

    def get_question_number(self, question):
        code = question.code
        code = code.replace(question.section.code, "")
        code = code.replace("_q", "")
        return code

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Methodology"
        context["current_page"] = "methodology-page"

        questions = (
            PlanQuestion.objects.filter(section__year=settings.PLAN_YEAR)
            .select_related("section")
            .order_by("section__code", "code")
        )

        sections = []

        # fix sorting to not have 1, 11, 2
        natsort = gen_natsort_lamda(lambda k: k["code"])

        SECTION_WEIGHTINGS = {
            "Buildings & Heating": {
                "single": 20,
                "district": 25,
                "county": 20,
                "northern-ireland": 20,
            },
            "Transport": {
                "single": 20,
                "district": 5,
                "county": 30,
                "northern-ireland": 15,
            },
            "Planning & Land Use": {
                "single": 15,
                "district": 25,
                "county": 5,
                "northern-ireland": 15,
            },
            "Governance & Finance": {
                "single": 15,
                "district": 15,
                "county": 15,
                "northern-ireland": 20,
            },
            "Biodiversity": {
                "single": 10,
                "district": 10,
                "county": 10,
                "northern-ireland": 10,
            },
            "Collaboration & Engagement": {
                "single": 10,
                "district": 10,
                "county": 10,
                "northern-ireland": 10,
            },
            "Waste Reduction & Food": {
                "single": 10,
                "district": 10,
                "county": 10,
                "northern-ireland": 10,
            },
            "Transport (CA)": {
                "combined": 25,
            },
            "Buildings & Heating & Green Skills (CA)": {
                "combined": 25,
            },
            "Governance & Finance (CA)": {
                "combined": 20,
            },
            "Planning & Biodiversity (CA)": {
                "combined": 10,
            },
            "Collaboration & Engagement (CA)": {
                "combined": 20,
            },
        }

        current_section = None
        for question in questions:
            if (
                current_section is not None
                and current_section["title"] != question.section.description
            ):
                current_section["questions"] = sorted(
                    current_section["questions"], key=natsort
                )
                sections.append(deepcopy(current_section))
                current_section = None

            if current_section is None:
                is_combined = False
                types = [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                ]
                if question.section.code.find("_ca") > 0:
                    is_combined = True
                    types = ["combined"]
                current_section = {
                    "code": question.section.code,
                    "title": question.section.description,
                    "council_types": types,
                    "description": question.section.long_description,
                    "is_combined": is_combined,
                    "weightings": SECTION_WEIGHTINGS[question.section.description],
                    "questions": [],
                }

            q_types = [g.description for g in question.questiongroup.all()]
            q = {
                "council_types": q_types,
                "code": self.get_question_number(question),
                "name": question.text,
                "topic": question.topic,
                "importance": question.get_weighting_display(),
                "how_marked": question.get_how_marked_display(),
                "criteria": question.criteria,
                "clarifications": question.clarifications,
            }

            current_section["questions"].append(deepcopy(q))

        current_section["questions"] = sorted(current_section["questions"], key=natsort)
        sections.append(deepcopy(current_section))
        context["sections"] = sections

        context["organisations"] = [
            {"name": "20’s Plenty for Us"},
            {"name": "Abundance Investment"},
            {"name": "Active Travel Academy"},
            {"name": "Ad Free Cities"},
            {"name": "ADEPT"},
            {"name": "Anthesis"},
            {"name": "Architects Action Network"},
            {"name": "Association of Local Government Ecologists"},
            {"name": "Badvertising"},
            {"name": "Brighton Peace and Environment Centre"},
            {"name": "British Lung Foundation"},
            {"name": "Buglife"},
            {"name": "Campaign for Better Transport"},
            {"name": "Carbon Co-op"},
            {"name": "Chartered Institute of Public Finance and Accountancy"},
            {"name": "CLES"},
            {"name": "Climate Conversations"},
            {"name": "Climate Emergency Manchester"},
            {"name": "Climate Museum UK"},
            {"name": "Collective for Climate Action"},
            {"name": "Community Energy England"},
            {"name": "Community Rights Planning"},
            {"name": "CoMoUK"},
            {"name": "Crossing Footprints"},
            {"name": "Culture Declares Emergency"},
            {"name": "Cycle Streets"},
            {"name": "Cycling UK"},
            {"name": "Democracy Club"},
            {"name": "Department of Transport"},
            {"name": "Ecotricity"},
            {"name": "Energy Savings Trust"},
            {"name": "Food For Life"},
            {"name": "Food Matters"},
            {"name": "Friends of the Earth"},
            {"name": "Generation Rent"},
            {"name": "Green Finance Institute"},
            {"name": "Green Flag (Keep Britain Tidy)"},
            {"name": "Institute for Local Government"},
            {"name": "Involve"},
            {"name": "Living Streets"},
            {"name": "Local Partnerships"},
            {"name": "London Cycling Campaign"},
            {"name": "Making Places Together"},
            {"name": "mySociety"},
            {"name": "National Farmers’ Union"},
            {"name": "Passivhaus Homes"},
            {"name": "Pesticides Action Network"},
            {"name": "PETA (People for the Ethical Treatment of Animals)"},
            {"name": "Place Based Carbon Calculator"},
            {"name": "Planning Aid Wales"},
            {"name": "Planning Scotland"},
            {"name": "Plantlife"},
            {"name": "Plastic Free Communities"},
            {"name": "Possible"},
            {"name": "ProVeg"},
            {"name": "Quantum Strategy & Technology"},
            {"name": "Solar Together"},
            {"name": "Southampton Climate Action Network"},
            {"name": "Sustain"},
            {"name": "Sustrans"},
            {"name": "The Campaign to Protect Rural England"},
            {"name": "The Climate Change Committee"},
            {"name": "The Soil Association"},
            {"name": "The Wildlife Trusts"},
            {"name": "Town and Country Planning Association"},
            {"name": "Transport Action Network"},
            {"name": "Transport for New Homes"},
            {"name": "Tree Economics"},
            {"name": "Turing Institute"},
            {"name": "UK Divest"},
            {"name": "Waste Data Flow"},
            {"name": "Wirral Environmental Network"},
            {"name": "Wildlife & Countryside Link"},
            {"name": "Winchester Action on Climate Change"},
            {"name": "Zap Map"},
        ]
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class ContactView(CheckForDownPageMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/contact.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Contact"
        context["current_page"] = "contact-page"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HowToUseView(CheckForDownPageMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/how-to-use-the-scorecards.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "How to use the Scorecards"
        context["current_page"] = "how-to-page"
        return context
