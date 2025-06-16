import re
from collections import defaultdict
from copy import deepcopy
from datetime import date
from operator import itemgetter

from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Avg, Count, F, Max, Min, OuterRef, Subquery, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, resolve_url, reverse
from django.templatetags.static import static
from django.utils.decorators import method_decorator
from django.utils.text import Truncator
from django.views.decorators.cache import cache_control
from django.views.generic import DetailView, TemplateView
from django_filters.views import FilterView

import scoring.defaults as defaults
from caps.models import Council, PlanDocument, Promise
from caps.utils import gen_natsort_lamda
from caps.views import BaseLocationResultsView
from conf.social_graphics import social_graphics
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
        context["plan_year"] = self.request.year.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HomePageView(
    PrivateScorecardsAccessMixin,
    SearchAutocompleteMixin,
    AdvancedFilterMixin,
    FilterView,
):
    filterset_class = PlanScoreFilter
    template_name = "scoring/home.html"

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
            "year": self.request.year.year,
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
            .order_by(F("weighted_total").desc(nulls_last=True), "council__name")
        )

        if self.request.year.previous_year:
            qs = qs.annotate(
                previous_percentage=Subquery(
                    PlanScore.objects.filter(
                        council=OuterRef("council"),
                        year=self.request.year.previous_year.year,
                    ).values("weighted_total")
                ),
                change=(F("weighted_total") - F("previous_percentage")),
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
            year=self.request.year.year
        ).all()

        context = self.setup_filter_context(context, context["filter"], scoring_group)

        averages = PlanSection.get_average_scores(
            scoring_group=scoring_group,
            filter=context.get("filter_params", None),
            year=self.request.year.year,
        )
        all_scores = PlanSectionScore.get_all_council_scores(
            plan_year=self.request.year.year, as_list=True
        )

        if self.request.year.previous_year:
            previous_averages = PlanSection.get_average_scores(
                scoring_group=scoring_group,
                filter=context.get("filter_params", None),
                year=self.request.year.previous_year.year,
            )
            for section in averages.keys():
                if section != "total" and previous_averages.get(section):
                    averages[section]["change"] = (
                        averages[section]["weighted"]
                        - previous_averages[section]["weighted"]
                    )

        section_averages = []
        for code in sorted(averages.keys()):
            if code != "total":
                section_averages.append(averages[code])

        councils = list(councils.all())
        council_ids = []
        out = True
        for council in councils:
            council_ids.append(council["council_id"])
            if out:
                out = False
            council["all_scores"] = all_scores[council["council_id"]]
            if council["score"] is not None:
                council["percentage"] = council["score"]
            else:
                council["percentage"] = 0
            if (
                council.get("previous_percentage") is None
                or council["previous_percentage"] == 0
            ):
                council["change"] = None

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
        codes = PlanSection.section_codes(year=self.request.year.year)

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
        context["section_averages"] = section_averages
        context["current_plan_year"] = False
        context["plan_year"] = self.request.year.year
        context["previous_year"] = self.request.year.previous_year
        context["council_link_template"] = (
            "scoring/includes/council_link_with_year.html"
        )
        context["section_link_template"] = (
            "scoring/includes/section_link_with_year.html"
        )
        if self.request.year.is_current:
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
        if not self.request.year.is_current:
            context["page_title"] = f"{self.request.year.year} {context['page_title']}"

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

        if question.previous_question_code:
            q["previous_q_code"] = question.previous_question_code

        return q

    def is_active_council(self, council):
        is_active = True
        inactive_type = ""
        if (
            council.start_date is not None
            and council.start_date >= self.request.year.new_council_date
        ):
            inactive_type = "new_council"
            is_active = False

        if (
            council.end_date is not None
            and council.end_date <= self.request.year.old_council_date
        ):
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
                .filter(council__slug__in=comparison_slugs, year=self.request.year.year)
                .annotate(
                    previous_total=Subquery(
                        PlanScore.objects.filter(
                            id=OuterRef("previous_year__id"),
                        ).values("weighted_total")
                    )
                )
                .annotate(change=(F("weighted_total") - F("previous_total")))
                .order_by("council__name")
            )
            comparison_sections = PlanSectionScore.sections_for_plans(
                plans=comparisons,
                plan_year=self.request.year.year,
                previous_year=True,
            )

            comparison_ids = [p.id for p in comparisons]
            if len(comparison_ids) > 0:
                for question in PlanScore.questions_answered_for_councils(
                    plan_ids=comparison_ids, plan_year=self.request.year.year
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

                previous_answers = defaultdict(dict)
                for question in PlanScore.questions_answered_for_councils(
                    plan_ids=ids, plan_year=year
                ):
                    previous_answers[question.code][question.council_name] = {}
                    previous_answers[question.code][question.council_name][
                        "previous_score"
                    ] = question.score
                    previous_answers[question.code][question.council_name][
                        "previous_max"
                    ] = question.max_score

                for code in comparison_answers.keys():
                    for council, answer in comparison_answers[code].items():
                        prev_code = answer.get("previous_question_code")
                        if prev_code and previous_answers[prev_code].get(council):
                            answer = {**answer, **previous_answers[prev_code][council]}
                            answer["change"] = int(
                                answer["score"] - answer["previous_score"]
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
            council_group=group, plan_year=self.request.year.year
        )
        for section in section_avgs.all():
            sections[section["plan_section__code"]]["avg"] = round(
                section["avg_score"], 1
            )

        section_top_marks = PlanSectionScore.get_all_section_top_mark_counts(
            council_group=group, plan_year=self.request.year.year
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
            council_group=group, plan_year=self.request.year.year
        )

        previous_questions = defaultdict(dict)
        if plan_score.previous_year is not None:
            prev_answers = plan_score.previous_year.questions_answered()
            for pa in prev_answers:
                previous_questions[pa.section_code][pa.code] = pa

        for question in plan_score.questions_answered():
            section = question.section_code

            q = self.make_question_obj(question)
            if q.get("previous_q_code") and previous_questions[section].get(
                q["previous_q_code"]
            ):
                pq = previous_questions[section][q["previous_q_code"]]
                q["previous_score"] = pq.score
                q["previous_max"] = pq.max_score
                q["change"] = int(q["score"] - q["previous_score"])

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

        if (
            plan_score.previous_year is not None
            and plan_score.previous_year.weighted_total is not None
            and plan_score.previous_year.weighted_total > 0
        ):
            prev = plan_score.previous_year
            context["previous_year"] = prev.year
            context["previous_total"] = prev.weighted_total
            context["previous_diff"] = plan_score.weighted_total - prev.weighted_total
        else:
            context["previous_total"] = False

        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council = context.get("council")
        group = council.get_scoring_group()

        context["scoring_group"] = group
        context["plan_year"] = self.request.year.year

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
            plan_score = PlanScore.objects.get(
                council=council, year=self.request.year.year
            )
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
            plan_score, group, sections, comparisons, comparison_answers
        )

        council_count = PlanScore.objects.filter(
            year=self.request.year.year,
            council__authority_type__in=group["types"],
            council__country__in=group["countries"],
        ).count()

        context["canonical_path"] = self.request.path
        context["council_count"] = council_count
        context["plan_score"] = plan_score
        context["plan_urls"] = plan_urls
        context["plan_year"] = self.request.year.year
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
            f"{settings.MEDIA_URL}scoring/og-images/councils/{self.request.year.year}/{council.slug}.png"
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
        plan_score = PlanScore.objects.get(council=council, year=self.request.year.year)
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


