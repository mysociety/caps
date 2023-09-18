import re
from collections import defaultdict
from copy import deepcopy
from datetime import date

from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, F, OuterRef, Subquery, Sum
from django.shortcuts import resolve_url, reverse
from django.utils.decorators import method_decorator
from django.utils.text import Truncator
from django.views.decorators.cache import cache_control
from django.views.generic import DetailView, TemplateView
from django_filters.views import FilterView

from caps.models import Council, Promise
from caps.views import BaseLocationResultsView
from scoring.filters import PlanScoreFilter, QuestionScoreFilter
from scoring.forms import ScoringSort
from scoring.mixins import AdvancedFilterMixin, CheckForDownPageMixin
from scoring.models import (PlanQuestion, PlanQuestionScore, PlanScore,
                            PlanScoreDocument, PlanSection, PlanSectionScore)

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
class HomePageView(CheckForDownPageMixin, AdvancedFilterMixin, FilterView):
    filterset_class = PlanScoreFilter

    def get_template_names(self):
        authority_type = self.get_authority_type()["slug"]
        print(authority_type)
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
        qs = (
            PlanScore.objects.filter(
                year=settings.PLAN_YEAR,
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
        context["plan_sections"] = PlanSection.objects.filter(
            year=settings.PLAN_YEAR
        ).all()

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
    template_name = "scoring/council.html"

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
            "negative": question.question_type == "negative",
            # need to do this to make the JS work
            "how_marked": question.how_marked.replace("_", "-"),
            "how_marked_display": question.get_how_marked_display(),
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

        context["all_councils"] = Council.objects.filter(
            authority_type__in=group["types"],
            country__in=group["countries"],
            # newer councils don't have a score so don't include them
            start_date__lt="2023-01-01",
        )

        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete

        promises = Promise.objects.filter(council=council).all()
        plan_score = PlanScore.objects.get(council=council, year=settings.PLAN_YEAR)
        plan_urls = PlanScoreDocument.objects.filter(plan_score=plan_score)
        sections = PlanSectionScore.sections_for_council(
            council=council, plan_year=settings.PLAN_YEAR
        )

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
class SectionView(CheckForDownPageMixin, DetailView):
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
        return PlanSection.objects.get(code=self.kwargs["code"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = context["section"]

        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete

        if section.code.find("_ca") > 0:
            context["section_is_combined"] = True
            alt_section = self.alt_map.get(section.code, None)
            if alt_section is not None:
                alt = PlanSection.objects.get(code=alt_section)
                context["alternative"] = {
                    "name": alt.description,
                    "url": reverse("scoring:section", args=(alt_section,)),
                }
        else:
            ca_alt_section = self.combined_alt_map.get(section.code, None)
            if ca_alt_section is not None:
                alt = PlanSection.objects.get(code=ca_alt_section)
                context["combined_alternative"] = {
                    "name": alt.description,
                    "url": reverse("scoring:section", args=(ca_alt_section,)),
                }

        avgs = section.get_averages_by_council_group()

        avgs["ni"] = avgs["northern-ireland"]
        context["averages"] = avgs
        return context


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SectionsView(CheckForDownPageMixin, TemplateView):
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
        context["sections"] = []
        context["ca_sections"] = []
        for section in PlanSection.objects.all():
            details = {
                "name": section.description,
                "url": reverse("scoring:section", args=(section.code,)),
            }
            if section.code in self.sections:
                context["sections"].append(details)
            elif section.code in self.ca_sections:
                context["ca_sections"].append(details)

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

        section_qs = PlanSection.objects.filter(year=settings.PLAN_YEAR)

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
class Methodology2023View(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/methodology2023.html"

    def get_question_number(self, question):
        code = question.code
        code = code.replace(question.section.code, "")
        code = code.replace("_q", "")
        return code

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "Draft methodology"
        context["current_page"] = "methodology2023-page"

        questions = (
            PlanQuestion.objects.filter(section__year=settings.PLAN_YEAR)
            .select_related("section")
            .order_by("section__code", "code")
        )

        sections = []

        # fix sorting to not have 1, 11, 2
        natsort = lambda q: [
            int(t) if t.isdigit() else t.lower() for t in re.split("(\d+)", q["code"])
        ]

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
                types = [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                ]
                if question.section.code.find("_ca") > 0:
                    types = ["combined"]
                current_section = {
                    "title": question.section.description,
                    "council_types": types,
                    "description": "",
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
