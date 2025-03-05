import re
from collections import defaultdict
from os.path import exists, join
from pathlib import Path
from random import randint, sample, shuffle
from typing import Any

import mailchimp_marketing as MailchimpMarketing
import markdown
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import (
    Avg,
    Case,
    Count,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template import Context, Template
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils.safestring import mark_safe
from django.views.generic import DetailView, ListView, TemplateView, View
from django_filters.views import FilterView
from haystack.generic_views import SearchView as HaystackSearchView
from mailchimp_marketing.api_client import ApiClientError

import caps.charts as charts
from caps.forms import HighlightedSearchForm
from caps.helpers.council_navigation import council_menu
from caps.mapit import (
    BadRequestException,
    ForbiddenException,
    InternalServerErrorException,
    MapIt,
    NotFoundException,
)
from caps.models import (
    ComparisonLabel,
    ComparisonType,
    Council,
    CouncilFilter,
    CouncilProject,
    CouncilTag,
    DataPoint,
    DataType,
    PlanDocument,
    ProjectFilter,
    SavedSearch,
    Tag,
)
from caps.search_funcs import condense_highlights
from caps.utils import file_size, is_valid_postcode
from charting import ChartCollection
from scoring.models import PlanScore, PlanSection, PlanSectionScore, PlanYear


def add_context_for_plans_download_and_search(context):
    # Takes a context object (eg: from inside get_context_data) and adds the
    # necessary context for the plans-download-and-search.html partial.
    context["total_councils"] = Council.current_councils().count()
    context["total_plans"] = PlanDocument.objects.all().count()
    context["percent_councils_with_plan"] = Council.percent_with_plan()
    # can't shuffle querysets because they don't support assignment
    context["popular_searches"] = [s for s in SavedSearch.objects.most_popular()[:6]]
    shuffle(context["popular_searches"])
    context["last_update"] = PlanDocument.objects.aggregate(Max("updated_at"))[
        "updated_at__max"
    ]
    plan_file = join(settings.MEDIA_ROOT, "data", "plans", "plans.zip")
    plan_size = file_size(plan_file)
    context["plan_zip_size"] = plan_size
    return context


class HomePageView(TemplateView):
    template_name = "caps/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_councils"] = Council.current_councils()
        context = add_context_for_plans_download_and_search(context)
        context["page_title"] = "Tracking the UK's journey towards carbon zero"
        return context


class AssemblyView(TemplateView):
    template_name = "caps/assembly.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_councils"] = Council.current_councils()
        context["assembly_councils"] = Council.current_councils().filter(
            plandocument__document_type=PlanDocument.CITIZENS_ASSEMBLY
        )
        context["percent_councils_with_assembly"] = int(
            (context["assembly_councils"].count() / context["all_councils"].count())
            * 100
        )
        context = add_context_for_plans_download_and_search(context)
        context["page_title"] = "Local Climate Assemblies - CAPE"
        context["page_description"] = (
            "Search and view reports from local climate assemblies."
        )
        return context