class MostImprovedBase(DetailView):
    def calculate_change(self, current_score, previous_score):
        return current_score - previous_score

    def get_changes(self, plan_score, previous_year):
        previous_plan_score = PlanScore.objects.get(
            council=plan_score.council, year=previous_year
        )
        previous_score = previous_plan_score.weighted_total

        change = self.calculate_change(plan_score.weighted_total, previous_score)

        return previous_score, change

    def add_nosplit_span(self, council):
        add_nosplit_span = False
        words = council.name.split()
        last_two_words = f"{words[-2]} {words[-1]}"
        if len(last_two_words) < 16:
            add_nosplit_span = True

        return add_nosplit_span

    def add_common_context(self, context, previous_year, council):
        context["add_nosplit_span"] = self.add_nosplit_span(council)
        context["plan_year"] = self.request.year.year
        context["previous_year"] = previous_year
        context["council"] = council
        context["page_title"] = council.name

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class OverallMostImproved(MostImprovedBase):
    model = PlanScore
    context_object_name = "plan_score"
    template_name = "scoring/overall-most-improved.html"

    def get_object(self, queryset=None):
        plan_score = get_object_or_404(
            PlanScore,
            year=self.request.year.year,
            most_improved="overall",
        )

        return plan_score

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan_score = context.get("plan_score")
        previous_year = self.kwargs["previous_year"]

        council = plan_score.council
        last_score, change = self.get_changes(plan_score, previous_year)

        context = self.add_common_context(context, previous_year, council)
        context["current_score"] = plan_score.weighted_total
        context["last_score"] = last_score
        context["change"] = change
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class CouncilMostImproved(MostImprovedBase):
    model = PlanScore
    context_object_name = "plan_score"
    template_name = "scoring/council-most-improved.html"

    def get_object(self, queryset=None):
        group = Council.SCORING_GROUPS[self.kwargs["group"]]
        plan_score = (
            PlanScore.objects.filter(
                year=self.request.year.year,
                council__authority_type__in=group["types"],
                council__country__in=group["countries"],
                most_improved__in=[
                    group["slug"],
                    "overall",
                    "England",
                    "Wales",
                    "Scotland",
                    "Northern Ireland",
                ],
            )
            .annotate(
                previous_total=Subquery(
                    PlanScore.objects.filter(
                        id=OuterRef("previous_year__id"),
                    ).values("weighted_total")
                )
            )
            .annotate(change=(F("weighted_total") - F("previous_total")))
            .order_by("-change")
        )

        return plan_score.first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan_score = context.get("plan_score")
        previous_year = self.kwargs["previous_year"]

        council = plan_score.council
        last_score, change = self.get_changes(plan_score, previous_year)

        context = self.add_common_context(context, previous_year, council)

        if self.kwargs["group"] == "northern-ireland":
            context["add_nosplit_span"] = False

        context["current_score"] = plan_score.weighted_total
        context["scoring_group"] = council.get_scoring_group()
        context["last_score"] = last_score
        context["change"] = change
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionMostImproved(MostImprovedBase):
    model = PlanSectionScore
    context_object_name = "section_score"
    template_name = "scoring/section-most-improved.html"

    def get_object(self, queryset=None):
        section = self.kwargs["section"]
        try:
            plan_score = (
                PlanSectionScore.objects.filter(
                    plan_score__year=self.request.year.year,
                    most_improved=section,
                )
                .annotate(
                    previous_score=Subquery(
                        PlanSectionScore.objects.filter(
                            plan_section__code=section,
                            plan_score__council=OuterRef("plan_score__council"),
                            plan_score__year=self.request.year.previous_year.year,
                        ).values("weighted_score")
                    ),
                    change=(F("weighted_score") - F("previous_score")),
                )
                .order_by("change")
                .first()
            )
        except PlanSectionScore.DoesNotExist:
            raise Http404

        return plan_score

    def get_changes(self, section_score, previous_year):
        previous_section_score = PlanSectionScore.objects.get(
            plan_score__council=section_score.plan_score.council,
            plan_section__code=section_score.plan_section.code,
            plan_score__year=previous_year,
        )
        previous_score = previous_section_score.weighted_score

        change = self.calculate_change(section_score.weighted_score, previous_score)

        return previous_score, change

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section_score = context.get("section_score")
        section_code = self.kwargs["section"]
        previous_year = self.kwargs["previous_year"]

        section = get_object_or_404(
            PlanSection, year=self.request.year.year, code=section_code
        )
        council = section_score.plan_score.council
        last_score, change = self.get_changes(section_score, previous_year)

        context = self.add_common_context(context, previous_year, council)

        context["section"] = section
        context["current_score"] = section_score.weighted_score
        context["scoring_group"] = council.get_scoring_group()
        context["last_score"] = last_score
        context["change"] = change
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class CouncilTypeTopPerformerView(TemplateView):
    template_name = "scoring/council-top-performer-overall-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council_type = self.kwargs["council_type"]
        group = Council.SCORING_GROUPS[council_type]
        scores = PlanScore.objects.filter(
            year=self.request.year.year,
            council__authority_type__in=group["types"],
            council__country__in=group["countries"],
        ).order_by("-weighted_total")

        top = scores.first()
        council = top.council

        context["page_title"] = council.name
        context["scoring_group"] = group
        context["council"] = council
        context["score"] = top.weighted_total
        context["plan_year"] = self.request.year.year

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

    alt_map = dict((ca, non_ca) for non_ca, ca in combined_alt_map.items())

    def get_object(self):
        return get_object_or_404(
            PlanSection, code=self.kwargs["code"], year=self.request.year.year
        )

    def add_comparisons(self, context, comparison_slugs, comparison_questions):
        section = context["section"]
        comparisons = None
        previous_year = None
        if comparison_slugs:
            comparisons = (
                PlanScore.objects.select_related("council")
                .filter(year=self.request.year.year, council__slug__in=comparison_slugs)
                .order_by("council__name")
            )
            previous_year = comparisons.first().previous_year
            comparison_sections = PlanSectionScore.sections_for_plans(
                plans=comparisons,
                plan_year=self.request.year.year,
                plan_sections=PlanSection.objects.filter(code=section.code),
                previous_year=previous_year,
            )

            first_comparison = comparison_slugs[0]

            comparison_scores = comparison_sections[section.code]

            for score in comparison_scores:
                answers = {
                    answer.plan_question.code: answer
                    for answer in score["section_score"].questions_answered(
                        prev_year=score["section_score"].plan_score.previous_year
                    )
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

            context["previous_year"] = previous_year
            context["comparison_councils"] = comparisons
            context["comparison_scores"] = comparison_scores

    def get_questions(self, context):
        section = context["section"]

        natsort = gen_natsort_lamda()

        removed_qs = defaults.get_config("REMOVED_QUESTIONS", self.request.year.year)

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
                if removed_qs and removed_qs.get(question.code):
                    comparison_questions[question.code]["removed"] = removed_qs.get(
                        question.code
                    )

            question_max_counts = PlanQuestionScore.all_question_max_score_counts(
                council_group=council_type, plan_year=self.request.year.year
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
            if context.get("current_plan_year"):
                url = reverse("scoring:section", args=(alt.code,))
            else:
                url = reverse(
                    "year_scoring:section",
                    args=(
                        self.request.year.year,
                        alt.code,
                    ),
                )

            context["alternative"] = {
                "name": alt.description,
                "url": url,
            }

        self.get_questions(context)

        avgs = section.get_averages_by_council_group()
        avgs["ni"] = avgs["northern-ireland"]
        context["averages"] = avgs
        if context.get("council_type", None) is not None:
            context["council_type_avg"] = avgs[context["council_type"]["slug"]]

        if social_graphics.get(self.request.year.year):
            sg = social_graphics[self.request.year.year].get(section.code)
            if sg:
                context["social_graphics"] = sg
                context["og_image_path"] = (
                    f"{settings.STATIC_URL}{sg['pdf']['src_jpg']}"
                )
                context["og_image_type"] = "image/jpeg"
                context["og_image_height"] = sg["pdf"]["height"]
                context["og_image_width"] = sg["pdf"]["width"]

        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year.year
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
            PlanSection.objects.filter(year=self.request.year.year)
            .order_by("code")
            .all()
        ):
            if self.request.year.is_current:
                url = reverse("scoring:section", args=(section.code,))
            else:
                url = reverse(
                    "year_scoring:section",
                    args=(
                        self.request.year.year,
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
        context["plan_year"] = self.request.year.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionPreview(PrivateScorecardsAccessMixin, TemplateView):
    template_name = "scoring/section-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]
        scoring_group_slug = self.kwargs["type"]

        group = Council.SCORING_GROUPS[scoring_group_slug]

        section = PlanSection.objects.get(code=code, year=self.request.year.year)

        scores = PlanSectionScore.objects.filter(
            plan_section=section,
            plan_score__year=self.request.year.year,
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
        context["plan_year"] = self.request.year.year

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionTopPerformerPreview(PrivateScorecardsAccessMixin, TemplateView):
    template_name = "scoring/council-top-performer-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]

        section = PlanSection.objects.get(code=code, year=self.request.year.year)

        scores = PlanSectionScore.objects.filter(
            plan_section=section,
            plan_score__year=self.request.year.year,
        ).order_by("-weighted_score")

        top = scores.first()

        context["section"] = section
        context["score"] = top.weighted_score
        context["council"] = top.plan_score.council
        context["plan_year"] = self.request.year.year

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionCouncilTopPerformerPreview(PrivateScorecardsAccessMixin, TemplateView):
    template_name = "scoring/council-top-performer-preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        code = self.kwargs["slug"]
        council = self.kwargs["council"]

        section = PlanSection.objects.get(code=code, year=self.request.year.year)

        scores = get_object_or_404(
            PlanSectionScore,
            plan_section=section,
            top_performer=code,
            plan_score__year=self.request.year.year,
            plan_score__council__slug=council,
        )

        context["section"] = section
        context["score"] = scores.weighted_score
        context["council"] = scores.plan_score.council
        context["plan_year"] = self.request.year.year

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
            section__year=self.request.year.year,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        question = context["question"]
        context["page_title"] = question.text
        context["plan_year"] = self.request.year.year

        context["applicable_scoring_groups"] = question.questiongroup.all()
        scoring_group = None

        removed = None
        removed_qs = defaults.get_config("removed_questions", self.request.year.year)
        if removed_qs and removed_qs.get(question.code):
            removed = removed_qs[question.code]

        if removed:
            context["question_removed"] = removed
            return context

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

        previous_q = None
        previous_q_overriden = False
        previous_q_overrides = defaults.get_config(
            "previous_q_overrides", self.request.year.year, default=[]
        )

        # this is a temporary fix for transport Q8 county councils because a number of councils
        # were no longer eligible for this due to changed criteria
        if (
            self.request.year.year == 2025
            and question.section.description == "Transport"
            and scoring_group
            and scoring_group["name"] == "County"
        ):
            previous_q_overrides.extend(["s2_tran_q5a", "s2_tran_q5b"])

        if scoring_group is not None:
            context["scoring_group"] = scoring_group
            context["scores"] = (
                PlanQuestionScore.objects.filter(
                    plan_score__year=self.request.year.year,
                    plan_question=question,
                    plan_score__council__authority_type__in=scoring_group["types"],
                )
                .select_related("plan_score", "plan_score__council")
                .order_by("-score", "plan_score__council__name")
            )

            prev_counts = None
            if self.request.year.previous_year:
                context["scores"] = (
                    context["scores"]
                    .annotate(
                        previous_score=Subquery(
                            PlanQuestionScore.objects.filter(
                                plan_question__code=self.kwargs["code"],
                                plan_score__year=2023,
                                plan_score__council=OuterRef("plan_score__council"),
                            ).values("score")
                        )
                    )
                    .annotate(change=(F("score") - F("previous_score")))
                )

                context["increased"] = 0
                context["decreased"] = 0
                for score in context["scores"]:
                    if score.change is not None:
                        if score.change > 0:
                            context["increased"] += 1
                        elif score.change < 0:
                            context["decreased"] += 1

                previous_q = context["question"].previous_question
                if previous_q and previous_q.code in previous_q_overrides:
                    previous_q = None
                    previous_q_overriden = True

                if previous_q:
                    prev_counts = previous_q.get_scores_breakdown(
                        year=self.request.year.previous_year.year,
                        scoring_group=scoring_group,
                    )

            score_counts = question.get_scores_breakdown(
                year=self.request.year.year, scoring_group=scoring_group
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

                if prev_counts:
                    for score in prev_counts:
                        if not totals.get(score["score"]):
                            continue
                        totals[score["score"]]["prev_count"] = score["score_count"]
                        totals[score["score"]]["change"] = (
                            totals[score["score"]]["count"] - score["score_count"]
                        )

                    for score in totals.keys():
                        if not totals[score].get("prev_count"):
                            totals[score]["prev_count"] = 0
                            totals[score]["change"] = totals[score]["count"]

                context["totals"] = [totals[k] for k in sorted(totals.keys())]
            else:
                totals[0] = {
                    "score": 0,
                    "count": 0,
                }
                totals["negative"] = {
                    "score": -1,
                    "count": 0,
                }
                for score in score_counts:
                    if score["score"] < 0:
                        totals["negative"]["count"] += score["score_count"]
                    else:
                        totals[score["score"]] = {
                            "score": score["score"],
                            "count": score["score_count"],
                        }
                if prev_counts:
                    print(prev_counts)
                    totals["negative"]["prev_count"] = 0
                    totals[0]["prev_count"] = 0

                    for score in prev_counts:
                        if score["score"] < 0:
                            totals["negative"]["prev_count"] += score["score_count"]
                        else:
                            totals[score["score"]]["prev_count"] = score["score_count"]

                    for score in totals.keys():
                        totals[score]["change"] = (
                            totals[score]["count"] - totals[score]["prev_count"]
                        )

                context["totals"] = [totals["negative"], totals[0]]

        if not previous_q:
            if previous_q_overriden:
                context["comparison_overridden"] = True
            context["no_comparison"] = True
        elif previous_q.max_score != context["question"].max_score:
            context["max_score_changed"] = True

        if self.request.year.previous_year:
            context["previous_year"] = self.request.year.previous_year.year

        if (
            context.get("previous_year")
            and not context.get("no_comparison")
            and not context.get("max_score_changed")
        ):
            context["display_comparison"] = True
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class LocationResultsView(PrivateScorecardsAccessMixin, BaseLocationResultsView):
    template_name = "scoring/location_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Choose a council"
        context["plan_year"] = self.request.year.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class AboutView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "About"
        context["current_page"] = "about-page"
        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year.year
        context["year_content"] = (
            f"scoring/includes/{self.request.year.year}_about.html"
        )
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

        methodology_year = self.request.year.year
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
                    "weightings": defaults.get_config(
                        "section_weightings", self.request.year.year
                    )[question.section.description],
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

        context["organisations"] = defaults.get_config(
            "organisations", self.request.year.year
        )

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
        context["plan_year"] = self.request.year.year
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HowToUseView(PrivateScorecardsAccessMixin, SearchAutocompleteMixin, TemplateView):
    template_name = "scoring/how-to-use-the-scorecards.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "How to use the Scorecards"
        context["current_page"] = "how-to-page"
        context["canonical_path"] = self.request.path
        context["plan_year"] = self.request.year.year
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
