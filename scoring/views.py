from django.views.generic import DetailView, TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Subquery, OuterRef, Avg, Count, Sum
from django.shortcuts import resolve_url
from django.utils.text import Truncator
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control

from django_filters.views import FilterView

from caps.models import Council, Promise
from scoring.models import (
    PlanScore,
    PlanScoreDocument,
    PlanSection,
    PlanSectionScore,
    PlanQuestion,
    PlanQuestionScore,
)
from scoring.filters import PlanScoreFilter, QuestionScoreFilter

from scoring.forms import ScoringSort

from caps.views import BaseLocationResultsView
from scoring.mixins import CheckForDownPageMixin, AdvancedFilterMixin

cache_settings = {
    "max-age": 60,
    "s-maxage": 3600,
}


class DownPageView(TemplateView):
    template_name = "scoring/down.html"


class LoginView(LoginView):
    next_page = "home"
    template_name = "scoring/login.html"

    def get_success_url(self):
        return resolve_url(self.next_page)


class LogoutView(LogoutView):
    next_page = "home"


@method_decorator(cache_control(**cache_settings), name="dispatch")
class HomePageView(CheckForDownPageMixin, AdvancedFilterMixin, FilterView):
    filterset_class = PlanScoreFilter
    template_name = "scoring/home.html"

    def get_authority_type(self):
        authority_type = self.kwargs.get("council_type", "")
        try:
            group = Council.SCORING_GROUPS[authority_type]
        except:
            group = Council.SCORING_GROUPS["single"]

        return group

    def get_queryset(self):
        authority_type = self.get_authority_type()
        qs = Council.objects.annotate(
            score=Subquery(
                PlanScore.objects.filter(council_id=OuterRef("id"), year="2021").values(
                    "weighted_total"
                )
            ),
            top_performer=Subquery(
                PlanScore.objects.filter(council_id=OuterRef("id"), year="2021").values(
                    "top_performer"
                )
            ),
        ).order_by("-score")

        qs = qs.filter(
            authority_type__in=authority_type["types"],
            country__in=authority_type["countries"],
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
            council["all_scores"] = all_scores[council["id"]]
            if council["score"] is not None:
                council["percentage"] = council["score"]
            else:
                council["percentage"] = 0

        codes = PlanSection.section_codes()

        form = ScoringSort(self.request.GET)
        if form.is_valid():
            sort = form.cleaned_data["sort_by"]
            if sort != "":
                councils = sorted(
                    councils,
                    key=lambda council: 0
                    if council["score"] == 0
                    else council["all_scores"][sort]["score"],
                    reverse=True,
                )
        else:
            form = ScoringSort()

        context["authority_type"] = authority_type["slug"]
        context["authority_type_label"] = authority_type["name"]

        context["form"] = form
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
    template_name = "scoring/council.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete

        council = context.get("council")
        promises = Promise.objects.filter(council=council).all()

        plan_score = PlanScore.objects.get(council=council, year=2021)

        plan_urls = PlanScoreDocument.objects.filter(plan_score=plan_score)

        section_qs = PlanSectionScore.objects.select_related("plan_section").filter(
            plan_score__council=council, plan_section__year=2021
        )

        sections = {}
        for section in section_qs.all():
            sections[section.plan_section.code] = {
                "top_performer": section.top_performer,
                "code": section.plan_section.code,
                "description": section.plan_section.description,
                "max_score": section.max_score,
                "score": section.score,
                "answers": [],
            }

        group = council.get_scoring_group()

        # get average section scores for authorities of the same type
        section_avgs = (
            PlanSectionScore.objects.select_related("plan_section")
            .filter(
                plan_score__total__gt=0,
                plan_score__council__authority_type__in=group["types"],
                plan_score__council__country__in=group["countries"],
                plan_section__year=2021,
            )
            .values("plan_section__code")
            .annotate(avg_score=Avg("score"))
        )  # , distinct=True))

        for section in section_avgs.all():
            sections[section["plan_section__code"]]["avg"] = round(
                section["avg_score"], 1
            )

        # do this in raw SQL as otherwise we need a third query and an extra loop below
        questions = PlanQuestion.objects.raw(
            "select q.id, q.code, q.text, q.question_type, q.max_score, s.code as section_code, a.answer, a.score \
            from scoring_planquestion q join scoring_plansection s on q.section_id = s.id \
            left join scoring_planquestionscore a on q.id = a.plan_question_id \
            where s.year = '2021' and ( a.plan_score_id = %s or a.plan_score_id is null) and (q.question_type = 'HEADER' or a.plan_question_id is not null)\
            order by q.code",
            [plan_score.id],
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
                "answer": question.answer or "-",
                "score": question.score or 0,
            }
            sections[section]["answers"].append(q)

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
    template_name = "scoring/question.html"
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
                plan_question__code__contains=question.code,
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

        overall_totals = Council.objects.filter(
            authority_type__in=authority_type["types"],
            country__in=authority_type["countries"],
        ).annotate(
            total=Subquery(
                PlanQuestionScore.objects.filter(
                    plan_question__parent=question.code,
                    plan_score__council=OuterRef("id"),
                )
                .values("plan_score__council")
                .annotate(
                    total=Sum("score"),
                )
                .values("total")
            ),
            max_total=Subquery(
                PlanQuestionScore.objects.filter(
                    plan_question__parent=question.code,
                    plan_score__council=OuterRef("id"),
                )
                .values("plan_score__council")
                .annotate(
                    total=Sum("plan_question__max_score"),
                )
                .values("total")
            ),
        )

        if q_filter.is_valid():
            council_scores = q_filter.filter_queryset(council_scores)
            score_counts = q_filter.filter_queryset(score_counts)
            c_filter.is_valid()
            council_total = c_filter.filter_queryset(council_total)
            overall_totals = c_filter.filter_queryset(overall_totals)

        council_count = council_total.count()

        overall_stats = (
            overall_totals.values("total", "max_total")
            .annotate(total_count=Count("pk"))
            .order_by("total")
        )

            overall = []
            for score in overall_stats:
                overall.append(
                    {
                        "total": score["total_count"],
                        "score": score["total"],
                        "max_total": score["max_total"],
                        "percentage": round(
                            (score["total_count"] / council_count) * 100
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

        context["authority_type"] = authority_type["slug"]
        context["question"] = question
        context["council_count"] = council_count
        context["sub_questions"] = questions
        context["overall_totals"] = overall_totals
        context["overall_stats"] = overall
        context["page_title"] = Truncator(question.text).chars(75)
        context["filter"] = q_filter
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class LocationResultsView(CheckForDownPageMixin, BaseLocationResultsView):
    template_name = "scoring/location_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "Choose a council"
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class MethodologyView(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/methodology.html"

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
    template_name = "scoring/about.html"

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
    template_name = "scoring/contact.html"

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
    template_name = "scoring/how-to-use-the-scorecards.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "How to use the Scorecards"
        context["current_page"] = "how-to-page"
        return context