class CouncilDetailView(DetailView):
    model = Council
    context_object_name = "council"
    template_name = "caps/council_detail.html"

    def get_polling_context(self, council: Council) -> dict[str, Any]:
        """
        Get polling information for this council
        """
        context = {}
        polling_data = council.data_points(DataType.DataCollection.POLLING)

        # transform this into a double list so I can access a specific percentage like
        # data["OnwardsUK"]["Q5"]
        data = defaultdict(dict)
        for d in polling_data:
            data[d.data_type.name_in_source][
                d.data_type.name.replace(".", "_")
            ] = d.value

        context["polling_data"] = data
        return context

    def get_emissions_context(self, council: Council) -> dict[str, Any]:
        """
        Get emissions information for this council
        """
        council_emissions_data = council.data_points(DataType.DataCollection.EMISSIONS)
        context = {}
        context["emissions_data"] = False
        try:
            latest_year = council_emissions_data.aggregate(Max("year"))["year__max"]
            context["latest_year"] = latest_year
            latest_year_per_capita_emissions = council_emissions_data.get(
                year=latest_year, data_type__name="Per Person Emissions"
            ).value
            latest_year_per_km2_emissions = council_emissions_data.get(
                year=latest_year, data_type__name="Emissions per km2"
            ).value
            latest_year_total_emissions = council_emissions_data.get(
                year=latest_year, data_type__name="Total Emissions"
            ).value
            context["latest_year_per_capita_emissions"] = (
                latest_year_per_capita_emissions
            )
            context["latest_year_per_km2_emissions"] = latest_year_per_km2_emissions
            context["latest_year_total_emissions"] = latest_year_total_emissions
            context["emissions_data"] = True
        except DataPoint.DoesNotExist as e:
            pass

        if context["emissions_data"]:
            context["current_emissions_breakdown"] = (
                council.current_emissions_breakdown(year=latest_year)
            )
            multi_emission_chart = charts.multi_emissions_chart(council, latest_year)
            context["chart_collection"] = ChartCollection()
            context["chart_collection"].register(multi_emission_chart)

        return context

    def get_scorecard_context(self, council: Council) -> dict[str, Any]:
        """
        Get the scorecard information for this council
        """
        context = {}
        try:
            plan_year = PlanYear.objects.get(is_current=True)
            plan_score = PlanScore.objects.get(council=council, year=plan_year.year)

            group = council.get_scoring_group()

            average_total = PlanScore.objects.filter(
                total__gt=0,
                council__authority_type__in=group["types"],
                council__country__in=group["countries"],
                year=2023,
            ).aggregate(average_score=Avg("weighted_total"))

            sections = PlanSectionScore.sections_for_council(
                council=council, plan_year=plan_year.year
            )

            # get average section scores for authorities of the same type
            section_avgs = PlanSectionScore.get_all_section_averages(
                council_group=group, plan_year=plan_year.year
            )

            for section in section_avgs.all():
                print(section)
                if section["plan_section__code"] not in sections:
                    sections[section["plan_section__code"]] = {
                        "code": section["plan_section__code"],
                        "top_performer": False,
                    }

                sections[section["plan_section__code"]]["avg"] = round(
                    section["avg_score"], 1
                )

            context["scoring_group"] = group
            context["scoring_score"] = plan_score
            context["scoring_sections"] = sorted(
                sections.values(), key=lambda section: section["code"]
            )

            context["average_total"] = average_total["average_score"]

            top_scoring_sections = [
                section for section in sections.values() if section["top_performer"]
            ]

            if plan_score.top_performer or top_scoring_sections:
                context["scoring_accolades"] = {
                    "overall": plan_score.top_performer,
                    "num_sections": len(top_scoring_sections),
                }
                if len(top_scoring_sections) > 0:
                    context["scoring_accolades"]["example_section"] = (
                        top_scoring_sections[0]["description"]
                    )

            context["scoring_hidden"] = getattr(settings, "SCORECARDS_PRIVATE", False)

        except PlanScore.DoesNotExist:
            print("Plan missing!!")
            context["scoring_hidden"] = True

        return context

    def get_project_context(self, council: Council) -> dict[str, Any]:
        """
        Get the emissions project info for Scottish councils
        """
        context = {}
        project_stats = {"total_projects": 0, "total_savings": 0, "total_cost": 0}
        projects = CouncilProject.objects.filter(council=council).order_by("start_year")
        for project in projects.all():
            project_stats["total_savings"] = (
                project_stats["total_savings"] + project.emission_savings
            )
            project_stats["total_cost"] = (
                project_stats["total_cost"] + project.capital_cost
            )
            project_stats["total_projects"] = project_stats["total_projects"] + 1
        project_stats["total_savings"] = project_stats["total_savings"] / 1000

        context["project_stats"] = project_stats
        return context

        context["page_title"] = council.name

        if council.emergencydeclaration_set.count() > 0:
            context["declared_emergency"] = council.emergencydeclaration_set.all()[0]

    def get_document_context(self, council: Council) -> dict[str, Any]:
        """
        Get information on the documents associated with this council
        """
        context = {}
        documents = council.plandocument_set.order_by(
            "-created_at", "-updated_at"
        ).all()
        context["document_count"] = documents.count()
        grouped_documents = defaultdict(list)
        for document in documents:
            grouped_documents[document.get_document_type].append(document)

        context["documents"] = documents

        deletions = PlanDocument.history.filter(council=council).order_by(
            "history_date"
        )
        for change in deletions.all():
            if change.history_type == "-":
                change.is_deleted = True
                grouped_documents[
                    PlanDocument.get_document_type_from_code(change.document_type)
                ].append(change)
                change.file_exists = exists(change.file)

        # need to convert to a dict as items doesn't work on defaultdicts
        # in django templates
        context["grouped_documents"] = dict(grouped_documents)
        if "citizens' assembly" in context["grouped_documents"]:
            # just pull this into a smaller dictionary
            context["grouped_documents_assembly"] = {
                "citizens' assembly": context["grouped_documents"]["citizens' assembly"]
            }
        else:
            context["grouped_documents_assembly"] = {}

        return context

    def get_council_card_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Return the council cards that are valid for this council
        """

        banned_items = []

        council = context["council"]
        # if not a scottish council, knock out emissions reduction projects
        if council.country != Council.SCOTLAND:
            banned_items.append("emissions-reduction-projects")

        # if not a new council, knock out new council details
        if not council.is_new_council():
            banned_items.append("new-council")

        # if not an old council, knock out old council details
        if not council.is_old_council():
            banned_items.append("old-council")

        # remove scorecard if the hidden flag is set
        if context["scoring_hidden"]:
            banned_items.append("scorecard")

        if not context["polling_data"]:
            banned_items.append("local-polling")

        if not context["grouped_documents_assembly"]:
            banned_items.append("climate-assembly")

        menu = [item for item in council_menu if item.slug not in banned_items]
        summary_menu = [item for item in menu if item.list_in_summary]

        return {"council_cards": menu, "summary_menu_cards": summary_menu}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council: Council = context.get("council")

        additional_contexts = [
            self.get_emissions_context(council),
            self.get_polling_context(council),
            self.get_scorecard_context(council),
            self.get_project_context(council),
            self.get_document_context(council),
        ]
        for additional_context in additional_contexts:
            context.update(additional_context)

        # run menu update last so it can have access to wider context
        context.update(self.get_council_card_context(context))

        # get postcode from 'pc' cookie if set
        context["postcode"] = self.request.COOKIES.get("pc")

        context["page_title"] = council.name
        context["feedback_form_url"] = settings.FEEDBACK_FORM

        context["related_councils"] = council.get_related_councils()
        context["promises"] = council.promise_set.filter(has_promise=True).order_by(
            "target_year"
        )
        context["no_promise"] = council.promise_set.filter(has_promise=False)
        context["last_updated"] = council.plandocument_set.aggregate(
            last_update=Max("updated_at"), last_found=Max("date_first_found")
        )
        context["tags"] = CouncilTag.objects.filter(council=council).select_related(
            "tag"
        )

        if council.emergencydeclaration_set.count() > 0:
            context["declared_emergency"] = council.emergencydeclaration_set.all()[0]

        return context


class CouncilProjectsListView(FilterView):
    filterset_class = ProjectFilter
    context_object_name = "projects"
    template_name = "caps/projects_list.html"
    extra_context = {"page_title": "Browse council emissions reduction projects"}
    paginate_by = 20

    def get_queryset(self):
        return CouncilProject.objects.select_related("council").order_by(
            "council__name", "start_year"
        )


class CouncilListView(FilterView):
    filterset_class = CouncilFilter
    template_name = "caps/council_list.html"
    extra_context = {"page_title": "Find a council"}
    advanced_filters = [
        "promise_combined",
        "promise_area",
        "promise_council",
        "authority_type",
        "region",
        "geography",
        "population",
    ]

    def get_queryset(self):
        return (
            Council.current_councils()
            .annotate(
                num_plans=Subquery(
                    PlanDocument.objects.filter(
                        council_id=OuterRef("id"),
                        document_type=PlanDocument.ACTION_PLAN,
                    )
                    .values("council_id")
                    .annotate(num_plans=Count("id"))
                    .values("num_plans")
                ),
                has_promise=Count("promise"),
                has_promise_area=Count(
                    Case(
                        When(
                            promise__scope=PlanDocument.WHOLE_AREA,
                            then="promise__target_year",
                        ),
                        default=Value(None),
                        output_field=IntegerField(),
                    )
                ),
                has_promise_council=Count(
                    Case(
                        When(
                            promise__scope=PlanDocument.COUNCIL_ONLY,
                            then="promise__target_year",
                        ),
                        default=Value(None),
                        output_field=IntegerField(),
                    )
                ),
                earliest_promise=Min("promise__target_year"),
                earliest_promise_area=Min(
                    Case(
                        When(
                            promise__scope=PlanDocument.WHOLE_AREA,
                            then="promise__target_year",
                        ),
                        default=Value(None),
                        output_field=IntegerField(),
                    )
                ),
                earliest_promise_council=Min(
                    Case(
                        When(
                            promise__scope=PlanDocument.COUNCIL_ONLY,
                            then="promise__target_year",
                        ),
                        default=Value(None),
                        output_field=IntegerField(),
                    )
                ),
                declared_emergency=Min("emergencydeclaration__date_declared"),
                last_plan_update=Max("plandocument__updated_at"),
            )
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["filter"].form

        if hasattr(form, "cleaned_data"):
            active_filters = {}
            active_advanced_filters = {}
            context["field_descriptions"] = {}
            for field, value in form.cleaned_data.items():
                # create readable description of filters selected
                if field != "sort" and value:
                    field_label = CouncilFilter.base_filters[
                        field
                    ].label or field.replace("_", " ")
                    choices = CouncilFilter.base_filters[field].extra.get("choices", [])
                    if field == "region" and value in "1234":
                        choices = Council.COUNTRY_CHOICES
                        value = int(value)
                        field_label = "Country"
                    if field == "emissions":
                        choices = ComparisonLabel.choices("emissions")
                    context["field_descriptions"][field_label] = dict(choices).get(
                        value, value
                    )

                if field != "sort" and value is not None and value != "":
                    active_filters[field] = 1
                    if field in self.advanced_filters:
                        active_advanced_filters[field] = 1

            context["active_filters"] = active_filters
            context["active_advanced_filters"] = active_advanced_filters

        return context


class SearchResultsView(HaystackSearchView):
    template_name = "caps/search_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, "related_terms"):
            context["related_terms"] = self.related_terms
        inorganic = self.request.GET.get("inorganic")
        if context["form"]["council_name"].value() is not None:
            context["council_name"] = context["form"]["council_name"].value()

        context["inorganic"] = False
        if inorganic == "1":
            context["inorganic"] = True

        context["query"] = context.get("query", "")

        if context["query"]:
            context["page_title"] = "{} - Search results".format(context["query"])
        else:
            context["page_title"] = "Search plans"

        pc = is_valid_postcode(context["query"])
        if pc is not None:
            context["postcode"] = pc
        return context

    """
    Following adapted from https://github.com/django-haystack/saved_searches/
    """

    def save_search(self, context):
        # we occasionally get super long search strings which cause an error becuase the saved search
        # field only copes with searches up to 1000 characters so truncate those as realistically they
        # are not great searches.
        if len(context["query"]) > 1000:
            context["query"] = context["query"][:1000]
        if context["query"] and context["page_obj"].number == 1:
            # Save the search.
            saved_search = SavedSearch(
                search_key=self.search_field,
                user_query=context["query"],
                result_count=context["paginator"].count,
                inorganic=context["inorganic"],
            )
            if context.get("council_name", "") != "":
                saved_search.council_restriction = context["council_name"]
            saved_search.save()

    def form_valid(self, form):
        self.queryset, possible_related_terms = form.search()
        context = self.get_context_data(
            **{
                self.form_name: form,
                "query": form.cleaned_data.get(self.search_field),
                "object_list": self.queryset,
            }
        )

        # at this point, object_list has been adjusted by pagination

        if form.cleaned_data.get("match_method") != HighlightedSearchForm.MATCH_NORMAL:
            # improve the highlighting by removing the <mark> tags from the middle of words
            # for all searches that use exact text
            rehighlighted_items, related_words = condense_highlights(
                context["object_list"], possible_related_terms
            )
            context["object_list"] = rehighlighted_items
            context["related_words"] = related_words

        return self.render_to_response(context)

    def render_to_response(self, context):
        self.save_search(context)
        return super().render_to_response(context)


class BaseLocationResultsView(TemplateView):
    def render_to_response(self, context):
        councils = context.get("councils")
        if councils and len(councils) == 1:
            response = redirect(context["councils"][0])
        else:
            response = super().render_to_response(context)

        postcode = context.get("postcode", None)
        if councils and postcode:
            # set cookie for postcode where there is a valid postcode
            # e.g. it has found at least one council
            response.set_cookie(
                key="pc",
                value=postcode,
                expires=None,
                domain=self.request.get_host().split(":")[0],
                secure=False,
            )

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        postcode = self.request.GET.get("pc")
        lon = self.request.GET.get("lon")
        lat = self.request.GET.get("lat")
        mapit = MapIt()
        context["postcode"] = postcode
        context["all_councils"] = Council.current_councils()
        try:
            if lon and lat:
                gss_codes = mapit.wgs84_point_to_gss_codes(lon, lat)
            elif postcode:
                gss_codes = mapit.postcode_point_to_gss_codes(postcode)
            else:
                return context
            councils = Council.objects.filter(gss_code__in=gss_codes)
            combined_authorities = [
                council.combined_authority
                for council in councils
                if council.combined_authority
            ]
            councils = list(councils) + combined_authorities

            # Fetch successors for any replaced councils, even if mapit doesn't know about them yet
            for c in councils:
                if c.replaced_by:
                    councils.extend(list(c.get_successors()))
            # remove any councils that are former councils
            councils = [
                x
                for x in councils
                if x.id in Council.current_councils().values_list("id", flat=True)
            ]
            # remove duplicates based on x.id
            councils = list({x.id: x for x in councils}.values())
            context["councils"] = councils
        except (
            NotFoundException,
            BadRequestException,
            InternalServerErrorException,
            ForbiddenException,
        ) as error:
            context["error"] = error

        return context


class LocationResultsView(BaseLocationResultsView):
    template_name = "caps/location_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if context.get("postcode", "") != "":
            context["page_title"] = "{} – Find your council’s action plan".format(
                context["postcode"]
            )
        else:
            context["page_title"] = "Find your council’s action plan"

        return context


class TwinsView(BaseLocationResultsView):
    template_name = "caps/twins.html"

    def render_to_response(self, context):
        return super(BaseLocationResultsView, self).render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["all_councils"] = Council.current_councils()

        council = None

        if "slug" in self.kwargs:
            council = Council.objects.get(slug=self.kwargs["slug"])
        elif len(context.get("councils", [])) == 1:
            council = context["councils"][0]

        if council:
            context["council"] = council
            related_councils = council.get_related_councils()
            related_councils_intersection = (
                council.related_council_keyphrase_intersection()
            )
            for group in related_councils:
                for c in group["councils"]:
                    c.plan_overlap = related_councils_intersection[c]
                if group["type"].slug == "composite":
                    twin = group["councils"][0]
                    context["twin"] = twin

            # check not unbound
            assert "twin" in context, "Council has no twin"

            context["related_council_groups"] = related_councils

            context["page_title"] = "{}’s climate twin".format(council.name)
        else:
            context["page_title"] = "Find your council climate twin"

        return context


class TagDetailView(DetailView):
    model = Tag
    context_object_name = "tag"
    template_name = "caps/tag_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tag = context["tag"]
        context["page_title"] = "Feature: {}".format(tag.name)

        tagged = CouncilTag.objects.filter(tag=tag).values_list("council", flat=True)

        councils = Council.objects.filter(id__in=list(tagged)).annotate(
            num_plans=Count("plandocument"),
            has_promise=Count("promise"),
            earliest_promise=Min("promise__target_year"),
            declared_emergency=Min("emergencydeclaration__date_declared"),
            last_plan_update=Max("plandocument__updated_at"),
        )
        context["councils"] = councils

        return context


class TagListView(ListView):
    model = Tag
    context_object_name = "tags"
    template_name = "caps/tag_list.html"

    def get_queryset(self):
        return Tag.objects.annotate(num_councils=Count("counciltag"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context = add_context_for_plans_download_and_search(context)
        context["page_title"] = "Council climate action plans"
        return context


class AboutView(TemplateView):
    template_name = "caps/about.html"
    extra_context = {
        "page_title": "About",
        "feedback_form_url": settings.FEEDBACK_FORM,
    }


class AboutDataView(TemplateView):
    template_name = "caps/about_data.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comparison_types"] = ComparisonType.objects.all()

        context["csv_field_explanations"] = [
            [
                "last_update",
                "This is the date we last updated any information about the plan. It is not the date the plan was last updated.",
            ],
            ["url", "The URL where the plan was fetched."],
            ["plan_path", "This is the path to download the plan from our website."],
            [
                "scope",
                "Council only means the plan only deals with the council’s operations. Whole area means the plan covers non council activities within council boundaries as well.",
            ],
        ]

        context["projects_field_explanations"] = [
            ["council_name", "Human-readable name for the council"],
            ["authority_code", "Three letter council code as above"],
            ["start_year", "Reporting start year"],
            ["end_year", "Reporting end year"],
            ["data_type", "This is always “projects”"],
            ["emission_savings", "Emissions saved in tCO2e"],
            ["project_name", "Name of the project"],
            ["lifetime", "Length of the project in years"],
            ["cost", "Capital cost of the project"],
            ["funding_source", "Where the funding for the project came from"],
            ["emission_source", "Where the emissions savings come from"],
            ["annual_savings", "Annual cost savings"],
            ["measurement", "If the emissions savings are measured or estimated"],
            ["savings_start", "Year the savings start"],
            ["comments", "Optional comments about this project"],
        ]

        context["page_title"] = "Our data"

        return context


class MailchimpView(View):
    """
    View that accepts a post request of an email address
    and adds that to the mailchimp list.

    Returns a JSON object, as per https://jsonapi.org
    """

    def post(self, request):
        email = request.POST.get("email")
        client = MailchimpMarketing.Client()
        client.set_config(
            {
                "api_key": settings.MAILCHIMP_KEY,
                "server": settings.MAILCHIMP_SERVER_PREFIX,
            }
        )

        content = {"email_address": email, "status": "subscribed"}
        body = {"members": [content], "update_existing": True}

        http_status = 200
        response_data = {"data": content}

        try:
            client.lists.batch_list_members(settings.MAILCHIMP_LIST_ID, body)
        except ApiClientError as error:
            http_status = 500
            response_data = {
                "errors": [
                    {
                        "status": 500,
                        "title": "mailchimp_marketing ApiClientError",
                        "detail": error.text,
                    }
                ]
            }

        return JsonResponse(response_data, status=http_status)


class NetZeroLocalHeroView(TemplateView):
    template_name = "caps/net_zero_local_hero.html"
    extra_context = {
        "page_title": "Be a Net Zero Local Hero",
        "og_image_path": "/static/caps/img/og-image-nzlh.jpg",
    }


class StyleView(TemplateView):
    template_name = "caps/style.html"
    extra_context = {
        "page_title": "Styles",
        "colors": [
            "blue",
            "navy",
            "purple",
            "pink",
            "red",
            "orange",
            "yellow",
            "green",
            "cyan",
        ],
    }


class FeedbackEmail(View):
    def post(self, request):
        email = request.POST.get("feedback-email")
        data = request.POST.get("data-downloaded")

        send_mail(
            "CAPE data downloaded",
            "email: {}\ndata: {}".format(email, data),
            settings.FEEDBACK_EMAIL,
            [settings.FEEDBACK_EMAIL],
            fail_silently=True,
        )

        content = {"email_address": email, "status": "sent"}

        http_status = 200
        response_data = {"data": content}

        return JsonResponse(response_data, status=http_status)


class MarkdownView(TemplateView):
    """
    View that accepts a markdown slug and renders the markdown file
    with the given slug in the template.
    """

    template_name = "caps/markdown.html"

    def get_markdown_context(self, **kwargs) -> dict:
        """
        Override this method to add extra context to feed to the markdown.
        """
        return {}

    def get_context_data(self, **kwargs):
        """
        Given a markdown slug, fetch the file from caps/templates/caps/markdown/{slug}.md
        This is a jekyll style markdown file, with a yaml header and markdown body.
        The yaml header is parsed and used to populate the template context.
        """
        context = super().get_context_data(**kwargs)

        markdown_slug = kwargs.get("markdown_slug")
        # sanitise the slug to prevent directory traversal
        markdown_slug = re.sub(r"[^a-zA-Z0-9_-]", "", markdown_slug)
        template_path = Path("caps", "markdown/{}.md".format(markdown_slug))
        try:
            template = get_template(template_path)
        except TemplateDoesNotExist:
            raise Http404

        markdown_body = template.template.source.strip()

        # Extract the markdown H1 header to use as the page title, and remove it from the markdown_body
        lines = markdown_body.splitlines()
        h1_header = lines[0]
        assert h1_header.startswith(
            "# "
        ), "Markdown file should start with an H1 header '# title'"
        markdown_body = "\n".join(lines[1:])
        context["page_title"] = h1_header[2:]

        markdown_content = markdown.markdown(markdown_body, extensions=["toc"])

        markdown_context = Context(self.get_markdown_context(**kwargs))

        # we want to run the markdown_content through a basic django template so that any urls, etc are expanded
        markdown_content = Template(markdown_content).render(markdown_context)

        # there are ids assigned to each header by the TOC extention, extract these so we can put them in the sidebar
        soup = BeautifulSoup(markdown_content, "html.parser")
        headers = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        header_links = []
        last_item = {1: None, 2: None, 3: None, 4: None, 5: None, 6: None}

        for header in headers:
            header_item = {
                "level": int(header.name[1]),
                "text": header.text,
                "id": header.attrs["id"],
                "parent": None,
            }
            current_level = header_item["level"]
            last_item[current_level] = header_item["id"]
            if current_level > 1:
                header_item["parent"] = last_item[current_level - 1]
            header_links.append(header_item)

        # re-arrange the headers into a tree
        for header in header_links:
            header["children"] = [
                h for h in header_links if h["parent"] == header["id"]
            ]

        # remove anything below h3 and that will now be a child from top level
        header_links = [
            h for h in header_links if h["level"] <= 3 and h["parent"] is None
        ]

        context["body"] = mark_safe(str(soup))
        context["header_links"] = header_links
        return context


class NotFoundPageView(TemplateView):
    template_name = "caps/404.html"
    extra_context = {
        "page_title": "Page not found",
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_councils"] = Council.current_councils()
        return context

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
