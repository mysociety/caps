from collections import defaultdict
from datetime import date

from caps.models import Council, Promise
from caps.views import BaseLocationResultsView
from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, F, OuterRef, Subquery, Sum
from django.shortcuts import resolve_url
from django.utils.decorators import method_decorator
from django.utils.text import Truncator
from django.views.decorators.cache import cache_control
from django.views.generic import DetailView, TemplateView
from django_filters.views import FilterView
from scoring.filters import PlanScoreFilter, QuestionScoreFilter
from scoring.forms import ScoringSort
from scoring.mixins import AdvancedFilterMixin, CheckForDownPageMixin
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


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HomePageView(CheckForDownPageMixin, AdvancedFilterMixin, FilterView):
    filterset_class = PlanScoreFilter
    template_name = "scoring2022/home.html"

    def get_authority_type(self):
        authority_type = self.kwargs.get("council_type", "")
        try:
            group = Council.SCORING_GROUPS[authority_type]
        except:
            group = Council.SCORING_GROUPS["single"]

        return group

    def get_queryset(self):
        authority_type = self.get_authority_type()
        qs = (
            PlanScore.objects.filter(
                year=2021,
                council__authority_type__in=authority_type["types"],
                council__country__in=authority_type["countries"],
            )
            .annotate(
                score=F("weighted_total"),
                name=F("council__name"),
                slug=F("council__slug"),
            )
            .order_by(F("weighted_total").desc(nulls_last=True))
        )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete

        authority_type = self.get_authority_type()

        councils = context["object_list"].values()
        context["plan_sections"] = PlanSection.objects.filter(year=2021).all()

        context = self.setup_filter_context(context, context["filter"], authority_type)

        averages = PlanSection.get_average_scores(
            authority_type["slug"], filter=context.get("filter_params", None)
        )
        all_scores = PlanSectionScore.get_all_council_scores()

        for council in councils:
            council["all_scores"] = all_scores[council["council_id"]]
            if council["score"] is not None:
                council["percentage"] = council["score"]
            else:
                council["percentage"] = 0

        codes = PlanSection.section_codes()

        form = ScoringSort(self.request.GET)
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
        else:
            form = ScoringSort()

        context["authority_type"] = authority_type["slug"]
        context["authority_type_label"] = authority_type["name"]

        context["form"] = form
        context["sorted_by"] = sorted_by
        context["council_data"] = councils
        context["averages"] = averages

        title_format_strings = {
            "single": "Council Climate Plan Scorecards",
            "district": "{name} Councils’ Climate Plan Scorecards",
            "county": "{name} Councils’ Climate Plan Scorecards",
            "combined": "{name} Climate Plan Scorecards",
            "northern-ireland": "{name} Councils’ Climate Plan Scorecards",
        }

        context["page_title"] = title_format_strings[authority_type["slug"]].format(
            name=authority_type["name"]
        )
        context["site_title"] = "Climate Emergency UK"

        context["current_page"] = "home-page"

        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class CouncilView(CheckForDownPageMixin, DetailView):
    model = Council
    context_object_name = "council"
    template_name = "scoring2022/council.html"

    def make_question_obj(self, question):
        q = {
            "code": question.code,
            "pretty_code": question.pretty_code(),
            "display_code": question.code.replace(
                "{}_".format(question.section_code), "", 1
            ),
            "question": question.text,
            "type": question.question_type,
            "max": question.max_score,
            "section": question.section_code,
            "answer": question.answer or "-",
            "score": question.score or 0,
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

        context["all_councils"] = Council.objects.filter(
            authority_type__in=group["types"],
            country__in=group["countries"],
            # newer councils don't have a score so don't include them
            start_date__lt="2023-01-01",
        )

        promises = Promise.objects.filter(council=council).all()
        plan_score = PlanScore.objects.get(council=council, year=2021)
        plan_urls = PlanScoreDocument.objects.filter(plan_score=plan_score)
        sections = PlanSectionScore.sections_for_council(
            council=council, plan_year=2021
        )

        # get average section scores for authorities of the same type
        section_avgs = PlanSectionScore.get_all_section_averages(
            council_group=group, plan_year=2021
        )
        for section in section_avgs.all():
            sections[section["plan_section__code"]]["avg"] = round(
                section["avg_score"], 1
            )

        section_top_marks = PlanSectionScore.get_all_section_top_mark_counts(
            council_group=group, plan_year=2021
        )
        for section in section_top_marks.all():
            sections[section["plan_section__code"]]["max_count"] = section[
                "max_score_count"
            ]

        question_max_counts = PlanQuestionScore.all_question_max_score_counts(
            council_group=group, plan_year=2021
        )

        comparison_slugs = self.request.GET.getlist("comparisons")
        comparisons = None
        comparison_answers = defaultdict(list)
        if comparison_slugs:
            comparisons = (
                PlanScore.objects.select_related("council")
                .filter(council__slug__in=comparison_slugs)
                .order_by("council__name")
            )
            comparison_sections = PlanSectionScore.sections_for_plans(
                plans=comparisons, plan_year=2021
            )
            for section, details in comparison_sections.items():
                sections[section]["comparisons"] = details

            comparison_ids = [p.id for p in comparisons]
            for question in PlanScore.questions_answered_for_councils(
                plan_ids=comparison_ids, plan_year=2021
            ):
                q = self.make_question_obj(question)
                comparison_answers[question.code].append(q)

        for question in plan_score.questions_answered():
            section = question.section_code

            q = self.make_question_obj(question)
            q["council_count"] = question_max_counts.get(question.code, 0)
            q["comparisons"] = comparison_answers[question.code]

            sections[section]["answers"].append(q)

        council_count = Council.objects.filter(
            authority_type__in=group["types"],
            country__in=group["countries"],
        ).count()

        context["council_count"] = council_count
        context["targets"] = promises
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
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class QuestionView(CheckForDownPageMixin, AdvancedFilterMixin, DetailView):
    model = PlanQuestion
    context_object_name = "question"
    template_name = "scoring2022/question.html"
    slug_field = "code"

    def get_authority_type(self):
        authority_type = self.request.GET.get("council_type", "")
        try:
            group = Council.SCORING_GROUPS[authority_type]
        except KeyError:
            group = Council.SCORING_GROUPS["single"]

        return group

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete

        filter_args = {
            "data": self.request.GET or None,
            "request": self.request,
        }

        # manually create these filters because we need one for councils and one for
        # questions
        q_filter = QuestionScoreFilter(**filter_args)
        c_filter = PlanScoreFilter(**filter_args)

        question = context.get("question")

        is_header = True
        if question.question_type != "HEADER":
            is_header = False

        authority_type = self.get_authority_type()

        council_total = context["all_councils"].filter(
            authority_type__in=authority_type["types"],
            country__in=authority_type["countries"],
        )

        # set up a queryset to filter the scores table for displaying the list
        # of per question council scores
        council_scores = (
            PlanQuestionScore.objects.filter(
                plan_score__council__authority_type__in=authority_type["types"],
                plan_score__council__country__in=authority_type["countries"],
            )
            .select_related(
                "plan_score",
                "plan_score__council",
                "plan_question",
            )
            .order_by("plan_score__council__name")
        )

        score_counts = (
            PlanQuestionScore.objects.filter(
                plan_question__parent=question.code,
                plan_score__council__authority_type__in=authority_type["types"],
                plan_score__council__country__in=authority_type["countries"],
            )
            .values(
                "score",
                "plan_question__code",
                "plan_question__max_score",
                "plan_question__text",
            )
            .annotate(score_count=Count("pk"))
            .order_by("plan_question__code", "score")
        )

        if is_header:
            overall_totals = PlanQuestionScore.objects.filter(
                plan_question__code=question.code,
                plan_score__council__authority_type__in=authority_type["types"],
                plan_score__council__country__in=authority_type["countries"],
            )

        if q_filter.is_valid():
            council_scores = q_filter.filter_queryset(council_scores)
            score_counts = q_filter.filter_queryset(score_counts)
            c_filter.is_valid()
            council_total = c_filter.filter_queryset(council_total)
            if is_header:
                overall_totals = q_filter.filter_queryset(overall_totals)

        council_count = council_total.count()

        if is_header:
            overall_stats = (
                overall_totals.values(
                    "score",
                    "plan_question__code",
                    "max_score",
                    "plan_question__text",
                )
                .annotate(score_count=Count("pk"))
                .order_by("plan_question__code", "score")
            )

            overall_totals = overall_totals.select_related(
                "plan_score__council"
            ).order_by("plan_score__council__name")

            overall = []
            for score in overall_stats:
                overall.append(
                    {
                        "score": score["score"],
                        "max_total": score["max_score"],
                        "percentage": round(
                            (score["score_count"] / council_count) * 100
                        ),
                    }
                )

        questions = []
        current_question = None
        for score in score_counts.all():
            if (
                current_question is None
                or current_question["code"] != score["plan_question__code"]
            ):
                if current_question is not None:
                    questions.append(current_question)

                current_scores = council_scores.filter(
                    plan_question__code=score["plan_question__code"]
                )
                current_question = {
                    "code": score["plan_question__code"],
                    "text": score["plan_question__text"],
                    "scores": current_scores,
                    "total": current_scores.count(),
                    "stats": [],
                }
            current_question["stats"].append(
                {
                    "score": score["score"],
                    "count": score["score_count"],
                    "percentage": round(
                        (score["score_count"] / current_question["total"]) * 100
                    ),
                    "max_score": score["plan_question__max_score"],
                }
            )

        questions.append(current_question)

        context = self.setup_filter_context(context, q_filter, authority_type)

        if is_header:
            context["overall_totals"] = overall_totals
            context["overall_stats"] = overall
        context["is_header_question"] = is_header
        context["authority_type"] = authority_type["slug"]
        context["question"] = question
        context["council_count"] = council_count
        context["sub_questions"] = questions
        context["page_title"] = Truncator(question.text).chars(75)
        context["filter"] = q_filter
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class LocationResultsView(CheckForDownPageMixin, BaseLocationResultsView):
    template_name = "scoring2022/location_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "Choose a council"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class MethodologyView(CheckForDownPageMixin, TemplateView):
    template_name = "scoring2022/methodology.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete

        # questions = PlanQuestion.objects.all()
        # sections = PlanSection.objects.all()

        section_qs = PlanSection.objects.filter(year=2021)

        sections = {}
        for section in section_qs.all():
            sections[section.code] = {
                "code": section.code,
                "description": section.description,
                "questions": [],
            }

        questions = PlanQuestion.objects.raw(
            "select q.id, q.code, q.text, q.question_type, q.max_score, s.code as section_code \
            from scoring_planquestion q join scoring_plansection s on q.section_id = s.id \
            where s.year = '2021' order by q.code"
        )

        for question in questions:
            section = question.section_code
            q = {
                "code": question.code,
                "pretty_code": question.pretty_code(),
                "display_code": question.code.replace(
                    "{}_".format(question.section_code), "", 1
                ),
                "question": question.text,
                "type": question.question_type,
                "max": question.max_score,
                "section": question.section.code,
            }
            sections[section]["questions"].append(q)

        # context['questions'] = questions
        context["sections"] = sorted(
            sections.values(), key=lambda section: section["code"]
        )
        context["page_title"] = "Methodology"
        context["current_page"] = "methodology-page"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class AboutView(CheckForDownPageMixin, TemplateView):
    template_name = "scoring2022/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "About"
        context["current_page"] = "about-page"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class ContactView(CheckForDownPageMixin, TemplateView):
    template_name = "scoring2022/contact.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "Contact"
        context["current_page"] = "contact-page"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HowToUseView(TemplateView):
    template_name = "scoring2022/how-to-use-the-scorecards.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "How to use the Scorecards"
        context["current_page"] = "how-to-page"
        return context
