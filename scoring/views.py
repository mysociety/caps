from collections import defaultdict
from datetime import date

from django.views.generic import DetailView, TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Subquery, OuterRef, Count, Sum, F
from django.shortcuts import resolve_url
from django.utils.text import Truncator
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from django.conf import settings

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
    next_page = "scoring:home"
    template_name = "scoring/login.html"

    def get_success_url(self):
        return resolve_url(self.next_page)


class LogoutView(LogoutView):
    next_page = "scoring:home"


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
                PlanScore.objects.filter(
                    council_id=OuterRef("id"), year=settings.PLAN_YEAR
                ).values("weighted_total")
            ),
            top_performer=Subquery(
                PlanScore.objects.filter(
                    council_id=OuterRef("id"), year=settings.PLAN_YEAR
                ).values("top_performer")
            ),
        ).order_by(F("score").desc(nulls_last=True))

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
        context["plan_sections"] = PlanSection.objects.filter(
            year=settings.PLAN_YEAR
        ).all()

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
            council=council, plan_year=settings.PLAN_YEAR
        )

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
        comparison_answers = defaultdict(list)
        if comparison_slugs:
            comparisons = (
                PlanScore.objects.select_related("council")
                .filter(council__slug__in=comparison_slugs)
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
class SectionView(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/section.html"


@method_decorator(cache_control(**cache_settings), name="dispatch")
class SocialMediaView(CheckForDownPageMixin, TemplateView):
    template_name = "scoring/social-media.html"


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[
            "all_councils"
        ] = Council.objects.all()  # for location search autocomplete
        context["page_title"] = "Draft methodology"
        context["current_page"] = "methodology2023-page"
        context["sections"] = [
            {
                "title": "Buildings & Heating",
                "council_types": [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                ],
                "description": "Buildings and Heating is one of the biggest sectors of carbon and other greenhouse gas emissions in the UK. This section aims to cover the main actions that councils can take to support both private rented and owned homes and socially renting households to reduce the emissions from their homes.",
                "weightings": {
                    "single": "20%",
                    "district": "25%",
                    "county": "20%",
                    "northern-ireland": "20%",
                },
                "questions": [
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "1",
                        "name": "Has the council completed extensive retrofit work on any of its significant buildings to make them low carbon?",
                        "topic": "Council buildings - retrofit",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the council have done any of the following extensive retrofit works for any one of its significant buildings:</p>
                            <ul class="mb-3">
                                <li>created on-site renewable energy</li>
                                <li>whole building retrofitting, including heat pump installations</li>
                                <li>extensive insulation of walls and floors</li>
                                <li>replacing gas boilers or installing a combined heating system</li>
                            </ul>
                            <p class="mb-0">Additional points awarded if the retrofit has been awarded a standard such as BREEAM Refurbishment and fit-out (any level), AECB Retrofit standard (Bronze, Silver or Gold) or any other recognised standard.</p>
                            """,
                        "clarifications": """
                            <p>Significant council buildings refers to leisure centres, libraries, council town halls or offices, community centres, schools & colleges (not academies or private schools) or care homes.</p>                                                                     
                            <p>Extensive retrofit (sometimes called deep retrofit) refers to significant works of size or scale that result in a fundamental change to the building structure and/or services. This could be a collection of lots of small retrofit enhancements, or a single larger and disruptive measure, such as installing a combined heat system.</p>
                            <p class="mb-0">The work must be completed, not in progress.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "2",
                        "name": "Are the council’s operations powered by renewable energy?",
                        "topic": "Council buildings - renewable energy tariff",
                        "importance": "Low",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>Criteria met if the council has a green tariff that is 100% renewable or if the council creates its own energy equivalent to 20% of more of its energy consumption through energy from waste.</p>
                            <p class="mb-0">Additional points awarded if the council has a green tariff with Green Energy UK plc, Good Energy Limited or Ecotricity, or if the council creates its own renewable energy equivalent to 20% or its energy consumption. This could be through on-site energy generation, or if the council has built or bought a solar/wind farm elsewhere. </p>
                            """,
                        "clarifications": """
                            <p class="mb-0">This includes all energy that the council is directly responsible for, in council offices and any other buildings leased and managed by the council where the council pays the energy tariff.</p>
                            <p>This includes all electricity used in these buildings (not gas).</p>
                            <p>This does not include homes owned or managed by the council.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district"],
                        "code": "3",
                        "name": "Are the homes owned and managed by the council energy efficient?",
                        "topic": "Council homes - EPC ratings",
                        "importance": "Medium",
                        "how_marked": "FOI",
                        "criteria": """
                            <p><strong>Three Tier Criteria</strong></p>
                            <p>Criteria met if 50% or more of the council’s homes receive C or above in their Environmental Performance Certificate ratings.</p>
                            <p class="mb-0">Additional points awarded if 60% or more, and then if 90% or more of their buildings received C or above EPC ratings.</p>

                            """,
                        "clarifications": """
                            <p>Environmental Performance Certificates (EPCs) show home buyers or tenants how energy efficient the building is. The EPC contains information on potential energy costs and carbon dioxide emissions.</p>
                            <p>Council owned or managed homes includes arms-length management organisation (ALMO) if the homes are owned by the Council but not Housing Associations. </p>
                            <p class="mb-0">This question applies only to homes that councils have an available EPC rating for. This question applies only to councils that own or manage any number of council homes.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district"],
                        "code": "4",
                        "name": "Does the council have a target to retrofit all council owned and managed homes and has this been costed?",
                        "topic": "Homeowner support - retrofit",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Three Tier Criteria</strong></p>
                            <p>Criteria met if the council has completed an exercise to measure how much, approximately, it will cost them to retrofit all homes (to EPC C or higher, or equivalent) and there is a target date provided. </p>
                            <p class="mb-0">Additional points will be awarded depending on the councils’ target dates, with tiers for 2030, 2040 and 2050.</p>

                            """,
                        "clarifications": """
                            <p>Home retrofit is the process of making changes to existing buildings so that energy consumption and emissions are reduced. These changes also provide more comfortable and healthier homes with lower fuel bills.</p>
                            <p>The council doesn’t need to have all the funds available for the retrofit.</p>
                            <p class="mb-0">This question applies only to councils that own or manage any number of homes.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "5",
                        "name": "Is the council part of a programme or partnership to support home retrofitting, through providing the skills and training needed or in other ways?",
                        "topic": "Retrofit partnerships",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <ul class="mb-0">
                                <li>The council convenes or is a member of a local retrofit partnership, that focuses on developing the skills and training needed for retrofit or sharing knowledge around retrofitting. 
                                    Evidence of this partnership is needed. At least two of the following must be visible:</li>
                                    <ol>
                                        <li>A named partnership with a public membership list</li>
                                        <li>A terms of reference or aims of the group</li>
                                        <li>Evidence of previous meetings, via notes, agendas, videos or in news stories</li>
                                    </ol>
                                <li>Alternatively, the criteria will be met if the council convenes or supports a programme for retrofitting locally through providing training or skills support.</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p class="mb-0">The criteria will be met if this partnership is a council task and finish group or sub-committee group with external members.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "6",
                        "name": "Does the council have a staff member employed to work on retrofitting across the council area?",
                        "topic": "Staff working on retrofit",
                        "importance": "Medium",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>Criteria met if a staff member is employed to work on retrofitting for 3 or more days a week and is working on any retrofit projects, including council buildings, council homes or private rented or owned households. </p>
                            <p class="mb-0">Staff can be as a project manager or officer on 3 or more days a week. We would accept contractors as long as they are equivalent to 3 days or more a week (0.6 FTE).</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">The criteria will be met if this partnership is a council task and finish group or sub-committee group with external members.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "northern-ireland"],
                        "code": "7",
                        "name": "Are the homes and buildings in the council area energy efficient?",
                        "topic": "EPC ratings - whole area",
                        "importance": "Low",
                        "how_marked": "National Data",
                        "criteria": """
                            <strong>Three Tier Criteria</strong>
                            <p>Criteria met if 50% or more of buildings in the area that have an EPC rating are rated C or above.</p>
                            <p class="mb-0">Additional points awarded if the more than 60% and then more than 90% of buildings in the area that have an EPC rating are rated C or above.</p>
                            """,
                        "clarifications": """
                            <p>Environmental Performance Certificates (EPCs) show home buyers or tenants how energy efficient the building is. The EPC contains information on potential energy costs and carbon dioxide emissions. </p>
                            <p>Not all buildings in the area have an EPC rating. We will be looking at only the ratings of the buildings that do have a rating. </p>
                            <p class="mb-0">Marked using data provided by UK Government, Scottish EPC Register and the Department of Finance NI</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district"],
                        "england_only": "yes",
                        "wales_apply": "yes",
                        "code": "8",
                        "name": "Is the council actively enforcing Minimum Energy Efficiency Standards of homes in the private rented sector?",
                        "topic": "Housing Efficiency Standards Enforcement",
                        "importance": "High",
                        "how_marked": "FOI",
                        "criteria": """
                            <p><strong>Two Tier Criteria</strong></p>
                            <p>Criteria met if the council has carried out 1-100 compliance or enforcement notices in the last financial year 2021/22.</p>
                            <p class="mb-0">Additional points if more than 100 compliance or enforcement notices have been carried out by a council.</p>
                            """,
                        "clarifications": """
                            <p>This question is applicable to English and Welsh District and Single tier councils only. </p>
                            <p class="mb-0">
                                All district and single tier councils have legal powers to enforce Minimum Energy Efficiency Standards. This legislation states that a home cannot be rented out by a landlord if the home has an EPC rating of E or lower. The council can enforce this requirement through enforcement notices and fining landlords if they continue to rent out homes that have an EPC rating of E or lower. </p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "9",
                        "name": "Does the council provide a service to support private homeowners to make their homes more energy efficient?",
                        "topic": "Homeowner support - retrofit",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria is met if the council is either providing a tailor-made advice to residents on home energy efficiency, or connecting residents with local trades people and suppliers for energy efficiency measures that can be carried out in their homes.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Points will not be awarded for webpages with standardised information on the council website. There must be links to a wider project or product being offered.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "10",
                        "name": "Does the council offer funding to private renters or homeowners to retrofit their homes?",
                        "topic": "Homeowner funding - retrofit",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council provides any amount of funding to any number of private renters, landlords or homeowners to retrofit their homes. This would include grant funding councils have secured from the Green Homes Grants and the Sustainable Warmth national government programmes if the council are administering them.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">This does not include services provided under the Energy Companies Obligation to replace or upgrade boilers to homes on low income as this is already required and administered by councils. The project cannot be a trial project.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "11",
                        "name": "Does the council have a scheme to allow residents to purchase renewable energy cheaply, through collective buying?",
                        "topic": "Renewable Energy purchasing schemes",
                        "importance": "Low",
                        "how_marked": "National Data and Volunteer Research",
                        "criteria": """
                            <p><strong>Two Tier Criteria</strong></p>
                            <p>Criteria met if the council is running a Solar Streets or equivalent collective energy buying project.</p>
                            <p class="mb-0">Additional points awarded if the council is running a Solar Together or equivalent project, such as iChoosr. Points awarded to any other scheme councils are doing that are on a similar scale to Solar Together. </p>
                            """,
                        "clarifications": """
                            <p>If the project is being led by the County Council or a combined authority and all other councils in that area are involved too, then all those district councils will be awarded the points.</p>
                            <p>The project cannot be a trial project.</p>
                            <p class="mb-0">Marked partly using publicly available data from <a href="https://solarstreets.co.uk/" class="d-inline-block">Solar Streets</a> and <a href="https://solartogether.co.uk/landing" class="d-inline-block">Solar Together</a></p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "12",
                        "name": "Has the council supported local community renewable energy creation?",
                        "topic": "Community Renewable Energy",
                        "importance": "Medium",
                        "how_marked": "National Data and Volunteer Research",
                        "criteria": """
                            <p>Criteria met if there is public information about a council working with a local community energy generation infrastructure project, such as wind, solar or hydro. Evidence of this could include: </p>
                            <ul class="mb-0">
                                <li>Being formally listed as a partner on the community energy projects’ website</li>
                                <li>Evidence on the councils’ website of the council providing funding, land or other support to the community energy project. </li>
                            </ul>
                            """,
                        "clarifications": """
                            <p class="mb-0">Marked partly using data provided by <a href="https://communityenergyengland.org/" class="d-inline">Community Energy England</a></p>
                            """,
                    },
                ],
            },
            {
                "title": "Buildings, Heatings and Green Skills",
                "council_types": [
                    "combined",
                ],
                "weightings": {
                    "combined": "25%",
                },
                "questions": [
                    {
                        "council_types": ["combined"],
                        "code": "CA1",
                        "name": "Is the combined authority’s operations powered by renewable energy?",
                        "topic": "Renewable Tariff - combined authority buildings",
                        "importance": "Low",
                        "total_points": "2",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>Criteria is met if the combined authority has a green tariff that is 100% renewable or if the combined authority creates its own energy equivalent to 20% of more of its energy consumption through energy from waste.</p>
                            <p>Additional points awarded if the combined authority has a green tariff with Green Energy UK plc, Good Energy Limited or Ecotricity, or if the combined authority creates its own renewable energy equivalent to 20% or more of its energy consumption. This could be through on-site energy generation, or if they have built or bought a solar/wind farm elsewhere.</p>
                            """,
                        "clarifications": """
                            <p>This includes all energy that the combined authority is directly responsible for, in offices and any other buildings leased and managed by the combined authority where the combined authority pays the energy tariff.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA2",
                        "name": "Has the combined authority supported local community renewable energy creation?",
                        "topic": "Renewable Tariff - combined authority buildings",
                        "importance": "Medium",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if there is public information about them working with a local community energy generation infrastructure project, such as wind, solar or hydro. Evidence of this could include:</p>
                            <p>Being formally listed as a partner on the community energy projects’ website</p>
                            <p>Evidence on the combined authority’s website of them providing funding, land or other support to the community energy project.</p>
                            """,
                        "clarifications": """
                            <p>Marked partly using data provided by <a class="d-inline" href="https://communityenergyengland.org/">Community Energy England</a></p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA3",
                        "name": "Is the combined authority part of a partnership to support retrofit in the area?",
                        "topic": "Retrofit Partnerships",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the combined authority convenes or is a member of a local retrofit partnership, that focuses on knowledge sharing or skills. Evidence of this partnership is needed. At least two of the following must be visible:</p>
                            <ol>
                                <li>A named partnership with a public membership list</li>
                                <li>A terms of reference or aims of the group</li>
                                <li> Evidence of previous meetings, via notes, agendas, videos or in news stories</li>

                            </ol>
                            <p class="mb-0">Trial schemes that are active at the time of marking will be accepted.</p>
                        """,
                        "clarifications": """
                            <p>The criteria will be met if this partnership is a combined authority task and finish group or sub-committee group with external members.</p>
                            <p>The partnership can be with any organisation beyond the combined authority. It could include other councils, community groups, financial institutions or local businesses.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA4",
                        "name": "Has the combined authority produced research or a strategy understanding the scale, need and opportunity of retrofitting in its area?",
                        "topic": "Retrofit Partnerships",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the combined authority has contributed to research, strategy, evidence or business development in relation to home retrofit.</p>
                        """,
                        "clarifications": """
                            <p>The research must be finished to be valid.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA5",
                        "name": "Has the combined authority successfully raised funds for decarbonising homes and buildings through national government grants?",
                        "topic": "Funding sources",
                        "importance": "Medium",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if a combined authority has successfully bid on a government grant since 1st January 2019. The money doesn’t have to be spent or the project completed in order to meet the criteria.</p>
                        """,
                        "clarifications": """
                            <p>Evidence of a news story from the combined authority or listed as a successful bidder on any of the follow national government grants:
                            </p>
                            <ul>
                                <li>Public Sector Decarbonisation Scheme (1, 2, 3a, 3b)</li>
                                <li>Social Housing Decarbonisation Fund (1 and 2)</li>
                                <li>Green Homes Grant, local authority delivery (phase 1a, 1b, 2 and 3)</li>
                                <li>Sustainable Warmth Competition (local authority delivery 3 and Home Upgrade Grant 1)</li>
                            </ul>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA6",
                        "name": "Does the combined authority have a detailed plan or strategy to create the green skills needed to mitigate and adapt to the climate emergency?",
                        "topic": "Net-Zero Embedded in Skills Strategy",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the combined authority has a skills strategy or similar which explicitly covers how they will create the green skills needed locally.</p>
                            <p>This information could be in a combined authority’s skills strategy or other strategies.</p>
                        """,
                        "clarifications": """
                            <p>A chapter or equivalent on green skills in a climate action plan, corporate plan or homes or a building strategy would also be valid for a point. </p>
                            <p>The plan must cover multiple years.</p>
                            <p>Green Jobs and Greens Skills are ones that contribute to preserving or restoring the environment. They have a focus on either reducing carbon emissions, mproving energy and raw materials efficiency, protecting and restoring nature, minimising waste and pollution, adapting to the effects of climate change or making similar environmental improvements.</p>

                            <p>Green Jobs and Skills can be in traditional sectors such as manufacturing and construction, or in new, emerging green sectors such as renewable energy and energy efficiency. Sustainability managers in businesses, green transport officers and thermal heating specialists are all examples of green jobs.</p>

                            <p>Definitions from <a class="d-inline" href="https://www.ilo.org/global/topics/green-jobs/news/WCMS_220248/lang--en/index.htm">International Labour Organisation</a> and <a href="https://friendsoftheearth.uk/climate/whats-green-job-and-how-can-we-create-more-them">Friends of the Earth</a>.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA7",
                        "name": "Is the combined authority part of a programme to support green jobs creation in the area?",
                        "topic": "Green Skills Partnerships",
                        "importance": "High",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>This must be above and beyond providing green skills training in their adult education budget.</p>
                            <p>If the combined authority has run a Green Skills Bootcamp or equivalent programmes this is valid for a point. The programme must guarantee interviews with potential employers after completing training to be valid for a point. </p>
                            <p>The programme can be done in partnership with any organisation beyond the combined authority. It could include other councils, community groups, education providers, local businesses, key employers in the area or others. </p>
                        """,
                        "clarifications": """
                            <p>Green Jobs and Greens Skills are ones that contribute to preserving or restoring the environment. They have a focus on either reducing carbon emissions, mproving energy and raw materials efficiency, protecting and restoring nature, minimising waste and pollution, adapting to the effects of climate change or making similar environmental improvements. </p>

                            <p>Green Jobs and Skills can be in traditional sectors such as manufacturing and construction, or in new, emerging green sectors such as renewable energy and energy efficiency. Sustainability managers in businesses, green transport officers and thermal heating specialists are all examples of green jobs.</p>

                            <p>Definitions from <a class="d-inline" href="https://www.ilo.org/global/topics/green-jobs/news/WCMS_220248/lang--en/index.htm">International Labour Organisation</a> and <a href="https://friendsoftheearth.uk/climate/whats-green-job-and-how-can-we-create-more-them">Friends of the Earth</a>.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA8",
                        "name": "Does the combined authority run an employment or careers programme or project to encourage and promote green jobs?",
                        "topic": "Greens Skills Promotion",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Point awarded if the combined authority provides a supplementary employment or careers programme to encourage and promote green jobs.</p>
                            <p>Activities can include, but not limited to: stand alone websites, funding, or events promoting green careers at schools and colleges .</p>
                        """,
                        "clarifications": """
                            <p>Green Jobs and Greens Skills are ones that contribute to preserving or restoring the environment. They have a focus on either reducing carbon emissions, mproving energy and raw materials efficiency, protecting and restoring nature, minimising waste and pollution, adapting to the effects of climate change or making similar environmental improvements. 
                            </p>
                            <p>Green Jobs and Skills can be in traditional sectors such as manufacturing and construction, or in new, emerging green sectors such as renewable energy and energy efficiency. Sustainability managers in businesses, green transport officers and thermal heating specialists are all examples of green jobs.</p>
                            <p>Definitions from <a class="d-inline" href="https://www.ilo.org/global/topics/green-jobs/news/WCMS_220248/lang--en/index.htm">International Labour Organisation</a> and <a href="https://friendsoftheearth.uk/climate/whats-green-job-and-how-can-we-create-more-them">Friends of the Earth</a>.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA9a",
                        "name": "Has the combined authority funded a significant number of adult education skills courses or training advertised as skills for Green Jobs?",
                        "topic": "Green Skills Training",
                        "importance": "Medium",
                        "total_points": "2",
                        "how_marked": "FOI",
                        "criteria": """
                            <p><strong>Tiered Criteria</strong></p>
                            <p>The exact number will be determined in due course. The scoring will be tiered, with further points available for a higher number of courses provided. </p>
                            <p>Criteria met if the combined authority has provided a minimum number of green skills adult education courses in the last three academic years.</p>
                            <p>This is the total number of adult education courses that the combined authority advertises as Green Skills or Green Jobs that they have funded, in part of partial. If the combined authority classifies them as a green job/skill, then they will be counted.</p>
                            <p>This includes courses related to the building of or maintaining of residential homes or commercial buildings as well as other Green Skills, such as in relation to Electric Vehicles, Digital Skills, Education, Biodiversity and Conservation management and others. </p>
                            <p>Any accredited course is valid for a point. There is no minimum length of the course required to be valid for the point.</p>
                            <p> Courses that are part of a Skills Bootcamp are valid. This question is not limited to Skills Bootcamps courses only, other courses are valid.</p>
                        """,
                        "clarifications": """
                            <p>Green Jobs and Greens Skills are ones that contribute to preserving or restoring the environment. They have a focus on either reducing carbon emissions, mproving energy and raw materials efficiency, protecting and restoring nature, minimising waste and pollution, adapting to the effects of climate change or making similar environmental improvements.</p>
                            <p>Green Jobs and Skills can be in traditional sectors such as manufacturing and construction, or in new, emerging green sectors such as renewable energy and energy efficiency. Sustainability managers in businesses, green transport officers and thermal heating specialists are all examples of green jobs.</p>

                            <p>Definitions from <a class="d-inline" href="https://www.ilo.org/global/topics/green-jobs/news/WCMS_220248/lang--en/index.htm">International Labour Organisation</a> and <a href="https://friendsoftheearth.uk/climate/whats-green-job-and-how-can-we-create-more-them">Friends of the Earth</a>.</p>
                            <p>The courses can be free.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA9b",
                        "name": "Has the combined authority had a significant number of people completing adult education courses or training in the last three academic years that they funded and advertised as skills for Green jobs?",
                        "topic": "Green Skills Training",
                        "importance": "Medium",
                        "total_points": "3",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>This question is asking how many people have been trained on the courses funded and advertised by the combined authority as Green skills/jobs in the last three academic years.</p>
                            <p>Criteria met if the combined authority has trained a minimum number of people in green skills through adult education courses. 
                            The exact number will be determined in due course. The scoring will be tiered, with further points available for a higher number of courses provided. </p>
                            <p>This includes courses related to retrofitting, the building of or maintaining of residential homes or commercial buildings as well as other Green Skills, such as in relation to Electric Vehicles, Digital Skills, Education, Biodiversity and Conservation management and others. </p>
                            <p>Any accredited course is valid for a point. There is no minimum length of the course required to be valid for the point. 
                            Courses that are part of a Skills Bootcamp are valid. This question is not limited to Skills Bootcamps courses only, other courses are valid.</p>
                        """,
                        "clarifications": """
                            <p>This is the total number of people who have completed green skills training courses in the last academic year.</p>
                            <p>Green Jobs and Greens Skills are ones that contribute to preserving or restoring the environment. They have a focus on either reducing carbon emissions, mproving energy and raw materials efficiency, protecting and restoring nature, minimising waste and pollution, adapting to the effects of climate change or making similar environmental improvements. </p>
                            <p>Green Jobs and Skills can be in traditional sectors such as manufacturing and construction, or in new, emerging green sectors such as renewable energy and energy efficiency. Sustainability managers in businesses, green transport officers and thermal heating specialists are all examples of green jobs.</p>

                            <p>Definitions from <a class="d-inline" href="https://www.ilo.org/global/topics/green-jobs/news/WCMS_220248/lang--en/index.htm">International Labour Organisation</a> and <a href="https://friendsoftheearth.uk/climate/whats-green-job-and-how-can-we-create-more-them">Friends of the Earth</a>.</p>
                            """,
                    },
                ],
            },
            {
                "title": "Transport",
                "council_types": [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                    "combined",
                ],
                "description": "Transport is the other biggest sector of greenhouse gas emissions in the UK. This section covers the main enabling actions councils can take to reduce car use and encourage more sustainable transport within their area.",
                "weightings": {
                    "single": "20%",
                    "district": "5%",
                    "county": "30%",
                    "northern-ireland": "15%",
                    "combined": "25%",
                },
                "questions": [
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "1",
                        "name": "Is the council transitioning their vehicle fleet to electric?",
                        "topic": "Council Fleet",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if over 10% of the council’s fleet are electric vehicles.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">A council’s fleet includes council owned or leased vehicles, and may include street cleaners and waste collection vehicles.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "2",
                        "name": "Has the council set up or supported a shared transport scheme that can be used across their whole area?",
                        "topic": "Shared Transport Schemes",
                        "importance": "Low",
                        "how_marked": "National Data and Volunteer Research",
                        "criteria": """
                            <p>Criteria met for each type of scheme where a member of the public can hire a vehicle (e.g. car/scooter/bike/mobility device) within the local authorities area.</p>
                            <p>The following schemes will be awarded points:</p>
                            <ul>
                                <li>Car share scheme of any size in the area. Including:
                                    <ul>
                                        <li>Community car clubs.</li>
                                        <li>Car clubs provided by private companies</li>
                                        <li>Hiring of council vehicles when not in use</li>
                                    </ul>
                                </li>
                                <li>Bike share scheme</li>
                                <li>E-bike or cargo bike share scheme</li>
                                <li>E-scooter scheme</li>
                                <li>Mobility Devices</li>
                                <li>Wheels 2 Work scheme</li>
                            </ul>
                            <p class="mb-0">Trial schemes that are active at the time of marking will be accepted.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Marked mainly using <a href="https://como.org.uk/" class="d-inline"> CoMoUK’s </a>publicly available data on shared transport schemes.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "3",
                        "name": "Does the council have enforced school streets across its area?",
                        "topic": "School Streets",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Points awarded for 10 or more enforced school streets.</p>
                            <p>Further points awarded for 30 or more enforced school streets.</p>
                            <p>A trial school street, which is current at the time of marking, will be counted but only if the local authority is over the total of 10/30 with trial/permanent school streets</p>
                            <p class="mb-0">School streets must be year round to be accepted here.</p>
                            """,
                        "clarifications": """
                            <p>A school street is a street outside of a school that is closed to private vehicles for a time period before and after the school opens and shuts. This is to encourage a safe route for children to walk or roll to school, and improve air quality on the roads outside schools.</p>
                            <p class="mb-0">Enforced school streets are when the road is blocked during the hours decided or there are cameras used to stop private vehicles (often with exceptions for residents) to travel down the street.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "4",
                        "name": "Is the council committed to making 20mph the standard speed limit for most restricted roads?",
                        "topic": "Speed limits",
                        "importance": "Low",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>Criteria met if you are verified by 20’s Plenty For Us as having 20mph as the default speed limit for restricted roads. </p>
                            <p>20’s Plenty For Us looks for councils that have a policy for setting 20mph for most roads: residential and high street roads. </p>
                            <p class="mb-0">This will include local authorities that have not implemented a 20mph speed limit for restricted roads but have passed the policy, as it can take 2-3 years to fully implement due to replacing the road signs.</p>
                            """,
                        "clarifications": """
                            <p>Restricted roads are roads that due to lighting frequency are usually 30mph as according to national speed limits.</p>
                            <p>Marked using <a href="https://www.20splenty.org/20mph_places" class="d-inline">20’s Plenty for Us</a> list of councils to have implemented a 20mph default.</p>
                            <p class="mb-0">Where a national government has introduced 20mph as the norm for restricted roads all councils within that nation will be awarded the point.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "5a",
                        "name": "Has the council introduced a Clean Air Zone or Low-Emission Zone?",
                        "topic": "Clean Air Zone",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if a council has implemented a Clean Air Zone or Low Emission Zone that has been in operation since 2019.</p>
                            <p class="mb-0">For this question the Clean Air Zone or Low Emission Zone does not have to require charges for private vehicles.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">A Clean Air Zone or Low Emission Zone is where targeted action is being taken to improve air quality and reduce the number of polluting vehicles and is usually defined over a certain area, such as a city centre.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "5b",
                        "name": "Does the council’s Clean Air Zone or Low Emission Zone require charges for private vehicles?",
                        "topic": "Clean Air Zone",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if a council has implemented a Clean Air Zone or Low Emission Zone that has been in operation since 2019 and it charges for private vehicles.</p>
                            <p class="mb-0">For this question the Clean Air Zone or Low Emission Zone does have to require charges for private vehicles.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">A Clean Air Zone or Low Emission Zone is where targeted action is being taken to improve air quality and reduce the number of polluting vehicles and is usually defined over a certain area, such as a city centre.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "6",
                        "name": "Has the council taken clear steps to support active travel?",
                        "topic": "Active Travel",
                        "importance": "Medium",
                        "how_marked": "National Data and Volunteer Research",
                        "criteria": """
                            <p class="mb-0"><i>Data is not currently available to create the criteria for this question. This will be published with the complete methodology when the Scorecard results are published.</i></p>
                            """,
                        "clarifications": """
                            <p class="mb-0">TBC</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "7",
                        "name": "Does the council have controlled parking zones across all the residential areas of the local authority?",
                        "topic": "Parking",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Points awarded if the council has a controlled parking zone across any area of the local authority. This can be for any time period stated.</p>
                            <p class="mb-0">Further points awarded if the council has controlled parking zones across the whole area of the local authority. This can be for any time period stated.</p>
                            """,
                        "clarifications": """
                            <p>A controlled parking zone is where Residential Permit Parking is only permitted.</p>
                            <p class="mb-0">By making areas residential permit parking only it discourages short trips as parking is not as available.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "8a",
                        "name": "Are there any low emission buses used within the council’s area?",
                        "topic": "Buses",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if there are any low-emission buses in use across the area.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">We have defined low emissions buses as any buses that are electric, hydrogen or plug-in hybrid buses.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "england_only": "yes",
                        "code": "8b",
                        "name": "Is bus ridership within the council’s area high?",
                        "topic": "Buses",
                        "importance": "Medium",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>Criteria met if bus passenger journeys are over 75 per head of population.</p>
                            <p class="mb-0">Further points awarded if bus passenger journeys are over 150 per head of population.</p>
                            """,
                        "clarifications": """
                            <p><strong>This question is applicable to English transport authorities only (Single Tier and County Councils).</strong></p>
                            <p>Where the data is combined at a ITA level - we are scoring all constituent councils as one. For example, all councils within Greater Manchester ITA will be scored according to the Greater Manchester ITA bus ridership figures.</p>
                            <p class="mb-0">Marked using Department for Transport data (BUS 0110): Passenger journeys on local bus services per head of population by local authority: England - <a href="https://www.gov.uk/government/statistical-data-sets/bus01-local-bus-passenger-journeys" class="d-inline">Link here</a></p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "9",
                        "name": "Does the council have a workplace parking levy?",
                        "topic": "Workplace Parking Levy",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if a workplace parking levy is in place by the time of marking.</p>
                            <p>The workplace parking levy does not have to cover the whole of the council’s area.</p>
                            <p class="mb-0">For scoring purposes we will count a scheme as implemented if it is approved by the council with a date set for the start of the implementation.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">A workplace parking levy is a fee paid by businesses, or their employees, for parking spaces. This is used to discourage commuting by car thereby reducing emissions, improving congestion and improving air quality.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "10",
                        "name": "Has the council supported the expansion of a public network of electric vehicle chargers?",
                        "topic": "EV charging",
                        "importance": "Low",
                        "how_marked": "National Data",
                        "criteria": """
                            <p><strong>Two tier criteria</p></strong>
                            <p>Points awarded if the council has over 60 public chargers per 100,000 residents.</p>
                            <p class="mb-0">Further points awarded if the council has over 434 chargers per 100,000 residents.</p>
                            """,
                        "clarifications": """
                            <p>This question is marked using the UK Government’s data on publicly available EV chargers within the council’s area. This includes all publicly available EV chargers, rather than just council owned or installed, as councils would still have to approve any public EV charger in their area.</p>
                            <p>We have chosen the two tier criteria to challenge councils. 60 public chargers per 100,000 residents has been achieved by a significant number of councils but many have also not yet reached this level. </p>
                            <p>The higher level of 434 chargers is based on the UK Government’s 2030 target for 300,000 public EV chargers. To achieve the same format we divided (300,000 by the Office for National Statistics 2030 projected population 69.2 million) and multiplied this figure by 100,000. Rounding to the nearest EV charger gave us 434 chargers per 100,000 residents.</p>
                            <p class="mb-0">Marked using <a href="https://www.zap-map.com/ " class="d-inline">Zap Maps</a> publicly available data on EV chargers, which is available using the <a href="https://www.gov.uk/government/statistics/electric-vehicle-charging-device-statistics-july-2022" class="d-inline">UK Government</a>. Please note, we will use the most recent available data in the 2023 scoring process.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "county"],
                        "code": "11",
                        "name": "Has the council approved, expanded or built a high carbon transport project since 2019?",
                        "topic": "High Carbon transport project",
                        "importance": "High",
                        "how_marked": "FOI",
                        "criteria": """
                            <p><strong>Negatively Scored Question</p></strong>
                            <p>Points deducted if the council has approved, expanded or built a road since 2019.</p>
                            <p class="mb-0">Further points deducted if the council has approved, expanded or built an airport since 2019.</p>
                            """,
                        "clarifications": """
                            <p>A high carbon transport project is defined as a road or an airport.</p>
                            <p>Approved = Passed a planning application in favour of expansion or construction of a road/airport since 2019.</p>
                            <p>Expanded = A road/airport has been expanded after 2019, even if it received planning approval before 2019. In the case of airports the expansion would include increasing passenger numbers.</p>
                            <p class="mb-0">Built = A road/airport has been built after 2019, even if it received planning approval before 2019.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA1a",
                        "name": "Does the combined authority’s Transport Plan include the combined authority’s net-zero target and make tackling the climate emergency one of its main priorities?",
                        "topic": "Transport Plan",
                        "importance": "Low",
                        # "total_points": "2",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the Transport Plan is in date and the net-zero target is included within the transport strategy, although any date would be sufficient.</p>
                            <p>One of the key priorities in the Transport Plan must be to tackle the climate emergency or reduce emissions.</p>
                            """,
                        "clarifications": """
                            <p>We will accept other language for target dates being used such as carbon neutrality.</p>
                            <p>The net-zero target date must be an area-wide target, either the UK Government’s national target, the devolved nation’s target or the combined authority’s area-wide net zero target.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA1b",
                        "name": "Does the combined authority’s Transport Plan include expanding or building a high carbon transport project?",
                        "topic": "Transport Plan - High Carbon projects ",
                        "importance": "Medium",
                        # "total_points": "2",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points deducted if the combined authority details the expansion or building of new roads in the Transport Strategy.</p>
                            <p>Further points deducted if the combined authority details the expansion or building of new airports in the Transport Strategy.</p>
                            """,
                        "clarifications": """
                            <p>A high carbon transport project is defined as a road or an airport.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA2",
                        "name": "Has the combined authority set up or supported a shared transport scheme that can be used in their area?",
                        "topic": "Shared Transport Schemes",
                        "importance": "Low",
                        # "total_points": "2",
                        "how_marked": "National Data & Volunteer Research",
                        "criteria": """
                            <p>Criteria met for each type of scheme where a member of the public can hire a vehicle (e.g. car/scooter/bike/mobility device) within the combined authorities area.</p>

                            <ul>
                                <li>Car share scheme of any size in the area. Including:
                                    <ul>
                                        <li>Community car clubs.</li>
                                        <li>Car clubs provided by private companies</li>
                                        <li>Hiring of combined authorities when not in use</li>
                                    </ul>
                                </li>
                                <li>Bike share scheme</li>
                                <li>E-bike or cargo bike share scheme</li>
                                <li>E-scooter scheme</li>
                                <li>Mobility Devices</li>
                                <li>Wheels 2 Work scheme</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>Marked mainly using  publicly available data on shared transport schemes from <a href="https://como.org.uk/" class="d-inline">Coordinated Mobility</a></p>

                            <p>If schemes are within the combined authority area then the combined authority will be awarded the point</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA3",
                        "name": "Has the combined authority supported the expansion of the train network?",
                        "topic": "Trains",
                        "importance": "Low",
                        # "total_points": "2",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the combined authority has published a rail strategy, which includes the opening of new or the reopening of any stations or train lines.</p>
                            <p>Points awarded if the combined authority has invested in new zero emission train stock. </p>
                            <p>Points awarded if the combined authority has provided funding for extensive retrofit or opening of new or reopening of any stations and/or train lines.</p>
                            """,
                        "clarifications": """
                            <p>Zero emission train stock would include any trains that run via electric voltage or they are hydrogen powered.</p>
                            <p>Extensive retrofit (sometimes called deep retrofit) refers to significant works of size or scale that result in a fundamental change to the building structure and/or services. </p>
                            <p>Projects (reopenings/extensive retrofit/new train stock) which are due to happen will not be awarded points. The project must have occurred or be under way.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA4a",
                        "name": "Does the combined authority’s bus service improvement plan include a target for the bus fleet to be zero emission?",
                        "topic": "Buses",
                        "importance": "Low",
                        # "total_points": "2",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the combined authority has a target to be completely zero emission by 2040.</p>
                            <p>Further points awarded if the combined authority has a target to be zero emission by 2030. </p>
                            """,
                        "clarifications": """
                            <p>Zero emission bus fleet could include any buses that are battery or hydrogen powered.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA4b",
                        "name": "Is bus ridership within the combined authority area high?",
                        "topic": "Buses",
                        "importance": "Medium",
                        # "total_points": "2",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>Points awarded if bus passenger journeys are over 75 per head of population</p>
                            <p>Further points awarded if bus passenger journeys are over 150 per head of the population</p>
                            """,
                        "clarifications": """
                            <p>This question is applicable to English transport authorities only.</p>
                            <p>Marked using <a href="https://www.gov.uk/government/statistical-data-sets/bus-statistics-data-tables#local-bus-passenger-journeys-bus01" class="d-inline">Department for Transport data (BUS 01)</a> : Passenger journeys on local bus services per head of population by local authority: England</p>
                        """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA5",
                        "name": "Has the combined authority introducted integrated ticketing for public transport?",
                        "topic": "Integrated Ticketing",
                        "importance": "High",
                        # "total_points": "2",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the combined authority has implemented, or has a firm timetable with a published date, for integrated ticketing for buses within the combined authority area.</p>

                            <p>Further points awarded if the combined authority has implemented, or has a firm timetable with a published date for integrated ticketing across all public transport including buses, rail, trams and shared active travel schemes - where they have these modes of transport - within the combined authority area.</p>
                            """,
                        "clarifications": """
                            <p>Integrated ticketing allows a person to make a journey that involves transfers within or between different transport modes with a single ticket.</p>
                        """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA6a",
                        "name": "Does the combined authority have a Clean Air Zone or Low-Emission Zone within its area?",
                        "topic": "Clean Air Zone",
                        "importance": "Low",
                        # "total_points": "2",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if a combined authority has implemented a Clean Air Zone or Low Emission Zone that has been in operation since 2019.</p>
                            <p>For this question the Clean Air Zone or Low Emission Zone does not have to require charges for private vehicles.</p>
                            """,
                        "clarifications": """
                            <p>A Clean Air Zone or Low Emission Zone is where targeted action is being taken to improve air quality and reduce the number of polluting vehicles and is usually defined over a certain area, such as a city centre.</p>
                        """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA6b",
                        "name": "Does the combined authority have a Clean Air Zone or Low-Emission Zone within its area that requires charges for private vehicles?",
                        "topic": "Clean Air Zone",
                        "importance": "Medium",
                        # "total_points": "2",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if a combined authority has implemented a Clean Air Zone or Low Emission Zone that has been in operation since 2019.</p>
                            <p>For this question the Clean Air Zone or Low Emission Zone does not have to require charges for private vehicles.</p>
                            """,
                        "clarifications": """
                            <p>A Clean Air Zone or Low Emission Zone is where targeted action is being taken to improve air quality and reduce the number of polluting vehicles and is usually defined over a certain area, such as a city centre.</p>
                        """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA7",
                        "name": "Has the combined authority provided support for active travel schemes?",
                        "topic": "Active Travel",
                        "importance": "Medium",
                        # "total_points": "2",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>Data is not currently available to create the criteria for this question. This will be published with the complete methodology when the Scorecard results are published. </p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA8",
                        "name": "Has the combined authority supported the expansion of a public network of electric vehicle chargers?",
                        "topic": "EV charging",
                        "importance": "Low",
                        # "total_points": "2",
                        "how_marked": "National Data",
                        "criteria": """
                            <p><strong>Two-tier criteria</strong></p>
                            <p>Points awarded if the combined authority has over 60 public chargers per 100,000 residents.</p>
                            <p>Further points awarded if the combined authority has over 434 chargers per 100,000 residents.</p>
                            """,
                        "clarifications": """
                            <p>This question is marked using the UK Government’s data on publicly available EV chargers within the combined authorities area. This includes all publicly available EV chargers, rather than just council owned or installed, as combined authorities provide funding and support for public EV charger in their area.</p>
                            <p>We have chosen the two tier criteria to challenge combined authorities. 60 public chargers per 100,000 residents has been achieved by a significant number of areas but many have also not yet reached this level. </p>
                            <p>The higher level of 434 chargers is based on the UK Government’s 2030 target for 300,000 public EV chargers. To achieve the same format we divided (300,000 by the Office for National Statistics 2030 projected population 69.2 million) and multiplied this figure by 100,000. Rounding to the nearest EV charger gave us 434 chargers per 100,000 residents.</p>
                            <p>Marked using <a href="https://www.zap-map.com/" class="d-inline">Zap Maps</a> publicly available data on EV chargers, which is available using the <a href="https://www.gov.uk/government/statistics/electric-vehicle-charging-device-statistics-july-2022" class="d-inline">UK Government</a>. Please note, we will use the most recent available data in the 2023 scoring process.</p>
                        """,
                    },
                ],
            },
            {
                "title": "Planning & Land Use",
                "council_types": [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                ],
                "description": "These sections have a less direct impact on emissions reduction. However, they have a considerable impact on enabling climate action and embedding it in longer-term policies. All council types have similar power and responsibilities in Governance & Finance and the actions scored in this section demonstrate the council’s commitment to reducing emissions and embedding climate action across the council. Planning & Land Use is one of the areas where single tier and district councils can be the most effective and also hold a lot of power, both for mitigation and adaptation, hence the higher weighting here than for the final three sections. County councils are not planning authorities which explains their lower section weighting for the Planning & Land Use section.",
                "weightings": {
                    "single": "15%",
                    "district": "25%",
                    "county": "5%",
                    "northern-ireland": "15%",
                },
                "questions": [
                    {
                        "council_types": ["single", "district"],
                        "code": "1",
                        "name": "Is the council’s area wide net zero target a strategic objective of the Local Plan?",
                        "topic": "Net-zero in Local Plan",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the Local Plan includes:</p>
                            <ul>
                                <li>Reaching net zero as a strategic objective of the Local Plan</li>
                                <li>The council’s net zero target date is also found within the Plan.</li>
                            </ul>
                            <p class="mb-0">The net-zero target must be an area wide net-zero target.</p>
                            """,
                        "clarifications": """
                            <p>Reaching net-zero must be part of the strategic objectives listed initially in the council’s Local Plan - even if the target date is not listed in the strategic objective. This is because the objectives are broader and Joint Local Plans may have different targets between the local authorities.</p>
                            <p>We will accept other language for target dates, including carbon neutrality or the carbon budget the council has committed to stay within.</p>
                            <p  class="mb-0">If the Local Plan references a national net-zero target it must still be a strategic objective of the local plan to meet the national target, rather than the national target just being stated.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district"],
                        "code": "2",
                        "name": "Has the council committed to building all future council owned or managed housing to a high energy efficiency or operationally net-zero standard?",
                        "topic": "Council homes - energy efficient and low carbon",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</p></strong>
                            <p>Points awarded if the council has a policy to build new council owned or managed housing as highly energy efficient or operationally net zero with the policy implemented from 2030 to 2040.</p>
                            <p class="mb-0">Additional points awarded if the council has a policy to build new council owned or managed housing as highly energy efficient or operationally net zero with the policy already implemented since 2019 or with implementation by 2030.</p>
                            """,
                        "clarifications": """
                            <p><strong>High energy efficiency</strong> includes building new council owned or managed housing building standards such as Passivhaus/BREAM excellent or LEED standard or a similar council own standard.</p>
                            <p>For operationally net-zero policies, we will accept those that define this as only concerning regulated emissions. Definitions for operationally net-zero and regulated emissions are below.</p>
                            <p><strong>Operationally net-zero:</strong> when the amount of carbon emissions associated with the building’s operational energy on an annual basis is zero or negative. A net zero carbon building is highly energy efficient and powered from on-site and/or off-site renewable energy sources, with any remaining carbon balance offset.” <a href="https://ukgbc.s3.eu-west-2.amazonaws.com/wp-content/uploads/2019/04/05150856/Net-Zero-Carbon-Buildings-A-framework-definition.pdf" class="d-inline"> Link to definition</a></p>
                            <p><strong>Regulated emissions:</strong> Emissions generated through building energy consumption resulting from the specification of controlled, fixed building services and fittings, including space heating and cooling, hot water, ventilation, fans, pumps and lighting. Such energy uses are inherent in the design of a building." <a href="https://www.designingbuildings.co.uk/wiki/Regulated_and_unregulated_energy_consumption" class="d-inline">More information</a></p>
                            <p class="mb-0">Council owned or managed housing: This includes arms-length management organisation (ALMO) if the homes are owned by the Council but not Housing Associations.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "northern-ireland"],
                        "code": "3a",
                        "name": "Does the council require new homes to make an improvement on the Part L building regulations?",
                        "topic": "New Homes - Low Carbon Requirements",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the council has a policy that requires a reduction in carbon/energy of new homes within the councils area that is 19% higher than the Part L building regulations.</p>
                            <p class="mb-0">This would be the same as Scottish councils requiring “Silver standard” as a minimum.</p>
                            """,
                        "clarifications": """
                            <p>Part L building regulations are the English national standard building regulations, which define the energy performance and carbon emissions in new homes.</p>
                            <p class="mb-0">Councils can require improvements that require lower emissions than the current building regulations.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "northern-ireland"],
                        "code": "3b",
                        "name": "Does the council require a fabric first approach for new development?",
                        "topic": "New Homes - Energy Efficiency Requirements",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>The criteria will be met by English councils if they have a policy that exceeds the minimum government’s building regulations on the Part L Target for Fabric Energy Efficiency. </p>
                            <p>Alternatively, the criteria will be met for councils that have a policy with a space heating requirement that exceeds the minimum government’s building regulations.</p>
                            <p class="mb-0">For Scottish councils, the criteria will be met if the council requires developers to meet the Silver or Gold building standards</p>
                            """,
                        "clarifications": """
                            <p>Part L building regulations are the English national standard building regulations, which define the energy performance and carbon emissions in new homes.</p>
                            <p class="mb-0">A fabric first approach by a council would require improvements on the national standard thereby ensuring new homes are energy efficient.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "northern-ireland"],
                        "code": "3c",
                        "name": "Does the council set a requirement that all new homes to be built must be operationally (regulated) net zero?",
                        "topic": "New Homes - Net zero requirements",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Points awarded if the council requires new homes to be operationally net zero with the policy implemented from 2030 to 2040.</p>
                            <p>More points awarded if the council requires new homes to be operationally net zero with the policy already implemented since 2019 or with implementation by 2030.</p>
                            <p>Any date to implement the policy after 2040 would not be awarded points.</p>
                            <p class="mb-0">This would be equivalent for Scottish authorities to mandate the “Platinum” building standard for carbon emissions for all new buildings.</p>
                            """,
                        "clarifications": """
                            <p>For operationally net-zero policies, we will accept those that define this as only concerning regulated emissions. Definitions for operationally net-zero and regulated emissions are below.</p>
                            <p><strong>Operationally net-zero:</strong> when the amount of carbon emissions associated with the building’s operational energy on an annual basis is zero or negative. A net zero carbon building is highly energy efficient and powered from on-site and/or off-site renewable energy sources, with any remaining carbon balance offset.” <a href="https://ukgbc.s3.eu-west-2.amazonaws.com/wp-content/uploads/2019/04/05150856/Net-Zero-Carbon-Buildings-A-framework-definition.pdf" class="d-inline">Link to definition</a></p>
                            <p><strong>Regulated emissions:</strong> Emissions generated through building energy consumption resulting from the specification of controlled, fixed building services and fittings, including space heating and cooling, hot water, ventilation, fans, pumps and lighting. Such energy uses are inherent in the design of a building." <a href="https://www.designingbuildings.co.uk/wiki/Regulated_and_unregulated_energy_consumption" class="d-inline">More information</a></p>
                            <p>If the council is achieving net-zero homes through cash-in-lieu contributions or offsets this will not count for this question. However, if the Council provides an exception that offsetting is allowed where a net-zero home may not be technically feasible this will still be valid.</p>
                            <p class="mb-0">There are a number of local plans in the draft stage who are requiring this policy. If these policies are deemed unsound by the Planning Inspectorate we will remove this question.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "northern-ireland"],
                        "code": "4",
                        "name": "Does the council require developers to carry out a whole life cycle carbon assessment of new build developments?",
                        "topic": "New Builds - Embodied Emissions",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Points awarded if the council requires developers to carry out a whole life cycle carbon assessment for new developments.</p>
                            """,
                        "clarifications": """
                            <p>Whole Life-Cycle Carbon (WLC) emissions are the carbon emissions resulting from the materials, construction and the use of a building over its entire life, including its demolition and disposal. A WLC assessment provides a true picture of a building’s carbon impact on the environment. For example it takes account of the embodied energy of the materials.</p>
                            <p class="mb-0">If this policy is applied for all new developments but does not apply for small scale developments (in England this is defined as any development under 10 homes) then the council will still score the point.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district"],
                        "code": "5",
                        "name": "Does the council require a higher level of water efficiency for all new homes?",
                        "topic": "New Builds - Water Efficiency",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the council requires the lower level of water use - stated as 110 litres per person per day - for new homes.</p>
                            <p class="mb-0">This would be the same as Scottish councils requiring "Silver standard" or "Gold standard" as a minimum for new homes.</p>
                            """,
                        "clarifications": """
                            <p>The council doesn’t have to be defined as in a water stressed area to adopt the 110 litres per person per day standard for new build development but a clear local need should be demonstrated. It should be noted that over half of England is defined as in a <a href="https://www.gov.uk/government/publications/water-stressed-areas-2021-classification" class="d-inline">water stressed area</a>.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "northern-ireland"],
                        "code": "6",
                        "name": "Has the council removed minimum parking requirements for new residential homes across their area?",
                        "topic": "Car dependency - Parking Standards",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Points awarded if the council has removed minimum parking requirements for new developments in any area. </p>
                            <p>For example, in a rural council this could mean minimum parking requirements are removed for the main town or if the council is urban if minimum parking requirements are removed for a central area.</p>
                            <p class="mb-0">Further points awarded if there are no minimum parking requirements across the whole of the council’s area.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district"],
                        "code": "7",
                        "name": "Does the council include a policy in the Local Plan to create 15/20 minute neighbourhoods?",
                        "topic": "Sustainable Neighbourhoods",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the Local Plan includes a policy to create 15/20 minute neighbourhoods. To meet the criteria the policy would have to include a definition of what a 15/20 minute community including:</p>
                            <ul>
                                <li>What key services would be required within 15/20 minutes of new homes.</li>
                                <li>How it will be measured, for example 15 minutes by bike, walking, bus. As the crow flies distances will not meet the criteria.</li>
                            </ul>
                            <p class="mb-0">If an authority has defined a specific zone where 15/20 minute neighbourhood policy principles would apply like the main town in a rural area then this would get the mark.</p>
                            """,
                        "clarifications": """
                            <p>Synonyms for 15/20 minute neighbourhoods include: <i>Healthy Streets Approach, Complete Neighbourhoods, Complete Communities</i>.</p>
                            <p class="mb-0">This policy must be found in the Local Plan, Corporate Plan or an Area Climate Action Plan</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "northern-ireland"],
                        "code": "8",
                        "name": "Has the council committed to avoiding new building developments on the functional flood plain?",
                        "topic": "Flood plain",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the Local Plan states that there is a ban, or avoidance to building on the functional flood plain.</p>
                            <p class="mb-0">The criteria will also be met if a policy states that any new development will only replace the footprint of current development.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">The functional flood plain is defined as a 3b flood plain by local authorities in England and Scotland, and Zone C in <a href="ttps://www.ambiental.co.uk/flood-zones/" class="d-inline">Wales</a></p>
                            <p class="mb-0">The functional flood plain is the most at risk area for flooding.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district"],
                        "code": "9",
                        "name": "Does the council have a minimum requirement for on-site renewable energy generation for new building development?",
                        "topic": "Renewable Energy Generation in New Development",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Points awarded if the council has a policy for any minimum level of onsite renewable energy generation for new building development.</p>
                            <p>More points awarded if the council requires new homes to be operationally net zero with the policy already implemented since 2019 or with implementation by 2030.</p>
                            <p class="mb-0">Further points awarded if the council has a policy that requires 20%, or above, onsite renewable energy generation for new building development.</p>
                            """,
                        "clarifications": """
                            <p>If this policy is expressed in terms of carbon reduction of energy by requiring the installation of renewable energy, instead of renewable energy usage, then the point would be awarded. A 15% reduction in carbon emissions through installing renewable energy will be treated as equivalent to a 15% requirement for total energy use from installing renewable energy.</p>
                            <p>If this policy is applied for all new developments but does not apply for small scale developments (in England this is defined as any development under 10 homes) then the council will still score the point.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district"],
                        "code": "10a",
                        "name": "Does the Local Plan identify suitable areas for new solar energy, wind developments and district heat networks?",
                        "topic": "Renewable Energy - Suitable Areas",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded if the council has a map detailing where solar energy can be built within the council’s area.</p>
                            <p>Points awarded if the council has a map detailing where wind energy can be built within the council’s area.</p>
                            <p class="mb-0">Points awarded if the council has a map detailing where a district heat network can be built within the council’s area.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "county"],
                        "code": "10b",
                        "name": "Has the Council approved any planning applications for new or expanded solar or wind developments, battery storage, or renewable district heat networks since 2019?",
                        "topic": "Renewable Energy - Approved Applications",
                        "importance": "High",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>Points awarded for planning applications approved for new or expanded solar, renewable district heat networks, wind developments or battery storage.</p>
                            <p class="mb-0">Solar developments must exceed 1 megawatt in capacity.</p>
                            """,
                        "clarifications": """
                            <p>Marked using data compiled by Department for <a href="https://data.barbour-abi.com/smart-map/repd/beis/?type=repd" class="d-inline">BEIS</a></p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "11",
                        "name": "Has the Council approved a planning application for a carbon intensive energy system to be built or expanded from 2019?",
                        "topic": "Carbon Intensive Industry",
                        "importance": "High",
                        "how_marked": "FOI",
                        "criteria": """
                            <p><strong>Negatively Scored Question:</strong></p>
                            <p>Points deducted if the council has approved a carbon intensive energy system since 2019. A carbon energy intensive system includes coal mines, fracking/shale gas/gas drilling, oil drilling, and unabated fossil fuel generation.</p>
                            """,
                    },
                ],
            },
            {
                "title": "Planning, Biodiversity and Land Use",
                "council_types": ["combined"],
                "weightings": {
                    "combined": "10%",
                },
                "questions": [
                    {
                        "council_types": ["combined"],
                        "code": "CA1",
                        "name": "Does the combined authority’s Spatial Planning Strategy include the combined authority’s net-zero target and make tackling the climate emergency one of its main priorities?",
                        "topic": "Spatial Planning Strategy",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the Spatial Planning Strategy is in date and the net-zero target is included within the Spatial Planning strategy, although any date for the net-zero target would be sufficient.</p>
                            <p>One of the key priorities in the Spatial Planning Strategy must be to tackle the climate emergency or reduce emissions. The priority to take climate action must be a stand alone priority, listed as one of the councils core priorities or equivalent. If the core priority is a more general 'Sustainability', 'Environment' or 'Greener City/Area' and climate action is a priority within this core priority this would get the point.</p>
                            """,
                        "clarifications": """
                            <p>If the Spatial Planning Strategy references a national net-zero target it must still clearly be an objective of the local plan to meet the national target, and rather than the national target just being stated.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA2",
                        "name": "Does the combined authority identify suitable areas for new solar energy, wind developments and district heat networks?",
                        "topic": "Area wide Energy Mapping",
                        "importance": "Medium",
                        "total_points": "3",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Points awarded if the combined authority has a map detailing where solar energy can be built within the whole combined authority area.</p>
                            <p>Points awarded if the combined authority has a map detailing where wind energy can be built within the whole combined authority area.</p>
                            <p>Points awarded if the combined authority has a map detailing where a district heat network can be built within the whole combined authority area.</p>
                            """,
                        "clarifications": """
                            <p>This can include if the combined authority has conducted Local Area Energy Mapping - but only if the mapping done within the area contains the mapping for either district heat, wind and/or solar. </p>
                            <p>Critieria is not met if a constituent authority has produced maps for their own area but the combined authority has not done the mapping across the whole of the combined authorities area.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA3",
                        "name": "Has the combined authority mapped the areas of opportunity for biodiversity?",
                        "topic": "Mapping biodiversity opportunity areas",
                        "importance": "Medium",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the combined authority has a map across its whole region detailing the opportunity areas for biodiversity opportunities. This could include mapping done as part of creating the local nature recovering strategy.</p>
                            """,
                        "clarifications": """
                            <p>Opportunity areas for biodiversity is defined as detailing the areas where biodiversity can be increased through habitat creation or improvement.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA4",
                        "name": "Does the combined authority have a natural capital investment plan?",
                        "topic": "Natural Capital Investment",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the combined authority has a natural capital investment plan.</p>
                            """,
                        "clarifications": """
                            <p>Natural Capital investment plan - a plan which details the natural resources and environmental features in a given area, regarded as having economic value or providing a service to humankind alongside the funding opportunities that can be sought to enact the plan.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA5",
                        "name": "Does the combined authority have a target to increase tree cover across its area?",
                        "topic": "Tree Cover",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the combined authority has publicly set a target to increase tree cover.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA6",
                        "name": "Does the combined authority provide funding for community action on biodiversity, for example through an environment fund or biodiversity action fund?",
                        "topic": "Biodiversity Community Funding",
                        "importance": "High",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>This is a ring-fenced fund that a combined authority has created to spend on biodiversity action locally for other organisations and volunteer groups. </p>
                            <p>The criteria must clearly be about biodiversity action projects and those who apply must complete some sort of application to define their planned biodiversity activities.</p>
                            <p>Point awarded if the combined authority has established a community biodiversity action fund or similar, provided the following criteria are met:</p>
                            <ul>
                                <li>The fund is at least £500,000 or higher. Where the overall amount of funding isn’t clear, it will be assumed that funds awarding individual grants over £10,000 or up to £100,000 will meet this criteria.</li>
                                <li>The fund is accessible to community groups, including where relevant parish councils</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>More general community or environment funds (such as the LCR Community Environment Fund) will be awarded if they specify that biodiversity projects will be supported.</p>
                            <p>The fund must be current - either accepting nominations in 2023, or awarding funding from January 2022.</p>
                            """,
                    },
                ],
            },
            {
                "title": "Governance & Finance",
                "council_types": [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                    "combined",
                ],
                "description": "This section aims to understand to what extent climate action has been incorporated and embedded across the whole of the council in all its activities and services in its decision making, forward planning and structures. This section also looks at how councils are raising funds for climate action and whether the councils’ investments are sustainable or supporting high carbon infrastructure and industries.",
                "weightings": {
                    "single": "15%",
                    "district": "15%",
                    "county": "15%",
                    "northern-ireland": "20%",
                    "combined": "20%",
                },
                "questions": [
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "1a",
                        "name": "Does the council’s corporate plan include a net-zero target and make tackling the climate emergency one of its main priorities?",
                        "topic": "Net Zero Embedded in Corporate Plan",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if climate action (alternatively called Sustainability or Environment) is listed as one of the council’s core priorities or equivalent. It must have its own heading or section and a net zero target date must be referenced.</p>
                            <p class="mb-0">The net-zero target date must be an area-wide target, either the UK Government’s national target, the devolved nation’s target or the council’s area-wide net zero target.</p>
                            """,
                        "clarifications": """
                            <p>A corporate plan is a business planning document that sets out the council’s future priorities and objectives to help ensure that the council manages its resources effectively.</p>
                            <p>For County Councils the document is called a (Strategic) Economic Plan</p>
                            <p  class="mb-0">We will accept other language for target dates being used such as carbon neutrality. </p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "1b",
                        "name": "Does the council’s medium term financial plan include the council’s net zero target and make tackling the climate emergency one of its main priorities?",
                        "topic": "Net-Zero Embedded in mid-term Financial Plan",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if climate action (alternatively called sustainability or environment) is listed as one of the council’s core priorities or equivalent. It must have its own heading or section and a net-zero target date must be referenced.</p>
                            <p class="mb-0">The net-zero target date must be an area-wide target, either the UK Government’s national target, the devolved nation’s target or the council’s area-wide net-zero target. </p>
                            """,
                        "clarifications": """
                            <p>A mid-term Financial Plan is a plan (often covering four years) which sets out the council’s commitment to provide services that meet the needs of people locally and that represent value for money within the overall resources available to the council. </p>
                            <p>We will accept other language for target dates being used such as carbon neutrality. </p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "2",
                        "name": "Has the council published a climate change risk register?",
                        "topic": "Climate Change Risk Register",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the council has accurately identified the environmental risks of climate change to the local area, either in a stand alone climate change or adaptation risk register, or incorporated into the council’s corporate risk register. There must be an explicit link between climate change and the increased risk of flooding or other weather events.</p>
                            <p class="mb-0">Adaptation plans are not valid, unless there is a risk register or equivalent within the adaptation plan.</p>
                            """,
                        "clarifications": """
                            <p>Environmental risks of climate change in the local area include flooding, extreme heat, air pollution or other extreme weather events.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "3a",
                        "name": "Is the council reporting on its own greenhouse gas emissions?",
                        "topic": "Emission data reduction",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Criteria met if the council is reporting its own emissions and fulfill all of the following:</p>
                            <ul>
                                <li>The council states whether they are using the Environmental Reporting Guidelines from Department for Environment, Food and Rural Affairs (DEFRA), the GCoM Common Reporting Framework (CRF), the Greenhouse Gas Accounting Tool (from the LGA), the Greenhouse Gas Protocol for Cities (Community Greenhouse Gas Emissions Inventories) or for Corporate Standards to develop their inventory. </li>
                            </ul>
                            <p>Councils must state whether they are using either:</p>
                            <ul>
                                <li>The inventory must cover a continuous period of 12 months, either a calendar year or a financial year</li>
                                <li>There must be data from 2019 and 2021 (or the financial year 2021/22).</li>
                                <li>The council must be measuring their own scope 1, 2 and 3 emissions</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>Scope 1 emissions are greenhouse gas emissions that an organisation owns or controls directly, such as fuel burnt from council vehicles.</p>
                            <p>Scope 2 emissions are greenhouse gas emissions that an organisation produces indirectly when they purchase and use energy, such as the emissions created from the electricity the council buys to heat its offices. </p>
                            <p class="mb-0">Scope 3 emissions are greenhouse gas emissions that are created indirectly in an organisations’ supply chain, such as the emissions produced in making the computers or paper that the council buys. Scope 3 also includes any other emissions not within scope 1 and 2.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "3b",
                        "name": "According to the council’s own reporting, have the council’s own greenhouse gas emissions reduced since 2019?",
                        "topic": "Emission data reduction",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Three tier criteria</strong></p>
                            <p>Councils must meet the minimum criteria of question 3a to be able to get points for this question.</p>
                            <p>Criteria met if, using the councils’ own reporting mechanisms, there has been a 5% or more reduction of scope 1 and 2 emissions when comparing 2019 to 2021 (or financial years 2018/19 to 2021/22) data.</p>
                            <p>Additional points awarded if this emission reduction has been 10% or more, or further points if the reduction has been 20% or more.</p>
                            <p>Further points awarded if there has been any reduction from scope 3 emissions.</p>
                            <p class="mb-0"><i>We recognise that there is currently no standard way that all councils use to report on emissions. We will score councils’ own calculations, despite the differences, as long as they fulfill the requirements in 3a.</i></p>
                            """,
                        "clarifications": """
                            <p>Scope 1 emissions are greenhouse gas emissions that an organisation owns or controls directly, such as fuel burnt from council vehicles. </p>
                            <p>Scope 2 emissions are greenhouse gas emissions that an organisation produces indirectly when they purchase and use energy, such as the emissions created from the electricity the council buys to heat its offices. </p>
                            <p class="mb-0">Scope 3 emissions are greenhouse gas emissions that are created indirectly in an organisations’ supply chain, such as the emissions produced in making the computers or paper that the council buys. Scope 3 also includes any other emissions not within scope 1 and 2.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "4",
                        "name": "Has the council’s area wide carbon emissions decreased, according to UK Government data?",
                        "topic": "Emission data reduction",
                        "importance": "Medium",
                        "how_marked": "National Data",
                        "criteria": """
                            <p><strong>Three tier criteria</strong></p>
                            <p>Criteria met if the council has had a 2% or more emission reduction from 2019 to 2021 data. </p>
                            <p class="mb-0">Additional points awarded if the emission reduction is more than 5%, or further points if the reduction is more than 10% from 2019 to 2021. </p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Marked using data provided by the Department for Business, Energy and Industrial Strategy. The data that will be used is the percentage difference between the calendar years 2021 and 2019 in the "Local Authority territorial carbon dioxide (CO2) emissions estimates within the scope of influence of Local Authorities" when it is published in Summer 2023.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "5",
                        "name": "Has the council adopted a new governance or decision making process to put tackling the climate emergency at the heart of every council decision made?",
                        "topic": "Climate Change Decision Making",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Criteria met if climate implications are listed or referenced for all council decisions at full council. Climate implications can be considered through Environmental Implications or an Integrated Impact Assessment if this includes a climate or environmental sub-heading or section.</p>
                            <p class="mb-0">Additional points if the council is using a detailed impact assessment tool to assess the climate implications of all council decisions. </p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "6",
                        "name": "Has the Council embedded climate action and waste reduction into their procurement policies?",
                        "topic": "Procurement",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Three tier criteria</strong></p>
                            <p>Criteria met if the council has a stand alone environmental or sustainable procurement policy, or a complete section on Sustainable or Responsible Procurement, Climate Change and Action or something similar, within their procurement policy that includes the following. </p>
                            <p>Two or more of the following criteria must be met to meet the minimum criteria for this point:</p>
                            <ol>
                                <li> The policy makes explicit reference to the council’s Climate Action Plan and zero carbon targets.</li>
                                <li>The policy requests to see the carbon reduction plan of the supplier in the tendering process or asks the supplier to detail any specific steps taken in the design and manufacture of the services to increase energy efficiency and reduce any detrimental environmental impacts.</li>
                                <li>There must be data from 2019 and 2021 (or the financial year 2021/22).</li>
                                <li>The policy encourages or requires suppliers, through selection processes, to adopt processes and procedures to reduce their environmental impact, including energy consumption and associated carbon emissions, where practicable. For example a council might allocate 5% or more of the tendering overall evaluation score to the environmental actions of the tenderer (the supplier’s contribution to carbon reduction within their own operations or other actions)</li>
                                <li>The policy encourages or requires suppliers, through selection processes, to adopt circular economy processes and procedures where practical. </li>
                            </ol>
                            <p>Additional points if the council has a mandatory requirement for tenders to do any of the following:</p>
                            <ul>
                                <li>Demonstrate how they will meet energy efficiency requirements or minimise energy consumption</li>
                                <li>Demonstrate how they will minimise waste in their products and services. This could be through recycled, natural, biodegradable or renewable materials being used, through not using single use plastic or other non-recyclable materials or through ensuring products and services last for as long as possible.</li>
                            </ul>
                            <p>Additional points if the council’s procurement policy includes any of the following:</p>
                            <ul class="mb-0">
                                <li>The council aims to source low or zero carbon energy wherever possible.</li>
                                <li>The council aims to phase out the use of fossil fuels from their council fleet.</li>
                                <li>The council references the waste hierarchy in its policy, for example by stating that it encourages the councils to consider if repeat procurement requests are always needed.</li>
                            </ul>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "7",
                        "name": "Does the council have a Cabinet member or Portfolio Holder that has climate change explicitly in their remit?",
                        "topic": "Elected Climate Change portfolio holder",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the council has a role such as Chair of Environment Committee, Cabinet Member for Environment, Chair of Environment and Climate Change Scrutiny Committee or any title with the words Climate Change, Climate Action, Climate Emergency, Environmental Sustainability, Environment or similar in it.</p>
                            <p class="mb-0">This role can be merged with another role, such as Environment and Transport.</p>
                            """,
                        "clarifications": """
                            <p>Councils are run by a cabinet or committee structure. A cabinet structure is where there is a council leader and cabinet members (all from the same governing party/parties) that make decisions on Council policy.</p>
                            <p>A committee structure is where councils are divided into politically balanced committees that make the decisions.</p>
                            <p class="mb-0">A Climate Champion (listed as a responsibility) is not valid for a point and neither is Chair or Cabinet member for Environmental Services.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "8",
                        "name": "What percentage of the council’s overall staff work on implementing their Climate Action Plan or other climate change projects?",
                        "topic": "Staff time on climate action",
                        "importance": "Medium",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>Criteria met if there are multiple staff members employed on 3 days a week or more to be working on the council’s Climate Action Plan or other climate change projects equating to a given % of the overall council staff team.</p>
                            <p class="mb-0">Data is not currently available to benchmark the exact % of staff that are working on implementing their Climate Action Plan or other climate change projects that will be valid for the points. This will be published with the complete methodology when the Scorecard results are published.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Staff is defined as all directly employed council staff (excluding sub/contractors and agency staff). We accept contractors for the role of biodiversity planning officer as long as they are equivalent to 3 days or more a week.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "9",
                        "name": "Have all senior management and councillors in the cabinet or committee chairs received climate awareness training?",
                        "topic": "Carbon literacy/awareness training",
                        "importance": "Low",
                        "how_marked": "FOI",
                        "criteria": """
                            <p class="mb-0">Criteria met if all senior management and councillors in leadership positions such as cabinet members or committee chairs elected before May 2023 have received climate awareness, carbon literacy or equivalent training.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Senior Management includes all Chief Executives, deputy Chief Executives and Directors or Heads of Departments, or equivalents, depending on what each council calls them.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "10a",
                        "name": "Has the council raised income for climate action from property development?",
                        "topic": "Funding sources",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria is met if the council has used either the Community Infrastructure Levy or Section 106 to raise any amount of funds for climate action, in England and Wales. There must be explicit reference to these funds being used for climate action, such as being used to deliver the council’s climate action plan.</p>
                            <p>In Scotland, the criteria is met if the council has used section 75 of the Town and Country Planning (Scotland) Act 1997.</p>
                            <p class="mb-0">In Northern Ireland, the criteria is met if the council has used section 76 of the 2011 Planning Act.</p>
                            """,
                        "clarifications": """
                            <p>The Community Infrastructure Levy is a charge that local authorities can set on new development in order to raise funds to help fund specific projects, such as the infrastructure, facilities and services needed to support new homes and businesses.</p>
                            <p>Section 106 are legal agreements between Local Authorities and developers linked to planning permissions, which can include councils requiring developers to build specific community infrastructure (such as bus and cycles lanes) or provide finance for specific council projects. They can also be known as planning obligations.</p>
                            <p>Section 75 of the Town and Country Planning (Scotland) Act 1997 is similar to section 106, where the council can require conditions of the developers, such as building specific community infrastructure or providing finance for specific council projects. </p>
                            <p class="mb-0">Section 76 of the 2011 Planning Act is similar to section 106, where the council can require conditions of the developers, such as building specific community infrastructure or providing finance for specific council projects.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "10b",
                        "name": "Has the council launched a Climate Bond, Community Municipal Investment or equivalent?",
                        "topic": "Funding sources",
                        "importance": "Medium",
                        "how_marked": "National Data and Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council has launched a Climate Bond, Community Municipal Investment or equivalent of any amount as a way to raise funds for climate action.</p>
                            """,
                        "clarifications": """
                            <p>A Climate Bond or Community Municipal Investment are bonds or loans issued by the council’s corporate body and administered by a regulated crowdfunding platform. They allow local authorities to raise funds for specific projects through the public investing their money, from as little as £5, through a crowdfunding model.</p>
                            <p class="mb-0">Marked using data provided by the 
                            <a href="https://www.greenfinanceinstitute.co.uk/programmes/ceeb/lcbs/" class="d-inline">Green Finance Institute</a>.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "10c",
                        "name": "Has the council raised income for climate action from any other sources?",
                        "topic": "Funding sources",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria is met if the council has raised any amount of funds for climate action through any of the following: </p>
                            <ul class="mb-0">
                                <li>Energy Service Company</li>
                                <li>Successful grants in relation to climate action (including active travel, bus or other public transport improvements, home retrofit or energy efficiency measures, rewilding, waste reduction, or biodiversity and conservation projects)</li>
                                <li>Joint Ventures/Special Purpose Vehicles </li>
                                <li>Loans (including through Salix Finance or Public Works Loans Board)</li>
                                <li>Procurement policy – Social Value</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p class="mb-0">A joint venture is a partnership between the council and a private company to provide a service or complete a project where both parties share the benefits and losses.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "11a",
                        "name": "Has the council passed a motion in support of divestment from all fossil fuels from the councils’ pension funds?",
                        "topic": "Divestment of Pension Funds",
                        "importance": "Low",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>Points awarded if the motion supports the divestment of the council’s own investments.</p>
                            <p class="mb-0">Points also awarded if the motion supports the divestment of the council’s pension investments.</p>
                            """,
                        "clarifications": """
                            <p>Divestment is the opposite of investment, and consists of stocks, bonds or investment funds that are unethical, and in this case, invested in fossil fuel companies such as Shell, BP and Exxon.</p>
                            <p>Marked using data provided by <a href="https://www.divest.org.uk/council-motions/" class="d-inline">UK Divest</a></p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "11b",
                        "name": "Has the council’s pensions fund committed to divesting from all fossil fuels?",
                        "topic": "Divestment of Pension Funds",
                        "importance": "Medium",
                        "how_marked": "National Data",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Criteria met if the pension fund has committed to partially divesting. For example, it has committed to divesting only from coal, tar sands or oil before 2030.</p>
                            <p class="mb-0">Additional points if the pension fund has committed to divest from all fossil fuels before 2030. </p>
                            """,
                        "clarifications": """
                            <p>Divestment is the opposite of investment, and consists of stocks, bonds or investment funds that are unethical, and in this case, invested in fossil fuel companies such as Shell, BP and Exxon.</p>
                            <p>Where the council does not have control over its own pension investments, such as where the council pension fund is pooled between local authorities, we are looking for a commitment from the pooled pension fund. </p>
                            <p>Marked using data provided by <a href="https://www.divest.org.uk/commitments/" class="d-inline">UK Divest</a></p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "12",
                        "name": "Does the council have direct investments in airports or high carbon intensive energy industries?",
                        "topic": "Council Investments in High Carbon Industries",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Negatively Scored Question</strong></p>
                            <p class="mb-0">Points deducted if the council has direct investments or shares, of any size, in airports or any carbon intensive industries. </p>
                            """,
                        "clarifications": """
                            <p class="mb-0">High carbon intensive industries is defined as coal, oil or gas production (including shale gas or unconventionally gas production).</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA1",
                        "name": "Does the combined authority’s Corporate Plan include a net-zero target and make tackling the climate emergency one of its main priorities?",
                        "topic": "Net-Zero Embedded in Corporate Plan",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if climate action (alternatively called Sustainability or Environment) is listed as one of the combined authority’s core priorities or equivalent. It must have its own heading or section and a net zero target date must be referenced.</p>
                            <p>The net-zero target date must be an area-wide target, either the UK Government’s national target, the devolved nation’s target or the combined authority’s area-wide net zero target.</p>
                            """,
                        "clarifications": """
                            <p>Points will not be awarded if the priority for climate action is part of another priority.</p>
                            <p>It might be called a (Strategic) Economic Plan.</p>
                            <p>We will accept other language for target dates being used such as carbon neutrality.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA1b",
                        "name": "Does the combined authority’s Medium Term Financial Plan include the combined authority’s net-zero target and make tackling the climate emergency one of its main priorities?",
                        "topic": "Net-Zero Embedded in mid-term Financial Plan",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if climate action (alternatively called sustainability or environment) is listed as one of the combined authority’s core priorities or equivalent. It must have its own heading or section and a net-zero target date must be referenced.</p>
                            <p>The net-zero target date must be an area-wide target, either the UK Government’s national target, the devolved nation’s target or the combined authority’s area-wide net-zero target.</p>
                            """,
                        "clarifications": """
                            <p>A mid-term Financial Plan is a plan (often covering four years) which sets out their commitment to provide services that meet the needs of people locally and that represent value for money within the overall resources available to the combined authority.</p>
                            <p>We will accept other language for target dates being used such as carbon neutrality.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA2",
                        "name": "Does the combined authority’s Local Industrial Strategy include a net-zero target and make tackling the climate emergency one of its main priorities?",
                        "topic": "Local Industrial Strategy",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if climate action (alternatively called sustainability or environment) is listed as one of the combined authority’s core priorities or equivalent. It must have its own heading or section and a net-zero target date must be referenced.</p>
                            <p>The net-zero target date must be an area-wide target, either the UK Government’s national target, the devolved nation’s target or the combined authority’s area-wide net-zero target.</p>
                            """,
                        "clarifications": """
                            <p>A Local Industrial Strategy is a strategy led by Mayoral Combined Authorities or Local Enterprise Partnerships which aims to promote the coordination of local economic policy and national funding streams and establish new ways of working between national and local government, and the public and private sectors.</p>
                            <p>All combined authorities will be marked on this question, whether they lead or are just part of the strategy.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA3",
                        "name": "Has the combined authority published a climate change risk register?",
                        "topic": "Climate change risk register",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>This can be part of the combined authority’s overall risk register, or a stand alone document.</p>
                            <p>Point would be awarded if the local authority includes climate related risk on their wider risk register.</p>
                            <p>We are looking for how they are incorporating climate risks as part of its adaptation to climate change therefore we will only accept explicit references to climate environmental risks in the local area (such as flooding, extreme heat, migration, air pollution or others).</p>
                            """,
                        "clarifications": """
                            <p>Criteria met if the combined authority has accurately identified the environmental risks of climate change to the local area, either in a stand alone climate change or adaptation risk register, or incorporated into the combined authority’s corporate risk register. There must be an explicit link between climate change and the increased risk of flooding or other weather events.</p>
                            <p>Adaptation plans are not valid, unless there is a risk register or equivalent within the adaptation plan.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA4a",
                        "name": "Is the combined authority reporting on its own emissions? ",
                        "topic": "Emission data reduction",
                        "importance": "Low",
                        "total_points": "3",
                        "how_marked": "Volunteer Research - CAP updates/council websites",
                        "criteria": """
                            <p>Criteria met if the combined authority is reporting its own emissions and fulfill all of the following:</p>
                            <ul>
                                <li>It states whether they are using the Environmental Reporting Guidelines from Department for Environment, Food and Rural Affairs (DEFRA) or Business and Industrial Strategy (BEIS), the GCoM Common Reporting Framework (CRF), the Greenhouse Gas Accounting Tool (from the LGA), the Greenhouse Gas Protocol for Cities (Community Greenhouse Gas Emissions Inventories) or for Corporate Standards to develop their inventory. </li>
                            </ul>
                            <p>They must state whether they are using either: </p>
                            <ul>
                                <li>the inventory must cover a continuous period of 12 months, either a calendar year or a financial year</li>
                                <li> there must be data from 2019 and 2021 (or the financial year 2021/22)</li>
                                <li>they must be measuring their own scope 1, 2 and 3 emissions</li>
                            </ul>
                            """,
                        "clarifications": """
                                <p>Scope 1 emissions are greenhouse gas emissions that an organisation owns or controls directly, such as fuel burnt from their vehicles.</p>
                                <p>Scope 2 emissions are greenhouse gas emissions that an organisation produces indirectly when they purchase and use energy, such as the emissions created from the electricity the combined authority buys to heat its offices.</p>
                                <p>Scope 3 emissions are greenhouse gas emissions that are created indirectly in an organisations’ supply chain, such as the emissions produced in making the computers or paper that the combined authority buys. Scope 3 also includes any other emissions not within scope 1 and 2.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA4b",
                        "name": "According to the combined authority’s own reporting, have their own emissions reduced since 2019?",
                        "topic": "Emission data reduction",
                        "importance": "High",
                        # "total_points": "3",
                        "how_marked": "Volunteer Research - CAP updates/council websites",
                        "criteria": """
                            <p><strong>Three tier criteria</strong></p>
                            <p>Combined authority must meet the minimum criteria of question 3a to be able to get points for this question.</p>
                            <p>Criteria met if, using the combined authority’s own reporting mechanisms, there has been a 5% or more reduction of scope 1 and 2 emissions when comparing 2019 to 2021 (or financial years 2018/19 to 2021/22) data.</p>
                            <p>Additional points awarded if this emission reduction has been 10% or more, or further points if the reduction has been 20% or more.</p>
                            <p>Further points awarded if there has been any reduction from scope 3 emissions.
                            </p>
                            <p>We recognise that there is currently no standard way that all combined authorities use to report on emissions. We will score combined authorities own calculations, despite the differences, as long as they fulfill the requirements in 3a.</p>
                            """,
                        "clarifications": """
                            <p>Scope 1 emissions are greenhouse gas emissions that an organisation owns or controls directly, such as fuel burnt from their vehicles.</p>
                            <p>Scope 2 emissions are greenhouse gas emissions that an organisation produces indirectly when they purchase and use energy, such as the emissions created from the electricity the combined authority buys to heat its offices.</p>
                            <p>Scope 3 emissions are greenhouse gas emissions that are created indirectly in an organisations’ supply chain, such as the emissions produced in making the computers or paper that the combined authority buys. Scope 3 also includes any other emissions not within scope 1 and 2.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA5",
                        "name": "According to national data, has the combined authority’s area-wide carbon emissions decreased?",
                        "topic": "Emission data reduction",
                        "importance": "Medium",
                        "total_points": "4",
                        "how_marked": "National Data",
                        "criteria": """
                            <p><strong>Three tier criteria</strong></p>
                            <p>Criteria met if the combined authority has had a 2% or more emission reduction from 2019 to 2021 data.</p>
                            <p>Additional points awarded if the emission reduction is more than 5%, or further points if the reduction is more than 10% from 2019 to 2021.</p>
                            """,
                        "clarifications": """
                            <p>Marked using data provided by the Department for Business, Energy and Industrial Strategy. The data that will be used is the percentage difference between the calendar years 2021 and 2019 in the "Local Authority territorial carbon dioxide (CO2) emissions estimates within the scope of influence of Local Authorities" when it is published in Summer 2023.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA6",
                        "name": "Has the combined authority adopted a new governance or decision making process to put tackling the climate emergency at the heart of every decision made?",
                        "topic": "Climate Change Decision Making",
                        "importance": "Medium",
                        "total_points": "3",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Criteria met if climate implications are listed or referenced for all combined authority decisions at their full meetings. Climate implications can be considered through Environmental Implications or an Integrated Impact Assessment if this includes a climate or environmental sub-heading or section.</p>
                            <p>Additional points if the combined authority is using a detailed impact assessment tool to assess the climate implications of all combined authority decisions.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA7",
                        "name": "Has the combined authority embedded climate action and waste reduction into their procurement policies?",
                        "topic": "Procurement",
                        "importance": "Medium",
                        "total_points": "3",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p><strong>Three tier criteria</strong></p>
                            <p>Criteria met if the combined authority has a stand alone environmental or sustainable procurement policy, or a complete section on Sustainable or Responsible Procurement, Climate Change and Action or something similar, within their procurement policy that includes the following.</p>
                            <p>Two or more of the following criteria A must be met to meet the minimum criteria for this point:</p>

                            <ul>
                                <li>The policy makes explicit reference to the combined authority’s Climate Action Plan and zero carbon targets.</li>
                                <li>The policy requests to see the carbon reduction plan of the supplier in the tendering process or asks the supplier to detail any specific steps taken in the design and manufacture of the services to increase energy efficiency and reduce any detrimental environmental impacts.</li>
                                <li>The policy encourages or requires suppliers, through selection processes, to adopt processes and procedures to reduce their environmental impact, including energy consumption and associated carbon emissions, where practicable. For example a combined authority might allocate 5% or more of the tendering overall evaluation score to the environmental actions of the tenderer (the supplier’s contribution to carbon reduction within their own operations or other actions)</li>
                                <li>The policy encourages or requires suppliers, through selection processes, to adopt circular economy processes and procedures where practical.</li>
                            </ul>

                            <p>Additional points if the combined authority has a mandatory requirement for tenders to do any of the following (criteria B):</p>
                            <ul>
                                <li>Demonstrate how they will meet energy efficiency requirements or minimise energy consumption</li>
                                <li>Demonstrate how they will minimise waste in their products and services. This could be through recycled, natural, biodegradable or renewable materials being used, through not using single use plastic or other non-recyclable materials or through ensuring products and services last for as long as possible.</li>
                            </ul>

                            <p>Additional points if the combined authority’s procurement policy includes any of the following (criteria C):</p>
                            <ul>
                                <li>The combined authority aims to source low or zero carbon energy wherever possible.</li>
                                <li>The combined authority aims to phase out the use of fossil fuels from their fleet.</li>
                                <li>The combined authority references the waste hierarchy in its policy, for example by stating that it encourages the combined authority to consider if repeat procurement requests are always needed.</li>
                            </ul>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA8",
                        "name": "Does the combined authority have a Portfolio Holder that has Climate Change explicitly in their remit?",
                        "topic": "Elected Climate Change portfolio holder",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the combined authority has a role such as Chair of Environment Committee or any title or portfolio holder with the words climate change, climate action, climate emergency, environmental sustainability, environment or similar in it.</p>
                            <p>This role can be merged with another role, such as environment and transport or split across multiple roles, such as one named person for sustainable transport and another for low carbon energy. Related role names are valid, such as: (Deputy Portfolio Holder) Low Carbon and Renewable Energy. </p>
                            """,
                        "clarifications": """
                            <p>A Climate Champion (listed as a responsibility) is not valid for a point and neither is Chair or Cabinet member for Environmental Services.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA9",
                        "name": "How many staff spend 50% or more of their time on implementing the Climate Action Plan or other climate change projects?",
                        "topic": "Staff time on climate action",
                        "importance": "Medium",
                        "total_points": "2",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>Criteria is met if there are multiple staff members employed on 3 days a week or more to be working on the combined authority’s Climate Action Plan or other climate change projects equating to a given % of the overall staff team.</p>
                            <p>Data is not currently available to benchmark the exact % of staff that are working on implementing their Climate Action Plan or other climate change projects that will be valid for the points. This will be published with the complete methodology when the Scorecard results are published.</p>
                            """,
                        "clarifications": """
                            <p>Staff is defined as all directly employed combined authority staff (excluding sub/contractors and agency staff). We accept contractors for the role of biodiversity planning officer as long as they are equivalent to 3 days or more a week.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA10",
                        "name": "Have all senior management and councillors in the cabinet or committee chairs received climate awareness training?",
                        "topic": "Carbon literacy/awareness training",
                        "importance": "Low",
                        "total_points": "1",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>Criteria is met if all senior management and current councillors that sit on the combined authority (elected before May 2023) on committees or equivalent have received climate awareness, carbon literacy or equivalent training.</p>
                            """,
                        "clarifications": """
                            <p>If councillors have been trained by the respective local authorities, rather than via the combined authority, this is valid. If staff have been trained elsewhere, that is also valid.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA11",
                        "name": "Does the combined authority have an environmental investment fund that small and medium-sized enterprises and/or the public sector can use?",
                        "topic": "Funding sources",
                        "importance": "High",
                        "total_points": "1",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Point awarded if the combined authority has established a community climate action fund by attracting external investment or similar, provided the following criteria are met:</p>
                            <ul>
                                <li>The fund is at least £100k or higher</li>
                                <li>The financing of the fund has come from attracting external investment.</li>
                                <li>The fund is accessible to small and medium-sized enterprises and/or the public sector</li>
                                <li>More general community or environment funds will be awarded if they specify that climate change projects will be supported.</li>
                            </ul>
                            <p>To account for funding released in stages, the point will be awarded if the funding or support has been offered since 1st January 2022.</p>
                            """,
                        "clarifications": """
                            <p>This is a ring-fenced fund that a combined authority has created by attracting external investment to spend on climate action locally, either in partnership with a local council, or directly by other public sector bodies. </p>
                            <p>A fund created only with existing combined authority funds or only from goverment funding is not valid for a point.</p>
                            <p>The criteria must clearly be about environmental action projects and those who apply must complete some sort of application to define their planned climate action activities. </p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA12a",
                        "name": "Has the combined authority passed a motion in support of divestment from all fossil fuels?",
                        "topic": "Divestment of Pension Funds",
                        "importance": "Medium",
                        "total_points": "2",
                        "how_marked": """<a href="https://www.divest.org.uk/council-motions/">Divest UK data </a>""",
                        "criteria": """
                            <p>Points awarded if the motion supports the divestment of the combined authority’s own investments.</p>
                            <p>Points also awarded if the motion supports the divestment of the combined authority’s pension investments.</p>
                            """,
                        "clarifications": """
                            <p>Divestment is the opposite of investment, and consists of stocks, bonds or investment funds that are unethical, and in this case, invested in fossil fuel companies such as Shell, BP and Exxon.</p>
                            <p>Marked using data provided by <a href="https://www.divest.org.uk/council-motions/" class="d-inline">UK Divest</a></p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA12b",
                        "name": "Has the combined authority’s pensions fund committed to divesting from all fossil fuels?",
                        "topic": "Divestment of Pension Funds",
                        "importance": "Medium",
                        "total_points": "2",
                        "how_marked": """<a href="https://www.divest.org.uk/commitments/ ">Divest UK data </a>""",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Criteria met if the combined authority’s pension fund has committed to partially divesting. For example, it has committed to divesting only from coal, tar sands or oil before 2030.</p>
                            <p>Additional points if the pension fund has committed to divest from all fossil fuels before 2030.</p>
                            """,
                        "clarifications": """
                            <p>Divestment is the opposite of investment, and consists of stocks, bonds or investment funds that are unethical, and in this case, invested in fossil fuel companies such as Shell, BP and Exxon.</p>
                            <p>Where the combined authority does not have control over its own pension investments, such as where the pension fund is pooled between local authorities, we are looking for a commitment from the pooled pension fund.</p>
                            <p>Marked using data provided by <a href="https://www.divest.org.uk/commitments/" class="d-inline">UK Divest</a></p>
                            """,
                    },
                ],
            },
            {
                "title": "Biodiversity",
                "council_types": [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                ],
                "description": "The climate emergency is deeply connected to the ecological emergency. This section looks at what councils can do to protect and increase biodiversity in the area through their direct actions, the management of their green spaces, and biodiversity net gain requirements for developers.",
                "weightings": {
                    "single": "10%",
                    "district": "10%",
                    "county": "10%",
                    "northern-ireland": "10%",
                },
                "questions": [
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "1",
                        "name": "Does the council use peat free compost or soil in all landscaping and horticulture?",
                        "topic": "Peat Free",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council has stopped using peat in soils in all landscaping and horticulture such as parks and council properties. A commitment that the council has stopped using peat compost or soil on their website or biodiversity strategy will be sufficient to meet the criteria.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "2",
                        "name": "Has the council banned the use of pesticides on all council owned and managed land?",
                        "topic": "Pesticides",
                        "importance": "Low",
                        "how_marked": "National Data",
                        "criteria": """
                            <p class="mb-0">Criteria met if a council has banned the use of pesticides in parks and road verges where they have control. This ban must include the street cleaning/weed control team.</p>
                            """,
                        "clarifications": """
                            <p>Banning pesticides includes banning glyphosate and any other pesticides that the council have been using.</p>
                            <p class="mb-0">Marked using data supplied by <a href="https://www.pan-uk.org/pesticide-free-towns-success-stories/" class="d-inline">Pesticide Action Network</a></p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "3",
                        "name": "Has the council committed to mowing their green spaces less for wildlife?",
                        "topic": "Mowing",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council has committed to mow green spaces including parks and road verges less regularly, or if the council has committed to create wildflower habitats within green spaces the local authorities manage.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "england_only": "yes",
                        "code": "4",
                        "name": "Are two thirds of the local wildlife sites in the council’s area in positive conservation management?",
                        "topic": "Wildlife Sites",
                        "importance": "Medium",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>Criteria met if 66% or more of local wildlife sites in the council’s area are in positive conservation management.</p>
                            <p class="mb-0">Only English councils will be assessed on this question, as there is no data available to mark Northern Ireland, Scotland or Wales.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Marked using data provided by <a href="https://www.gov.uk/government/statistical-data-sets/env10-local-sites-in-positive-conservation-management" class="d-inline">DEFRA</a></p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "5",
                        "name": "Does the council have a target to increase tree cover and is a tree management plan agreed as they grow?",
                        "topic": "Tree Cover",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council has a target to increase tree cover which has been included in the Biodiversity Action Plan and/or Tree Strategy, provided the council has agreed a tree management plan that details how new trees will be irrigated and cared for.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "6",
                        "name": "Does the council turn off or dim their street light network to reduce light pollution?",
                        "topic": "Light Pollution",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if any area of the local authority that has been deemed safe to do so has dimmed street lighting or part night lighting. </p>
                            """,
                        "clarifications": """
                            <p>Part night lighting is where councils switch off street lights for part of the night in certain areas. Typically areas with increased risk, such as in the vicinity of pedestrian crossings or with higher nighttime use, will be exempted for safety reasons.</p>
                            <p class="mb-0">Dimming street lighting is where a council will dim street lights for some or all of the night in certain areas, with similar safety exemptions typically in place. LED lights are brighter for the same energy use so have a higher impact on insect populations unless dimmed. Smart dimming street lights, which are dimmer as standard but increase brightness when motion or sound is detected will also be included.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "7",
                        "name": "Have the council’s parks been awarded Green Flag status?",
                        "topic": "Green Flag Awards",
                        "importance": "Low",
                        "how_marked": "National Data",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p class="mb-0">Points awarded for at least one Green Flag park, with further points available for 4 or more Green Flag parks. </p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Marked using data provided by <a href="https://www.greenflagaward.org/award-winners/" class="d-inline">Green Flags UK</a></p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                        ],
                        "code": "8",
                        "name": "Does the council employ a planning ecologist to scrutinise planning reports for biodiversity net gain?",
                        "topic": "Planning Ecologists",
                        "importance": "Medium",
                        "how_marked": "FOI",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council employs a planning ecologist on 3 days or more a week (0.6 FTE).</p>
                            """,
                        "clarifications": """
                            <p>Planning ecologists are ecologists within the planning department.</p>
                            <p class="mb-0">Contracted planning ecologists and permanent planning ecologists will both meet the criteria provided the threshold of 3 or more days a week is met.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                        ],
                        "code": "9",
                        "name": "Does the council require a higher biodiversity net gain commitment from new developments?",
                        "topic": "Biodiversity Net-Gain",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if any policy within the Local Plan states that the council is asking for biodiversity net gain above the minimum 10% required by the UK Government.</p>
                            """,
                    },
                ],
            },
            {
                "title": "Collaboration & Engagement",
                "council_types": [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                    "combined",
                ],
                "description": "This section addresses how councils can collaborate with others to improve their own climate action and to support others in the area to decarbonise. More than half of the emissions cuts needed to reach net zero rely on people and businesses taking up low-carbon solutions, and councils can work with those in their local area to enable those solutions.",
                "weightings": {
                    "single": "10%",
                    "district": "10%",
                    "county": "10%",
                    "northern-ireland": "10%",
                    "combined": "20%",
                },
                "questions": [
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "1",
                        "name": "Do the council’s climate pages include information about behaviour changes that residents can take, and are they easy to find?",
                        "topic": "Council website - information for residents",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the council website has climate pages that are easy for residents to find and include information about what residents can do to reduce their carbon emissions.</p>
                            <p class="mb-0">Information about what residents can do must include links to council initiatives for further support. For example, a suggestion to reduce food waste could include a link to order a food waste caddy.</p>
                            """,
                        "clarifications": """
                            <p>"Easy to find" will be defined as meeting any of the following criteria:</p>
                            <ul>
                                <li>Within 5 clicks of the homepage</li>
                                <li>Searchable on the site search bar using any of the phrases ‘climate change’, ‘climate emergency’, ‘climate action’ or ‘environment’</li>
                                <li>There is an environment and/or climate section in the drop down menu</li>
                            </ul>
                            <p class="mb-0">Links for further support can include links to collaborative initiatives with other councils.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "2a",
                        "name": "Has the council published a climate action plan with SMART targets?",
                        "topic": "Climate Action Plan",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council has published a climate action plan that covers the area and includes references to SMART targets since September 2015.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">This question will be marked using the criteria for Q3.12.1 of the Climate Action Plan Scorecards.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "2b",
                        "name": "Has the council published an up to date and easy-to-read annual report on their Climate Action Plan?",
                        "topic": "Published Annual report",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Points awarded for each of the following criteria:</p>
                            <ul class="mb-0">
                                <li>The council has published an annual report since 1st January 2022</li>
                                <li>The annual report is easy-to-read</li>
                                <li>The annual report includes reporting on progress towards the council’s climate action plan SMART targets.</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>We have chosen the date 1st of January 2022 to ensure that the report is being issued on a yearly basis, while allowing for some delays.</p>
                            <p>“Easy to read” will be defined as clearly meant for public reading, and may include features such as a contents page, an executive summary, definitions for acronyms or complex language, simple English wherever possible, and graphics or tables to aid comprehension and navigation.</p>
                            <p class="mb-0">Scottish councils are obliged to publish statutory annual reports which will meet the criteria for an annual report, but they must release a more easy-to-read version with reference to SMART targets for further points.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "3",
                        "name": "Has the council lobbied the government for climate action?",
                        "topic": "Councils lobbying government",
                        "importance": "Medium",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>Criteria met if the council has sent a letter or had a meeting with national or devolved governments calling for the government to take further action, or asking for councils to receive more funding, powers and climate resources to take climate action.</p>
                            <p class="mb-0">The criteria will be met if councils have worked on specific, climate-related issues, provided climate is cited as a reason to take action. For example, asking for measures to improve local bus provision will meet the criteria if reducing carbon emissions is cited as a reason to do so.</p>
                            """,
                        "clarifications": """
                            <p>We have chosen the date 1st of January 2022 to ensure that the report is being issued on a yearly basis, while allowing for some delays.</p>
                            <p class="mb-0">The criteria will be met if councils have worked on specific, climate-related issues, provided climate is cited as a reason to take action. For example, asking for measures to improve local bus provision will meet the criteria if reducing carbon emissions is cited as a reason to do so.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "4",
                        "name": "Is the council working with external partners or other councils to seek to influence national governments on climate action, or to learn about and share best practice on council climate action?",
                        "topic": "Sharing best practice between councils",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Point awarded for membership or contributing case studies for at least one of the following organisations, with a further point available for membership or contributing case studies for three or more of the following organisations.</p>
                            <p>Membership organisations:</p>
                            <ul>
                                <li>UK100 (Including the Countryside Climate Network)</li>
                                <li>ADEPT</li>
                                <li>Blueprint Coalition</li>
                                <li>ICLEI</li>
                                <li>Carbon Neutral Cities</li>
                                <li>UK Green Building Council</li>
                                <li> Sustainable Scotland Network</li>
                                <li>Carbon Disclosure Project (including submitting to the CDP since 2019)</li>
                            </ul>
                            <p>Case studies:</p>
                            <ul>
                                <li>Friends of the Earth & Ashden case studies</li>
                                <li>LGA (Local Government Association) climate change case studies</li>
                                <li>UK100 case studies</li>
                                <li>WRAP case studies</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>Further networks or case studies may be added on a case basis if a comparable standard of quality is met. </p>
                            <p class="mb-0">Working with climate consultants, while important, will not be scored as part of this question.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "5a",
                        "name": "Does the council have an ongoing way for residents to influence the implementation of the council’s Climate Action Plan?",
                        "topic": "Residents engagement",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Point awarded if the council has established a way for residents to influence the implementation of the council’s climate action. This may be through:</p>
                            <ul>
                                <li>A community engagement group</li>
                                <li>Introducing community, resident or activist representation on a council climate change committee/group</li>
                                <li>Convening or using a local climate action network to improve the implementation of their climate action plan</li>
                                <li>Broader forms of community engagement work such as a series of workshops across the area for different groups of residents. </li>
                            </ul>
                            <p class="mb-0">A further point will be awarded if there is an overarching framework such as a dedicated climate public engagement plan to inform this work. </p>
                            """,
                        "clarifications": """
                            <p class="mb-0">The way that councils engage with residents can include time bound engagement work such as climate assemblies provided they have been held since 1st January 2022. This is to ensure that the work is ongoing.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "5b",
                        "name": "Does the council’s ongoing engagement with residents include those most affected by climate change and climate action policy?",
                        "topic": "Representative residents engagement",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Point awarded if the council’s ongoing engagement (under 5a) specifically aims to engage those most affected by climate change and climate action policies.</p>
                            <p class="mb-0">A further point available if the council’s climate action plan has undergone an equalities impact assessment to identify who is most affected by climate change and climate action policies.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Who is most affected by climate change and climate action policies depends on the local context. Therefore, this could include any community or group of people provided the council has specified they are more affected. For example, this may include people who live near rivers with increasing risk of flooding, or people with physical disabilities who can be affected by policies to reduce traffic and increase active travel such as clean air zones.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "6",
                        "name": "Does the council provide funding for community climate action, for example through an environment fund or climate action fund?",
                        "topic": "Funding for community climate action",
                        "importance": "High",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met for a ring-fenced fund that a council has created to spend on climate action locally, either in partnership with the council or for other organisations or volunteer and community groups. The fund must fulfill the following criteria:</p>
                            <ul>
                                <li>The fund is at least £10k in size. Where the overall amount of funding has not been stated, it will be assumed that funds awarding individual grants over £1k in size have a total fund of at least £10k.</li>
                                <li>The fund is accessible to community groups, including, where relevant, parish councils.</li>
                                <li>The funding has been open to applications at some point since 1st January 2022, in order to include funds released in waves that may not be open at the time of marking.</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>More general community or environment funds will be included if they specify that climate change and biodiversity/ecological projects will be supported.</p>
                            <p class="mb-0">This can be a pooled fund between multiple councils.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "7",
                        "name": "Is the council working in partnership with health services on active travel, home insulation, air pollution, green spaces or other climate action policies?",
                        "topic": "Health Services Partnership",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council has embedded health services into their climate change work or if they have embedded climate change into their health partnership work. This includes embedding climate impacts into the Joint Strategic Needs Assessment (JSNA).</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">For example, the criteria might be met by including climate experts such as scientists, policy makers and representatives from environmental NGOs on Health and Wellbeing boards and regularly including climate change on the agenda.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "8",
                        "name": "Is the council working in partnership with cultural institutions and organisations to encourage decarbonisation within culture and arts locally?",
                        "topic": "Partnerships - Culture",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if there is a partnership between the council and local sports, arts and cultural partnerships, provided the partnership includes any one of the following: funding for climate work, evidence of co-creation with community groups, the decarbonisation of cultural buildings including targets, initiatives that encourage behaviour change such as sustainable travel incentives, or a focus on climate justice.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "9",
                        "name": "Is the council working in partnership with schools or other education settings to deliver climate action that young people can engage with?",
                        "topic": "Partnerships - young people",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the council supports schools or other education settings by running any of the following schemes in more than one school:</p>
                            <ul class="mb-0">
                                <li>EnergySparks or equivalent auditing schemes which require local authority support.</li>
                                <li>Solar schools or other visible low-carbon interventions.</li>
                                <li>Democratic engagement work in schools or other education settings to connect young people to climate decision making, including establishing youth climate panels or parliaments and holding youth climate summits for schools in the area.</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p class="mb-0">This can include initiatives with other councils including county and district partnerships, provided that the council signposts this work from their website.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "10",
                        "name": "Is the council working in partnership with local businesses to encourage decarbonisation?",
                        "topic": "Partnerships - Businesses",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council provides support or free tailored advice to businesses in the local area to decarbonise, including through collaborative measures with local businesses, other local authorities, or via the Local Enterprise Partnership.</p>
                            """,
                        "clarifications": """
                            <p>Examples of support for businesses to decarbonise include funding environmental audits for businesses, free training such as carbon literacy training, or grants to support businesses to decarbonise their properties.</p>
                            <p class="mb-0">This can include initiatives with other councils including county and district partnerships, provided that the council signposts this work from their website. This question will include schemes that have been available at some point since 1st January 2022, in order to include funds released in waves that may not be open at the time of marking.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "11",
                        "name": "Has the council passed a motion to ban high carbon advertising and sponsorship?",
                        "topic": "Communications - advertising",
                        "importance": "High",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>A point will be awarded if the council has passed a motion to ban high carbon advertising on ad sites it controls by introducing a low carbon advertising and sponsorship policy or similar.</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">High carbon advertising includes advertisements for products and activities that emit high amounts of CO2 emissions such as fossil fuels and fossil fuel companies, diesel, petrol and hybrid car engines and air travel.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA1a",
                        "name": "Has the combined authority published a climate action plan with SMART targets?",
                        "topic": "Climate Action Plan SMART targets",
                        "importance": "High",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the combined authority has published a climate action plan that covers the area and includes references to SMART targets since September 2015.</p>
                            """,
                        "clarifications": """
                            <p>This question will be marked using the criteria for Q3.12.1 of the Climate Action Plan Scorecards.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA1b",
                        "name": "Has the combined authority published an up to date and easy-to-read annual report on their Climate Action Plan?",
                        "topic": "Published Annual report",
                        "importance": "High",
                        "total_points": "3",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Points awarded for each of the following criteria:</p>
                            <ul>
                                <li>The combined authority has published an annual report since 1st January 2022</li>
                                <li>The annual report is easy-to-read</li>
                                <li>The annual report includes reporting on progress towards the council’s climate action plan SMART targets.</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>We have chosen the date 1st of January 2022 to ensure that the report is being issued on a yearly basis, while allowing for some delays.</p>
                            <p>"Easy to read" will be defined as clearly meant for public reading, and may include features such as a contents page, an executive summary, definitions for acronyms or complex language, simple English wherever possible, and graphics or tables to aid comprehension and navigation.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA2",
                        "name": "Has the combined authority commissioned a study of available decarbonisation pathways for their area?",
                        "topic": "Decarbonisation pathways",
                        "importance": "Medium",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the combined authority has commissioned a study of different decarbonisation pathways and scenarios to reach net zero carbon across the region by the local area-wide target.</p>
                            """,
                        "clarifications": """
                            <p>Decarbonisation pathways are modelled projected scenarios of policy, technology & behaviour change over time to reach net zero carbon emissions. They are a science-based approach to climate policymaking. The CCC’s <a href="https://www.theccc.org.uk/publication/sixth-carbon-budget/" class="d-inline">Sixth Carbon Budget report</a> includes a national example. These pathways are most effective when a specific pathway is chosen and implemented.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA3a",
                        "name": "Has the combined authority lobbied the government for more funding, powers and climate resources?",
                        "topic": "Lobbying government",
                        "importance": "Medium",
                        "total_points": "1",
                        "how_marked": "FOI",
                        "criteria": """
                            <p>Criteria met if the combined authority has sent a letter or had a meeting with national or devolved governments calling for the government to take further action, or asking for councils and combined authorities to receive more funding, powers and climate resources to take climate action.</p>
                            """,
                        "clarifications": """
                            <p>The criteria will be met if combined authorities have worked on specific, climate-related issues, provided climate is cited as a reason to take action. For example, asking for measures to improve local bus provision will meet the criteria if reducing carbon emissions is cited as a reason to do so.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA3b",
                        "name": "Has the combined authority or its mayor publicly called for more climate action from the Government or other organisations?",
                        "topic": "Lobbying government",
                        "importance": "Low",
                        "total_points": "2",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Point awarded for signing or supporting at least 2 open letters or public statements, including those led by other combined authorities or organisations.</p>
                            <p>A further point will be awarded if the combined authority or its mayor has led at least one open letter or public statement.</p>
                            """,
                        "clarifications": """
                            <p>We will consider combined authority website announcements and press releases as well as local or national news coverage when marking this question. The same open letter or public statement receiving coverage in several news sites will only be counted once.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA4",
                        "name": "Is the combined authority working with external partners or other councils to lobby national government for climate action, or to learn about and share best practice council climate action?",
                        "topic": "Sharing best practice",
                        "importance": "Low",
                        "total_points": "2",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Point awarded for membership or contributing case studies for at least one of the following organisations, with a further point available for membership or contributing case studies for three or more of the following organisations.</p>
                            <p>Membership organisations:</p>
                            <ul>
                                <li>UK100</li>
                                <li>ADEPT</li>
                                <li>Blueprint Coalition</li>
                                <li>ICLEI</li>
                                <li>Carbon Neutral Cities</li>
                                <li>C40 Cities</li>
                                <li>Carbon Disclosure Project (including submitting to the CDP since 2019)</li>

                            </ul>

                            <p>Case studies:</p>
                            <ul>
                                <li></li>
                                <li>Friends of the Earth & Ashden case studies</li>
                                <li>UK100 case studies</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>Further networks or case studies may be added on a case basis if a comparable standard of quality is met.</p>
                            <p>Working with climate consultants, while important, will not be scored as part of this question.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA5a",
                        "name": "Does the combined authority have an on-going way for residents to influence the implementation of the combined authority’s Climate Action Plan?",
                        "topic": "Ongoing resident engagement",
                        "importance": "High",
                        "total_points": "2",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Point awarded if the council has established a way for residents to influence the implementation of the council’s climate action. This may be through:</p>
                            <ul>
                                <li>a community engagement group </li>
                                <li>introducing community, resident or activist representation on a council climate change committee/group</li>
                                <li>convening or using a local climate action network to improve the implementation of their climate action plan</li>
                                <li>broader forms of community engagement work such as a series of workshops across the area for different groups of residents. </li>
                            </ul>

                            <p>A further point will be awarded if there is an overarching framework such as a dedicated climate public engagement plan to inform this work.</p>
                            """,
                        "clarifications": """
                            <p>The way that councils engage with residents can include time bound engagement work such as climate assemblies provided they have been held since 1st January 2022. This is to ensure that the work is ongoing.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA5b",
                        "name": "Does the combined authority’s ongoing engagement with residents include those most affected by climate change and the transition?",
                        "topic": "Representative ongoing engagement",
                        "importance": "Medium",
                        "total_points": "2",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Point awarded if the combined authority’s ongoing engagement (under 5a) specifically aims to engage those most affected by climate change and climate action policies.</p>
                            <p>A further point available if the combined authority’s climate action plan has undergone an equalities impact assessment to identify who is most affected by climate change and climate action policies.</p>
                            """,
                        "clarifications": """
                            <p>Who is most affected by climate change and climate action policies depends on the local context. Therefore, this could include any community or group of people provided the combined authority has specified they are more affected. For example, this may include people who live near rivers with increasing risk of flooding, or people with physical disabilities who can be affected by policies to reduce traffic and increase active travel such as clean air zones.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA6",
                        "name": "Has the combined authority supported a research project into climate action in their region?",
                        "topic": "Research",
                        "importance": "Low",
                        "total_points": "2",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the combined authority has funded or commissioned area-wide research to increase understanding of the local challenge and support constituent councils. </p>
                            """,
                        "clarifications": """
                            <p>Research projects may include area-wide opinion polling on behaviour change and climate interventions, research on nature-based flood mitigation opportunities, or any similar research to inform local climate policymaking.</p>
                            <p>Research on retrofitting will not be included in this question as it is marked in Buildings & Heating & Green Skills Q4.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA7",
                        "name": "Has the combined authority created a climate change commission or similar?",
                        "topic": "Climate change commission",
                        "importance": "Medium",
                        "total_points": "1",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the combined authority has created a climate commission or other similar body, to bring together experts and stakeholders, provide independant advice and guide climate policy in the area.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA8",
                        "name": "Is the combined authority working in partnership with local businesses to encourage decarbonisation?",
                        "topic": "Partnerships - Businesses",
                        "importance": "Low",
                        "total_points": "2",
                        "how_marked": "Volunteer research",
                        "criteria": """
                            <p>Criteria met if the combined authority has 3 or more schemes to provide free support or free tailored advice to businesses in the local area to decarbonise, including through collaborative measures with local businesses, other local authorities, or via the Local Enterprise Partnership. </p>
                            <p><strong>One single overarching scheme with three different approaches to support local businesses will also be awarded the point.</strong></p>
                            """,
                        "clarifications": """
                            <p>Examples of support for businesses to decarbonise include free environmental audits for businesses, free training such as carbon literacy training, or grants to support businesses to decarbonise their properties.</p>
                            <p>This question excludes green skills-specific schemes, which are covered in the Buildings & Heating & Skills section</p>
                            <p>This question will include schemes that have been available at some point since 1st January 2022, in order to include funds released in waves that may not be open at the time of marking.</p>
                            """,
                    },
                    {
                        "council_types": ["combined"],
                        "code": "CA9",
                        "name": "Has the combined authority committed to ban high carbon advertising & sponsorship?",
                        "topic": "Communications - advertising",
                        "importance": "Medium",
                        "total_points": "1",
                        "how_marked": "National data",
                        "criteria": """
                            <p>A point will be awarded if the combined authority has made a commitment to ban high carbon advertising on ad sites it controls by introducing a low carbon advertising and sponsorship policy or similar.</p>
                            """,
                        "clarifications": """
                            <p>High carbon advertising includes advertisements for products and activities that emit high amounts of CO2 emissions such as fossil fuels and fossil fuel companies, diesel, petrol and hybrid car engines and air travel.</p>
                            <p>Ad sites that the combined authority may control includes bus stops and other transport sites.</p>
                            """,
                    },
                ],
            },
            {
                "title": "Waste Reduction & Food",
                "council_types": [
                    "single",
                    "district",
                    "county",
                    "northern-ireland",
                ],
                "description": "This section looks at the influencing role councils can play in supporting sustainable food production on their land and in their schools, and circular economy initiatives locally. Councils also have an important role to play in waste and recycling locally and improving this.",
                "weightings": {
                    "single": "10%",
                    "district": "10%",
                    "county": "10%",
                    "northern-ireland": "10%",
                },
                "questions": [
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "1a",
                        "name": "Has the council reduced single use plastic in its buildings and events?",
                        "topic": "Single Use Plastic",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the council has successfully stopped using some single use plastic in the council office buildings and events. This excludes schools, leisure centres and other council buildings. </p>
                            <p>Points will be awarded if the council has done 2 or more of the following</p>
                            <ul class="mb-0">
                                <li>Installing water drinking fountains on the council estate/public spaces</li>
                                <li>Banning plastic cups for water</li>
                                <li>Reducing plastic packaging</li>
                                <li>Reducing the use of two or more of the following: plastic cutlery (forks, knives, spoons, chopsticks), plates, balloon sticks or food and cup containers made of expanded polystyrene; including their covers and lids at their external events. </li>
                            </ul>
                            """,
                        "clarifications": """
                            <p class="mb-0">Single use plastic or disposable plastics are used only once before they are thrown away or recycled. They are made from fossil fuels like petroleum and can be very hard to recycle. </p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "1b",
                        "name": "Has the council reduced single use plastic at external events on council land, property or public spaces such as roads and parks?",
                        "topic": "Single Use Plastic",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p><strong>Two tier criteria</strong></p>
                            <p>Point awarded if the council requires event organisers to provide additional information about their environmental commitments that make reference to single use plastic or items that will be used that will be recyclable, compostable or reusable (such as a cup refill scheme).</p>
                            <p class="mb-0">Further points awarded if the council has banned the use of all of the following at these external events: plastic cutlery (forks, knives, spoons, chopsticks), plates, balloon sticks or food and cup containers made of expanded polystyrene; including their covers and lids.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "2",
                        "name": "Has the council taken steps to support a circular economy locally?",
                        "topic": "Circular Economy",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the council has done 2 or more of the following: </p>
                            <ul class="mb-0">
                                <li>Provided funding or space provided for a repair cafe or similar </li>
                                <li> Provided funding or space for exchange shops or similar</li>
                                <li>Signed up as part of circular economy project </li>
                            </ul>
                            """,
                        "clarifications": """
                            <p>A circular economy is a model of production and consumption, which involves sharing, leasing, reusing, repairing, refurbishing and recycling existing materials and products as long as possible.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "3",
                        "name": "Does the council support initiatives to redistribute surplus food?",
                        "topic": "Surplus Food",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council supports an organisation that redistributes surplus food within the area through funding, staff or other ways (such as being listed as a partner of the project).</p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Surplus food is food that can no longer be sold or used in shops or restaurants even though it is still good to eat. Without redistributing this food, that often comes from supermarkets, restaurants or other businesses, it would go to waste or in landfill.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "4a",
                        "name": "Does the council have a sustainable food strategy?",
                        "topic": "Food Strategy",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the strategy or work plan covers the whole council area (sometimes called place-based) and includes sections on sustainable food or the climate impacts of food. </p>
                            <p class="mb-0">The strategy must cover 6 months or more. </p>
                            """,
                        "clarifications": """
                            <p class="mb-0">The strategy can not be for council only operations, or only focus on healthy eating and obesity. </p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "4b",
                        "name": "Is the council part of a sustainable food partnership?",
                        "topic": "Food Partnership",
                        "importance": "Medium",
                        "how_marked": "National Data and Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council is listed on the Sustainable Food Places membership list, or, if there is evidence that the council is part of a sustainable food partnership that fulfills the same criteria as Sustainable Food Places membership. The council can either lead the partnership or be a key member, such as on the steering group. </p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Marked using <a href="https://www.sustainablefoodplaces.org/members/" class="d-inline">Sustainable Food Places membership list</a> .</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "5a",
                        "name": "Has the council taken steps to support local food growing?",
                        "topic": "Local Food Growing",
                        "importance": "Low",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                        <p>Criteria met if the council has proactively created more space for local food growing through providing funding, land, staff or other resources to support:</p>
                        <ul class="mb-0">
                            <li>Community orchard</li>
                            <li>Schools to have growing spaces</li>
                            <li>Community or city farms or gardens, including edible fruit/veg/herbs patches in public spaces such as parks, rooftops or grass verges.</li>
                        </ul>
                            """,
                        "clarifications": """
                            <p class="mb-0">Allotment space is not included in this question as it is a statutory requirement for councils to provide allotments.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "county"],
                        "code": "6",
                        "name": "Do schools in the council area serve less meat in school meals?",
                        "topic": "School Catering",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p>Criteria met if the council does any one of the following: </p>
                            <ul class="mb-0">
                                <li>There is one complete vegetarian only day a week on the school menu on the council website</li>
                                <li>The council’s in-house catering has a policy to reduce meat in meals by 20% and provide plant-based alternatives, or runs a meat-free mondays or other vegetarian only days in schools </li>
                                <li>The council requires external catering providers for schools to reduce meat in meals by 20% and provide plant-based alternatives, or runs a meat-free mondays or other vegetarian only days in schools.</li>
                            </ul>
                            """,
                        "clarifications": """
                            <p class="mb-0">Schools includes primary, junior or secondary schools that are state-run schools. Schools excludes private schools or academies.</p>
                            """,
                    },
                    {
                        "council_types": ["single", "district", "northern-ireland"],
                        "code": "7",
                        "name": "Does the council provide kerbside food waste recycling?",
                        "topic": "Kerbside Food Waste Recycling",
                        "importance": "Medium",
                        "how_marked": "Volunteer Research",
                        "criteria": """
                            <p class="mb-0">Criteria met if the council provides kerbside food waste recycling to most homes in the area.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "8",
                        "name": "How high is the councils’ area wide annual recycling rate?",
                        "topic": "Recycling Rate",
                        "importance": "Medium",
                        "how_marked": "National Data",
                        "criteria": """
                            <p><strong>Three tier criteria</strong></p>
                            <p>Criteria met if the council has a recycling rate of 50% or more.</p>
                            <p class="mb-0">Additional points awarded if the council has a recycling rate of 60% and further points awarded if the council has a recycling rate of 70% or more. </p>
                            """,
                        "clarifications": """
                            <p class="mb-0">Marked using data provided by DEFRA, Stats Wales, SEPA and DAERA-NI.</p>
                            """,
                    },
                    {
                        "council_types": [
                            "single",
                            "district",
                            "county",
                            "northern-ireland",
                        ],
                        "code": "9",
                        "name": "How low is the councils’ area wide level of household waste produced?",
                        "topic": "Household Waste Amount",
                        "importance": "Low",
                        "how_marked": "National Data",
                        "criteria": """
                            <p>Criteria met if the annual residual waste in kg per household in the area is 300-400kg per household.</p>
                            <p>Further points awarded if the annual residual waste in kg per household in the area is under 300kg per household.</p>
                            <p class="mb-0">This question is scoring councils on the amount of residual waste (kg) per household in each council.</p>
                            """,
                        "clarifications": """
                            <p>Residual waste includes waste sent to landfill and incineration. It excludes waste that is recycled or composted.</p>
                            <p class="mb-0">Marked using data provided by DEFRA, Stats Wales and SEPA</p>
                            """,
                    },
                ],
            },
        ]
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
