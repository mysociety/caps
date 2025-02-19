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
    PrivateScorecardsAccessMixin,
    SearchAutocompleteMixin,
)
from scoring.models import (
    PlanQuestion,
    PlanQuestionGroup,
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
    next_page = "scoring:home"  # used if no ?next= query param
    template_name = "scoring/login.html"


class LogoutView(LogoutView):
    next_page = "scoring:home"  # used if no ?next= query param


class PrivacyView(TemplateView):
    template_name = "scoring/privacy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Privacy Policy"
        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HomePageView(
    PrivateScorecardsAccessMixin,
    SearchAutocompleteMixin,
    AdvancedFilterMixin,
    FilterView,
):
    filterset_class = PlanScoreFilter

    def get_template_names(self):
        scoring_group_slug = self.get_scoring_group()["slug"]
        if scoring_group_slug == "combined":
            return ["scoring/home_combined.html"]

        return ["scoring/home.html"]

    def get_scoring_group(self):
        scoring_group_slug = self.kwargs.get("council_type", "")
        try:
            group = Council.SCORING_GROUPS[scoring_group_slug]
        except:
            group = Council.SCORING_GROUPS["single"]

        return group

    def get_queryset(self):
        scoring_group = self.get_scoring_group()
        filters = {
            "year": self.request.year,
            "council__authority_type__in": scoring_group["types"],
        }

        if self.request.GET.get("country", None) is None:
            filters["council__country__in"] = scoring_group["countries"]

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

    def get_missing_councils(self, council_ids, scoring_group):
        filter_params = ["region", "county"]

        filters = {
            "authority_type__in": scoring_group["types"],
            "end_date__isnull": True,
        }

        for f in filter_params:
            if self.request.GET.get(f, None) is not None:
                filters[f] = self.request.GET[f]

        if self.request.GET.get("country", None) is None:
            filters["country__in"] = scoring_group["countries"]
        else:
            filters["country__in"] = self.request.GET["country"]

        missing_councils = Council.objects.exclude(id__in=council_ids).filter(**filters)

        return missing_councils

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        scoring_group = self.get_scoring_group()

        councils = context["object_list"].values()
        context["plan_sections"] = PlanSection.objects.filter(
            year=self.request.year
        ).all()

        context = self.setup_filter_context(context, context["filter"], scoring_group)

        averages = PlanSection.get_average_scores(
            scoring_group=scoring_group,
            filter=context.get("filter_params", None),
            year=self.request.year,
        )
        all_scores = PlanSectionScore.get_all_council_scores(
            plan_year=self.request.year
        )

        councils = list(councils.all())
        council_ids = []
        for council in councils:
            council_ids.append(council["council_id"])
            council["all_scores"] = all_scores[council["council_id"]]
            if council["score"] is not None:
                council["percentage"] = council["score"]
            else:
                council["percentage"] = 0

        if context.get("filter_params", None) is None:
            missing_councils = self.get_missing_councils(council_ids, scoring_group)

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
        codes = PlanSection.section_codes(year=self.request.year)

        if scoring_group["slug"] == "combined":
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
                    key=lambda council: (
                        0
                        if council["score"] == 0 or council["score"] is None
                        else council["all_scores"][sort]["score"]
                    ),
                    reverse=True,
                )
                councils = sorted(councils, key=itemgetter("slug"))
        else:
            form = form_class()

        context["scoring_group"] = scoring_group

        context["form"] = form
        context["sorted_by"] = sorted_by
        context["council_data"] = councils
        context["averages"] = averages
        context["current_plan_year"] = False
        context["plan_year"] = self.request.year
        context["council_link_template"] = (
            "scoring/includes/council_link_with_year.html"
        )
        context["section_link_template"] = (
            "scoring/includes/section_link_with_year.html"
        )
        if self.request.year == settings.PLAN_YEAR:
            context["current_plan_year"] = True
            context["council_link_template"] = (
                "scoring/includes/council_link_current.html"
            )
            context["section_link_template"] = (
                "scoring/includes/section_link_current.html"
            )

        title_format_strings = {
            "single": "Council Climate Action Scorecards",
            "district": "{name} Councils’ Climate Action Scorecards",
            "county": "{name} Councils’ Climate Action Scorecards",
            "combined": "{name} Climate Action Scorecards",
            "northern-ireland": "{name} Councils’ Climate Action Scorecards",
        }

        context["page_title"] = title_format_strings[scoring_group["slug"]].format(
            name=scoring_group["name"]
        )
        context["site_title"] = "Climate Emergency UK"

        context["current_page"] = "home-page"
        context["canonical_path"] = self.request.path

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class CouncilView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, DetailView):
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
            "evidence_links": question.evidence_links_cleaned,
        }
        if question.question_type == "HEADER":
            q["max"] = question.header_max

        return q

    # TODO: unhardcode dates based on plan year
    def is_active_council(self, council):
        new_council_date = date(year=2023, month=1, day=1)
        is_active = True
        inactive_type = ""
        if council.start_date is not None and council.start_date >= new_council_date:
            inactive_type = "new_council"
            is_active = False

        old_council_date = date(year=2021, month=4, day=1)
        if council.end_date is not None and council.end_date <= old_council_date:
            inactive_type = "old_council"
            is_active = False

        return is_active, inactive_type

    def get_comparison_data(self):
        comparison_slugs = self.request.GET.getlist("comparisons")
        comparisons = None
        comparison_answers = defaultdict(dict)
        comparison_sections = {}
        if comparison_slugs:
            comparisons = (
                PlanScore.objects.select_related("council")
                .filter(council__slug__in=comparison_slugs, year=self.request.year)
                .annotate(
                    previous_total=Subquery(
                        PlanScore.objects.filter(
                            id=OuterRef("previous_year__id"),
                        ).values("weighted_total")
                    )
                )
                .annotate(
                    change=(
                        (
                            (F("weighted_total") - F("previous_total"))
                            / F("previous_total")
                        )
                        * 100
                    )
                )
                .order_by("council__name")
            )
            comparison_sections = PlanSectionScore.sections_for_plans(
                plans=comparisons,
                plan_year=self.request.year,
                previous_year=True,
            )

            comparison_ids = [p.id for p in comparisons]
            if len(comparison_ids) > 0:
                for question in PlanScore.questions_answered_for_councils(
                    plan_ids=comparison_ids, plan_year=self.request.year
                ):
                    q = self.make_question_obj(question)
                    comparison_answers[question.code][question.council_name] = q
                prev_plans = PlanScore.objects.filter(id__in=comparison_ids).values(
                    "previous_year_id", "previous_year__year"
                )
                ids = []
                year = None
                for plan in prev_plans:
                    ids.append(plan["previous_year_id"])
                    year = plan["previous_year__year"]

                for question in PlanScore.questions_answered_for_councils(
                    plan_ids=ids, plan_year=year
                ):
                    if comparison_answers[question.code].get(question.council_name):
                        comparison_answers[question.code][question.council_name][
                            "previous_score"
                        ] = question.score
                        comparison_answers[question.code][question.council_name][
                            "previous_max"
                        ] = question.max_score
                        comparison_answers[question.code][question.council_name][
                            "change"
                        ] = (
                            comparison_answers[question.code][question.council_name][
                                "score"
                            ]
                            - question.score
                        )

        return comparisons, comparison_answers, comparison_sections

    def get_section_details(self, plan_score, group, comparisons, comparison_sections):
        sections = PlanSectionScore.sections_for_council(
            council=plan_score.council,
            plan_year=plan_score.year,
            previous_year=plan_score.previous_year,
        )

        for section in sections.keys():
            sections[section]["non_negative_max"] = sections[section]["score"]
            sections[section]["negative_points"] = 0

        # get average section scores for authorities of the same type
        section_avgs = PlanSectionScore.get_all_section_averages(
            council_group=group, plan_year=self.request.year
        )
        for section in section_avgs.all():
            sections[section["plan_section__code"]]["avg"] = round(
                section["avg_score"], 1
            )

        section_top_marks = PlanSectionScore.get_all_section_top_mark_counts(
            council_group=group, plan_year=self.request.year
        )
        for section in section_top_marks.all():
            sections[section["plan_section__code"]]["max_count"] = section[
                "max_score_count"
            ]

        for section, details in comparison_sections.items():
            sections[section]["comparisons"] = details

        return sections

    def add_answer_details(
        self, plan_score, group, sections, comparisons, comparison_answers
    ):
        question_max_counts = PlanQuestionScore.all_question_max_score_counts(
            council_group=group, plan_year=self.request.year
        )

        previous_questions = defaultdict(dict)
        if plan_score.previous_year is not None:
            prev_answers = plan_score.previous_year.questions_answered()
            for pa in prev_answers:
                previous_questions[pa.section_code][pa.code] = pa

        for question in plan_score.questions_answered():
            section = question.section_code

            q = self.make_question_obj(question)
            if previous_questions[section].get(q["code"]):
                pq = previous_questions[section][q["code"]]
                q["previous_score"] = pq.score
                q["previous_max"] = pq.max_score
                q["change"] = q["score"] - q["previous_score"]

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
                        data["negative_points"] / data["max_score"]
                    ) * -100
                else:
                    data["only_negative"] = True
            data["answers"] = sorted(data["answers"], key=natsort)

        return sections

    def get_related_councils(self, council, group, comparisons):
        similar_councils = []
        for group in council.get_related_councils(5, group["slug"]):
            if group["type"].slug == "composite":
                if comparisons:
                    # Filter out any related councils that are already being compared
                    comparison_slugs = {score.council.slug for score in comparisons}
                    similar_councils = [
                        sc
                        for sc in group["councils"]
                        if sc.slug not in comparison_slugs
                    ]
                else:
                    similar_councils = group["councils"]
                break

        return similar_councils

    def add_previous_scores(self, council, context, plan_score):
        try:
            original_plan_score = PlanScore.objects.get(council=council, year=2021)
            context["original_plan_score"] = original_plan_score
        except PlanScore.DoesNotExist:
            context["original_plan_score"] = False

        if plan_score.previous_year is not None:
            prev = plan_score.previous_year
            context["previous_total"] = prev.weighted_total
            context["previous_diff"] = (
                (plan_score.weighted_total - prev.weighted_total) / prev.weighted_total
            ) * 100
        else:
            context["previous_total"] = False

        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council = context.get("council")
        group = council.get_scoring_group()

        context["scoring_group"] = group
        context["plan_year"] = self.request.year

        is_active, inactive_type = self.is_active_council(council)
        if not is_active:
            context[inactive_type] = True
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
            plan_score = PlanScore.objects.get(council=council, year=self.request.year)
        except PlanScore.DoesNotExist:
            context["no_plan"] = True
            return context

        plan_urls = PlanScoreDocument.objects.filter(plan_score=plan_score)

        context = self.add_previous_scores(council, context, plan_score)

        comparisons, comparison_answers, comparison_sections = (
            self.get_comparison_data()
        )

        sections = self.get_section_details(
            plan_score, group, comparisons, comparison_sections
        )

        sections = self.add_answer_details(
            plan_score, group, sections, comparisons, comparison_sections
        )

        council_count = PlanScore.objects.filter(
            year=self.request.year,
            council__authority_type__in=group["types"],
            council__country__in=group["countries"],
        ).count()

        context["canonical_path"] = self.request.path
        context["council_count"] = council_count
        context["plan_score"] = plan_score
        context["plan_urls"] = plan_urls
        context["plan_year"] = self.request.year
        context["sections"] = sorted(
            sections.values(), key=lambda section: section["code"]
        )
        context["comparisons"] = comparisons
        context["similar_councils"] = self.get_related_councils(
            council, group, comparisons
        )

        context["page_title"] = "{name} Climate Action Scorecard".format(
            name=council.name
        )

        context["page_description"] = (
            "Want to know how effective {name}’s climate plans are? Check out {name}’s Council Climate Scorecard to understand how their climate plans compare to local authorities across the UK.".format(
                name=council.name
            )
        )
        context["twitter_tweet_text"] = (
            "Up to 30% of the UK’s transition to zero carbon is within the influence of local councils - that’s why I’m checking {name}’s Climate Action Plan on 📋 #CouncilClimateScorecards".format(
                name=(
                    "@{}".format(council.twitter_name)
                    if council.twitter_name
                    else council.name
                )
            )
        )
        context["og_image_path"] = (
            f"{settings.MEDIA_URL}scoring/og-images/councils/{council.slug}.png"
        )
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
        plan_score = PlanScore.objects.get(council=council, year=self.request.year)
        max_score, min_score = self.get_high_low_scores(plan_score)

        words = council.name.split()
        last_two_words = f"{words[-2]} {words[-1]}"
        if len(last_two_words) < 16:
            context["add_nosplit_span"] = True

        context["page_title"] = council.name
        context["plan_score"] = plan_score
        context["scoring_group"] = council.get_scoring_group()
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
            year=self.request.year,
            council__authority_type__in=group["types"],
            council__country__in=group["countries"],
        ).order_by("-weighted_total")

        top = scores.first()
        council = top.council

        context["page_title"] = council.name
        context["scoring_group"] = group
        context["council"] = council
        context["score"] = top.weighted_total
        context["plan_year"] = self.request.year

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
        context["plan_year"] = self.request.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, DetailView):
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

    social_graphics = {
        "s4_g_f": {
            "pdf": {
                "src_pdf": "scoring/img/social-graphics/governance-and-finance/scorecards-governance.pdf",
                "src_jpg": "scoring/img/social-graphics/governance-and-finance/governance-graphic.jpg",
                "height": 1159,
                "width": 2100,
            },
            "zip": "scoring/img/social-graphics/governance-and-finance/governance-and-finance.zip",
            "images": [
                {
                    "src_facebook": "scoring/img/social-graphics/governance-and-finance/facebook-1@2x.png",
                    "src_instagram": "scoring/img/social-graphics/governance-and-finance/instagram-1@2x.png",
                    "alt": "Governance & Finance; Leading the Way; 68% of local authorities have raised funds for climate action; 84% of councils have a named climate portfolio holder; 45% of councils include climate as a priority in their Corporate Plan.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/governance-and-finance/facebook-2@2x.png",
                    "src_instagram": "scoring/img/social-graphics/governance-and-finance/instagram-2@2x.png",
                    "alt": "Governance & Finance; Climate Governance; 14% of councils have trained all their senior staff and councillors who are cabinet or committee chairs in climate awareness; 64% of councils don’t have a detailed sustainable procurement policy; 47% of councils list climate implications on full council decisions.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/governance-and-finance/facebook-3@2x.png",
                    "src_instagram": "scoring/img/social-graphics/governance-and-finance/instagram-3@2x.png",
                    "alt": "Governance & Finance; Funding the Climate Crisis; 1% of councils have committed to divesting their pension fund from fossil fuels by 2030; 13% of councils have passed a motion supporting the divestment of its own investments and their pension fund; 10% of local authorities* have direct investments in airports.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/governance-and-finance/facebook-4@2x.png",
                    "src_instagram": "scoring/img/social-graphics/governance-and-finance/instagram-4@2x.png",
                    "alt": "Governance & Finance; Emissions Reductions Between 2019 and 2021; 7% of councils have reduced their own emissions by 20% or more; 2% of district & single tier councils have had area wide emissions reduced by 10% or more; 0% No county, combined authority or Northern Irish council have had area wide emissions reduced by 10% or more.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/governance-and-finance/facebook-0@2x.png",
                    "src_instagram": "scoring/img/social-graphics/governance-and-finance/instagram-0@2x.png",
                    "alt": "Governance & Finance; Average scores: 27% for Single Tier; 24% for District; 34% for County; 11% for Northern Ireland; 29% for Combined Authority.",
                },
            ],
        },
        "s2_tran": {
            "pdf": {
                "src_pdf": "scoring/img/social-graphics/transport/scorecards-transport.pdf",
                "src_jpg": "scoring/img/social-graphics/transport/transport-graphic.jpg",
                "height": 1158,
                "width": 2100,
            },
            "zip": "scoring/img/social-graphics/transport/transport.zip",
            "images": [
                {
                    "src_facebook": "scoring/img/social-graphics/transport/facebook-1@2x.png",
                    "src_instagram": "scoring/img/social-graphics/transport/instagram-1@2x.png",
                    "alt": "Transport, leading the way; 57% of transport authorities have 20mph as the default speed limit; 59% of transport authorities have low-emission buses in their area",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/transport/facebook-2@2x.png",
                    "src_instagram": "scoring/img/social-graphics/transport/instagram-2@2x.png",
                    "alt": "Transport, driving the climate crisis; 25% of local authorities have expanded airports or their road networks",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/transport/facebook-3@2x.png",
                    "src_instagram": "scoring/img/social-graphics/transport/instagram-3@2x.png",
                    "alt": "Transport, accelerated action needed; 20% of local authorities have 10% or more of their council fleet as electric vehicles; 32% of councils have 60 or more public electric vehicle chargers across their area",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/transport/facebook-4@2x.png",
                    "src_instagram": "scoring/img/social-graphics/transport/instagram-4@2x.png",
                    "alt": "Transport, driving the climate crisis; 0 english councils received the highest capability rating by active travel england; 3 english transport authorities outside of london have high bus ridership.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/transport/facebook-5@2x.png",
                    "src_instagram": "scoring/img/social-graphics/transport/instagram-5@2x.png",
                    "alt": "Transport, air quality; 98% of air quality authorities in england have high pm2.5 levels in 25% or more of the council's area; 55% of air quality authorities have high no2 levels in 25% or more of the council's area",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/transport/facebook-6@2x.png",
                    "src_instagram": "scoring/img/social-graphics/transport/instagram-6@2x.png",
                    "alt": "Transport; Average scores: 22% for Single Tier; 9% for District; 18% for County; 7% for Northern Ireland; 41% for Combined Authority",
                },
            ],
        },
        "s2_tran_ca": {
            "pdf": {
                "src_pdf": "scoring/img/social-graphics/ca-transport/scorecards-ca-transport.pdf",
                "src_jpg": "scoring/img/social-graphics/ca-transport/ca-transport-graphic.jpg",
                "height": 1125,
                "width": 2000,
            },
            "zip": "scoring/img/social-graphics/ca-transport/transport.zip",
            "images": [
                {
                    "src_facebook": "scoring/img/social-graphics/ca-transport/facebook-1@2x.png",
                    "src_instagram": "scoring/img/social-graphics/ca-transport/instagram-1@2x.png",
                    "alt": "Transport, 100% support shared transport schemes like car clubs; 82% include climate as a priority in their Transport Plan; 36% have integrated ticketing for all public transport and shared active travel schemes.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/ca-transport/facebook-2@2x.png",
                    "src_instagram": "scoring/img/social-graphics/ca-transport/instagram-2@2x.png",
                    "alt": "Transport, 0% have a capability rating of 4 out of 4 from Active Travel England; 36% have more than 60 public EV chargers per 100,000 residents; 27% have a clean air zone that requires charges for private vehicles.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/ca-transport/facebook-3@2x.png",
                    "src_instagram": "scoring/img/social-graphics/ca-transport/instagram-3@2x.png",
                    "alt": "Transport, 73% included high carbon transport projects within their Transport plans.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/ca-transport/facebook-4@2x.png",
                    "src_instagram": "scoring/img/social-graphics/ca-transport/instagram-4@2x.png",
                    "alt": "Transport, 91% have a target for a zero emission bus fleet by 2040 or sooner; 27% have a target of 2030 for zero emission bus fleet.",
                },
            ],
        },
        "s1_b_h": {
            "pdf": {
                "src_pdf": "scoring/img/social-graphics/building-and-heating/building-and-heating-graphic.pdf",
                "src_jpg": "scoring/img/social-graphics/building-and-heating/building-and-heating-graphic.jpg",
                "height": 1125,
                "width": 2000,
            },
            "zip": "scoring/img/social-graphics/building-and-heating/building-and-heating.zip",
            "images": [
                {
                    "src_facebook": "scoring/img/social-graphics/building-and-heating/facebook-1@2x.png",
                    "src_instagram": "scoring/img/social-graphics/building-and-heating/instagram-1@2x.png",
                    "alt": "Building & Heating, Leading the Way; 96% of local authorities offer funding to residents to retrofit their homes; 59% of councils have a renewable energy tariff or generate renewable energy equal to 20% of their own energy use",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/building-and-heating/facebook-2@2x.png",
                    "src_instagram": "scoring/img/social-graphics/building-and-heating/instagram-2@2x.png",
                    "alt": "Building & Heating, Leading the Way; Only Greater Manchester Combined Authority scored 100% in Buildings & Heating",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/building-and-heating/facebook-3@2x.png",
                    "src_instagram": "scoring/img/social-graphics/building-and-heating/instagram-3@2x.png",
                    "alt": "Building & Heating, Room for Improvement; 59% of local authorities have at least one part-time retrofit staff member; 48% of local authorities support residents to collectively purchase renewable energy",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/building-and-heating/facebook-31@2x.png",
                    "alt": "Building & Heating, Room for Improvement; 71% of council owned social housing is energy efficient, EPC band C or higher; 5/11 combined authorities trained over 1,000 people in green skills",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/building-and-heating/facebook-4@2x.png",
                    "src_instagram": "scoring/img/social-graphics/building-and-heating/instagram-4@2x.png",
                    "alt": "Building & Heating, Falling Behind; 75% of single tier & district councils are not actively enforcing Minimum Energy Efficiency Standards of privately rented homes in 2021/22; 24% of local authorities provide support for local community renewable energy creation",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/building-and-heating/facebook-5@2x.png",
                    "src_instagram": "scoring/img/social-graphics/building-and-heating/instagram-5@2x.png",
                    "alt": "Building & Heating, Falling Behind; 43% of UK homes are energy efficient, rated EPC C or higher",
                },
            ],
        },
        "s3_p_lu": {
            "pdf": {
                "src_pdf": "scoring/img/social-graphics/planning-and-land-use/planning-and-land-use-graphic.pdf",
                "src_jpg": "scoring/img/social-graphics/planning-and-land-use/planning-and-land-use-graphic.jpg",
                "height": 1125,
                "width": 2000,
            },
            "zip": "scoring/img/social-graphics/planning-and-land-use/planning-and-land-use.zip",
            "images": [
                {
                    "src_facebook": "scoring/img/social-graphics/planning-and-land-use/facebook-1@2x.png",
                    "src_instagram": "scoring/img/social-graphics/planning-and-land-use/instagram-1@2x.png",
                    "alt": "Planning & Land Use; 59% of planning authorities set the highest water efficiency standards for new builds. 42% of planning authorities avoid building new developments on land that is most at risk of flooding.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/planning-and-land-use/facebook-2@2x.png",
                    "src_instagram": "scoring/img/social-graphics/planning-and-land-use/instagram-2@2x.png",
                    "alt": "Planning & Land Use; 14% of planning authorities have set net zero standards for building new housing; 19% of planning authorities require the measurement of a development’s embodied emissions; 46% of planning authorities require onsite renewable energy in new developments",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/planning-and-land-use/facebook-3@2x.png",
                    "src_instagram": "scoring/img/social-graphics/planning-and-land-use/instagram-3@2x.png",
                    "alt": "Planning & Land Use; 58% of planning authorities have mapped where new solar, wind, or district heating infrastructure can be built, but only 8% have mapped for all three. 33% of English, Scottish, and Welsh councils have approved 3 or more renewable energy projects.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/planning-and-land-use/facebook-4@2x.png",
                    "src_instagram": "scoring/img/social-graphics/planning-and-land-use/instagram-4@2x.png",
                    "alt": "Planning & Land Use; 11 mineral planning authorities have approved new, or the expansion of fossil fuel infrastructure.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/planning-and-land-use/facebook-5@2x.png",
                    "src_instagram": "scoring/img/social-graphics/planning-and-land-use/instagram-5@2x.png",
                    "alt": "Planning & Land Use; Average scores: 35% Single tier, 23% District, -25% County, 14% Northern Ireland",
                },
            ],
        },
        "s6_c_e": {
            "pdf": {
                "src_pdf": "scoring/img/social-graphics/collaboration-and-engagement/collaboration-and-engagement.pdf",
                "src_jpg": "scoring/img/social-graphics/collaboration-and-engagement/collaboration-and-engagement.jpg",
                "height": 1158,
                "width": 2100,
            },
            "zip": "scoring/img/social-graphics/collaboration-and-engagement/collaboration-and-engagement.zip",
            "images": [
                {
                    "src_facebook": "scoring/img/social-graphics/collaboration-and-engagement/facebook-1@2x.png",
                    "src_instagram": "scoring/img/social-graphics/collaboration-and-engagement/instagram-1@2x.png",
                    "alt": "Collaboration & Engagement; 79% of councils have a Climate Action Plan with SMART targets",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/collaboration-and-engagement/facebook-2@2x.png",
                    "src_instagram": "scoring/img/social-graphics/collaboration-and-engagement/instagram-2@2x.png",
                    "alt": "Collaboration & Engagement; 63% of councils published an annual Climate Action Update report; 53% of councils have ongoing ways for residents to influence Climate Action Plan development; 43% of local authorities have lobbied the UK or devolved governments for further climate action",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/collaboration-and-engagement/facebook-3@2x.png",
                    "src_instagram": "scoring/img/social-graphics/collaboration-and-engagement/instagram-3@2x.png",
                    "alt": "Collaboration & Engagement; 10 out of 11 Mayoral Authorities have three or more active schemes providing support or tailored advice to businesses in the local area to help them decarbonise",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/collaboration-and-engagement/facebook-4@2x.png",
                    "src_instagram": "scoring/img/social-graphics/collaboration-and-engagement/instagram-4@2x.png",
                    "alt": "Collaboration & Engagement; 5 out of 11 Mayoral Authorities have published a study of different decarbonisation pathways and scenarios to reach net zero",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/collaboration-and-engagement/facebook-5@2x.png",
                    "src_instagram": "scoring/img/social-graphics/collaboration-and-engagement/instagram-5@2x.png",
                    "alt": "Collaboration & Engagement; Average scores by council type: 53% Single Tier; 43% District; 60% County; 23% Northern Ireland; 55% Combined Authority",
                },
            ],
        },
        "s5_bio": {
            "pdf": {
                "src_pdf": "scoring/img/social-graphics/biodiversity/biodiversity-graphic.pdf",
                "src_jpg": "scoring/img/social-graphics/biodiversity/biodiversity-graphic@2x.jpg",
                "height": 1125,
                "width": 2000,
            },
            "zip": "scoring/img/social-graphics/biodiversity/biodiversity.zip",
            "images": [
                {
                    "src_facebook": "scoring/img/social-graphics/biodiversity/facebook-1@2x.png",
                    "src_instagram": "scoring/img/social-graphics/biodiversity/instagram-1@2x.png",
                    "alt": "Biodiversity - Enhancing Habitat. 80% of local authorities have reduced mowing or created wildflower habitat in their area. 49% of local authorities turn off or dim their street lighting, including 86% of county councils",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/biodiversity/facebook-2@2x.png",
                    "src_instagram": "scoring/img/social-graphics/biodiversity/instagram-2@2x.png",
                    "alt": "Biodiversity - Enhancing Habitat. 6 out of 11 combined authorities provide significant funding for biodiversity",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/biodiversity/facebook-3@2x.png",
                    "src_instagram": "scoring/img/social-graphics/biodiversity/instagram-3@2x.png",
                    "alt": "Biodiversity - Room for Improvement. 6% of councils have stopped using all pesticides. 5% of planning authorities have set a higher minimum standard than the 10% Biodiversity Net Gain for new developments. 17% of councils have a tree cover target and a tree management plan",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/biodiversity/facebook-4@2x.png",
                    "src_instagram": "scoring/img/social-graphics/biodiversity/instagram-4@2x.png",
                    "alt": "Biodiversity - Mayoral Authorities. 32% of local authorities employ a planning ecologist to enforce Biodiversity Net Gain to new developments",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/biodiversity/facebook-5@2x.png",
                    "src_instagram": "scoring/img/social-graphics/biodiversity/instagram-5@2x.png",
                    "alt": "Biodiversity - Average Scores by Council Type. 27% Single Tier. 30% County. 55% Combined Authority. 22% District. 38% Northern Ireland",
                },
            ],
        },
        "s7_wr_f": {
            "pdf": {
                "src_pdf": "scoring/img/social-graphics/waste-reduction-and-food/waste-reduction-and-food-graphic.pdf",
                "src_jpg": "scoring/img/social-graphics/waste-reduction-and-food/waste-reduction-and-food-graphic@2x.jpg",
                "height": 1125,
                "width": 2000,
            },
            "zip": "scoring/img/social-graphics/waste-reduction-and-food/waste-reduction-and-food.zip",
            "images": [
                {
                    "src_facebook": "scoring/img/social-graphics/waste-reduction-and-food/facebook-1@2x.png",
                    "src_instagram": "scoring/img/social-graphics/waste-reduction-and-food/instagram-1@2x.png",
                    "alt": "Waste Reduction and Food - Leading the Way. 61% of local authorities provide kerbside food waste recycling to most homes. 57% of local authorities support community food growing initiatives. 43% of local authorities support food surplus redistributions initiatives.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/waste-reduction-and-food/facebook-2@2x.png",
                    "src_instagram": "scoring/img/social-graphics/waste-reduction-and-food/instagram-2@2x.png",
                    "alt": "Waste Reduction and Food - Room for Improvement. 29% of local authorities are part of a sustainable food partnership. 26% of local authorities support circular economy initiatives. 24% of single tier and county councils provide at least one complete vegetarian meal in schools each week.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/waste-reduction-and-food/facebook-3@2x.png",
                    "src_instagram": "scoring/img/social-graphics/waste-reduction-and-food/instagram-3@2x.png",
                    "alt": "Waste Reduction and Food - Falling Behind. 84% of local authorities don't have a sustainable food strategy. 70% of local authorities recycle less than half of their waste from residents. 94% of local authorities send to landfill or incinerate over 300kg of waste per household each year.",
                },
                {
                    "src_facebook": "scoring/img/social-graphics/waste-reduction-and-food/facebook-4@2x.png",
                    "src_instagram": "scoring/img/social-graphics/waste-reduction-and-food/instagram-4@2x.png",
                    "alt": "Waste Reduction and Food - Average Scores by Council Type. Single Tier councils score 37%, District councils score 23%, County councils score 30%, and Northern Ireland councils score 35%",
                },
            ],
        },
    }

    alt_map = dict((ca, non_ca) for non_ca, ca in combined_alt_map.items())

    def get_object(self):
        return get_object_or_404(
            PlanSection, code=self.kwargs["code"], year=self.request.year
        )

    def add_comparisons(self, context, comparison_slugs, comparison_questions):
        section = context["section"]
        comparisons = None
        if comparison_slugs:
            comparisons = (
                PlanScore.objects.select_related("council")
                .filter(year=self.request.year, council__slug__in=comparison_slugs)
                .order_by("council__name")
            )
            comparison_sections = PlanSectionScore.sections_for_plans(
                plans=comparisons,
                plan_year=self.request.year,
                plan_sections=PlanSection.objects.filter(code=section.code),
            )

            first_comparison = comparison_slugs[0]

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

                        # need to add this manually to the section question object so it displays
                        # the evidence if it's relevant
                        if score["council_slug"] == first_comparison:
                            comparison_questions[code][
                                "evidence_links"
                            ] = answer.evidence_links_cleaned

                    else:
                        comparison_questions[code]["comparisons"].append({"score": "-"})
                        comparison_questions[code]["evidence_links"] = []

                if score["negative_points"] < 0:
                    score["negative_percent"] = (
                        round((score["negative_points"] / score["max_score"]) * 100, 0)
                        * -1
                    )

            context["comparison_councils"] = comparisons
            context["comparison_scores"] = comparison_scores

    def get_questions(self, context):
        section = context["section"]

        natsort = gen_natsort_lamda()

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

            council_count = (
                Council.objects.filter(
                    authority_type__in=council_type["types"],
                    country__in=council_type["countries"],
                )
                .exclude(end_date__isnull=False)
                .exclude(start_date__gt=settings.RECENTLY_ADDED_COUNCILS)
                .count()
            )
            context["council_count"] = council_count

            try:
                council_group = PlanQuestionGroup.objects.get(
                    description=council_type["slug"]
                )
                questions = PlanQuestion.objects.filter(
                    section=section, questiongroup=council_group
                )
            except PlanQuestionGroup.DoesNotExist:
                questions = PlanQuestion.objects.filter(section=section)

            for question in questions:
                comparison_questions[question.code] = {
                    "details": question,
                    "evidence_links": "CouncilTypeOnly",
                    "comparisons": [],
                }

            question_max_counts = PlanQuestionScore.all_question_max_score_counts(
                council_group=council_type, plan_year=self.request.year
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

        sg = self.social_graphics.get(section.code, None)
        if sg:
            context["social_graphics"] = sg
            context["og_image_path"] = f"{settings.STATIC_URL}{sg['pdf']['src_jpg']}"
            context["og_image_type"] = "image/jpeg"
            context["og_image_height"] = sg["pdf"]["height"]
            context["og_image_width"] = sg["pdf"]["width"]

        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionsView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, TemplateView):
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
        for section in (
            PlanSection.objects.filter(year=self.request.year).order_by("code").all()
        ):
            if self.request.year == settings.PLAN_YEAR:
                url = reverse("scoring:section", args=(section.code,))
            else:
                url = reverse(
                    "year_scoring:section",
                    args=(
                        self.request.year,
                        section.code,
                    ),
                )
            details = {
                "name": section.description,
                "url": url,
                "description": section.long_description,
            }
            if section.code in self.sections:
                context["sections"].append(details)
            elif section.code in self.ca_sections:
                context["ca_sections"].append(details)

        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionPreview(PrivateScorecardsAccessMixin, TemplateView):
    template_name = "scoring/section-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]
        scoring_group_slug = self.kwargs["type"]

        group = Council.SCORING_GROUPS[scoring_group_slug]

        section = PlanSection.objects.get(code=code, year=self.request.year)

        scores = PlanSectionScore.objects.filter(
            plan_section=section,
            plan_score__year=self.request.year,
            plan_score__council__authority_type__in=group["types"],
            plan_score__council__country__in=group["countries"],
        ).aggregate(
            maximum=Max("weighted_score"),
            minimum=Min("weighted_score"),
            average=Avg("weighted_score"),
        )

        context["section"] = section
        context["scoring_group"] = group
        context["scores"] = scores
        context["plan_year"] = self.request.year

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionTopPerformerPreview(PrivateScorecardsAccessMixin, TemplateView):
    template_name = "scoring/council-top-performer-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]

        section = PlanSection.objects.get(code=code, year=self.request.year)

        scores = PlanSectionScore.objects.filter(
            plan_section=section,
            plan_score__year=self.request.year,
        ).order_by("-weighted_score")

        top = scores.first()

        context["section"] = section
        context["score"] = top.weighted_score
        context["council"] = top.plan_score.council
        context["plan_year"] = self.request.year

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionCouncilTopPerformerPreview(PrivateScorecardsAccessMixin, TemplateView):
    template_name = "scoring/council-top-performer-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]
        council = self.kwargs["council"]

        section = PlanSection.objects.get(code=code, year=self.request.year)

        scores = get_object_or_404(
            PlanSectionScore,
            plan_section=section,
            top_performer=code,
            plan_score__year=self.request.year,
            plan_score__council__slug=council,
        )

        context["section"] = section
        context["score"] = scores.weighted_score
        context["council"] = scores.plan_score.council
        context["plan_year"] = self.request.year

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class QuestionView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, DetailView):
    model = PlanQuestion
    context_object_name = "question"
    template_name = "scoring/question.html"

    def get_object(self):
        return get_object_or_404(
            PlanQuestion.objects.select_related("section"),
            code=self.kwargs["code"],
            section__year=self.request.year,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        question = context["question"]
        context["page_title"] = question.text

        context["applicable_scoring_groups"] = question.questiongroup.all()
        scoring_group = None

        # If question only applies to a single authority type,
        # assume the user wants to see that.
        if context["applicable_scoring_groups"].count() == 1:
            scoring_group = Council.SCORING_GROUPS[
                context["applicable_scoring_groups"][0].description
            ]

        # Otherwise, see whether they’ve provided a valid
        # scoring group slug as a query param in the URL.
        elif self.request.GET.get("type") in Council.SCORING_GROUPS:
            scoring_group = Council.SCORING_GROUPS[self.request.GET.get("type")]

        if scoring_group is not None:
            context["scoring_group"] = scoring_group
            context["scores"] = (
                PlanQuestionScore.objects.filter(
                    plan_score__year=self.request.year,
                    plan_question=question,
                    plan_score__council__authority_type__in=scoring_group["types"],
                )
                .select_related("plan_score", "plan_score__council")
                .order_by("-score", "plan_score__council__name")
            )

            score_counts = question.get_scores_breakdown(
                year=self.request.year, scoring_group=scoring_group
            )

            totals = {}

            # make sure we display all possible scores for positive marks
            if question.question_type != "negative":
                for score in range(question.max_score + 1):
                    totals[score] = {
                        "score": score,
                        "count": 0,
                    }

            for score in score_counts:
                totals[score["score"]] = {
                    "score": score["score"],
                    "count": score["score_count"],
                }

            context["totals"] = [totals[k] for k in sorted(totals.keys())]

        context["plan_year"] = self.request.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class LocationResultsView(PrivateScorecardsAccessMixin, BaseLocationResultsView):
    template_name = "scoring/location_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Choose a council"
        context["plan_year"] = self.request.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class AboutView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "About"
        context["current_page"] = "about-page"
        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year
        context["year_content"] = f"scoring/includes/{self.request.year}_about.html"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class MethodologyView(
    PrivateScorecardsAccessMixin, SearchAutocompleteMixin, TemplateView
):
    template_name = "scoring/methodology.html"

    def get_question_number(self, question):
        code = question.code
        code = code.replace(question.section.code, "")
        code = code.replace("_q", "")
        return code

    def get_question_removed(self, question):
        if question.section.year == 2025 and question.code == "s7_wr_f_q1a":
            return "This question has been removed due to changes in UK law making it a legal requirement to ban the use and sale of some single use plastic"
        return ""

    def get_question_exceptions(self, question):
        if question.section.year == 2025:
            if question.code == "s2_tran_q6":
                return "This question doesn’t apply to London Boroughs, the GLA, or councils in Scotland or Wales"
            elif question.code == "s2_tran_8b":
                return "This question only applies to councils in England"
            elif question.code == "s5_bio_q4":
                return "This question only applies to councils in England"
            elif question.code == "s1_b_h_q8":
                return "This question only applies to councils in England and Wales"
            elif question.code == "s7_w_f_q1b":
                return "This question does not apply to County councils"
        return ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Methodology"
        context["current_page"] = "methodology-page"

        methodology_year = self.request.year
        if kwargs.get("year") is None:
            methodology_year = settings.METHODOLOGY_YEAR

        context["methodology_year"] = methodology_year
        context["toc_template"] = f"scoring/methodology/{methodology_year}/_toc.html"
        context["intro_template"] = (
            f"scoring/methodology/{methodology_year}/_intro.html"
        )
        context["details_template"] = (
            f"scoring/methodology/{methodology_year}/_details.html"
        )

        questions = (
            PlanQuestion.objects.filter(section__year=methodology_year)
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
                "removed": self.get_question_removed(question),
                "exceptions": self.get_question_exceptions(question),
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
            {"name": "WasteDataFlow"},
            {"name": "Wirral Environmental Network"},
            {"name": "Wildlife & Countryside Link"},
            {"name": "Winchester Action on Climate Change"},
            {"name": "Zap Map"},
        ]

        context["canonical_path"] = self.request.path
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class ContactView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/contact.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Contact"
        context["current_page"] = "contact-page"
        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HowToUseView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/how-to-use-the-scorecards.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "How to use the Scorecards"
        context["current_page"] = "how-to-page"
        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year
        return context


class NotFoundPageView(SearchAutocompleteMixin, TemplateView):
    page_title = "Page not found"
    template_name = "scoring/404.html"

    def render_to_response(self, context, **response_kwargs):
        response_kwargs.setdefault("content_type", self.content_type)
        return self.response_class(
            request=self.request,
            template=self.get_template_names(),
            context=context,
            using=self.template_engine,
            status=404,
            **response_kwargs,
        )
