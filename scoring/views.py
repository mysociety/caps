from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Subquery, OuterRef, Q, Avg
from django.shortcuts import redirect, resolve_url

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
from scoring.filters import PlanScoreFilter

from scoring.forms import ScoringSort

from caps.views import BaseLocationResultsView
from scoring.mixins import CheckForDownPageMixin


class DownPageView(TemplateView):
    template_name = "scoring/down.html"


class LoginView(LoginView):
    next_page = "home"
    template_name = "scoring/login.html"

    def get_success_url(self):
        return resolve_url(self.next_page)


class LogoutView(LogoutView):
    next_page = "home"


class HomePageView(CheckForDownPageMixin, FilterView):
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

        if getattr(context["filter"].form, "cleaned_data", None) is not None:
            params = context["filter"].form.cleaned_data
            descs = []
            if params["population"] and params["population"] != "":
                descs.append(params["population"])
            if params["control"] and params["control"] != "":
                descs.append(params["control"])
            if params["ruc_cluster"] and params["ruc_cluster"] != "":
                descs.append(PlanScore.ruc_cluster_description(params["ruc_cluster"]))
            if params["imdq"] and params["imdq"] != "":
                descs.append("deprivation quintile {}".format(params["imdq"]))
            if params["country"] and params["country"] != "":
                descs.append(Council.country_description(params["country"]))

            context["filter_params"] = params
            context["filter_descs"] = descs

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
        context["population_filter"] = PlanScore.POPULATION_FILTER_CHOICES[
            authority_type["slug"]
        ]
        context["urbanisation_filter"] = PlanScore.RUC_TYPES

        context["form"] = form
        context["council_data"] = councils
        context["averages"] = averages
        context["page_title"] = "{} councils".format(authority_type["name"])
        context["current_page"] = "home-page"

        return context


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
        context["page_title"] = council.name
        return context


class QuestionView(CheckForDownPageMixin, DetailView):
    model = PlanQuestion
    context_object_name = "question"
    template_name = "scoring/question.html"
    slug_field = "code"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete

        question = context.get("question")

        answers = (
            PlanQuestionScore.objects.filter(plan_question=question)
            .select_related("plan_score", "plan_score__council")
            .order_by("plan_score__council__name")
        )

        context["question"] = question
        context["answers"] = answers
        context["page_title"] = question.code
        return context


class LocationResultsView(CheckForDownPageMixin, BaseLocationResultsView):
    template_name = "scoring/location_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        return context


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


class AboutView(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "About us"
        context["current_page"] = "about-page"
        return context


class ContactView(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/contact.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "Contact us"
        context["current_page"] = "contact-page"
        return context


class HowToUseView(TemplateView):
    template_name = "scoring/how-to-use-the-scorecards.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "How to use the scorecards"
        context["current_page"] = "how-to-page"
        return context
