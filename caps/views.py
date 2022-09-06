from random import shuffle, sample, randint

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.generic import View, DetailView, ListView, TemplateView
from django.db.models import Q, Count, Max, Min, Avg, Subquery, OuterRef
from django.shortcuts import redirect
from django.conf import settings
from django.core.mail import send_mail
import mailchimp_marketing as MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError

from os.path import join

from django_filters.views import FilterView
from haystack.generic_views import SearchView as HaystackSearchView

from caps.models import (
    Council,
    CouncilFilter,
    PlanDocument,
    DataPoint,
    SavedSearch,
    ComparisonType,
    Tag,
    CouncilTag,
    CouncilProject,
    ProjectFilter,
)
from caps.forms import HighlightedSearchForm
from caps.mapit import (
    MapIt,
    NotFoundException,
    BadRequestException,
    InternalServerErrorException,
    ForbiddenException,
)

import caps.charts as charts

from charting import ChartCollection

from caps.utils import file_size, is_valid_postcode

from scoring.models import (
    PlanScore,
    PlanSection,
    PlanSectionScore,
)


class HomePageView(TemplateView):

    template_name = "caps/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_councils"] = Council.objects.all()
        context["total_councils"] = Council.objects.all().count()
        context["total_plans"] = PlanDocument.objects.all().count()
        context["percent_councils_with_plan"] = Council.percent_with_plan()
        # can't shuffle querysets because they don't support assignment
        context["popular_searches"] = [
            s for s in SavedSearch.objects.most_popular()[:6]
        ]
        shuffle(context["popular_searches"])
        context["last_update"] = PlanDocument.objects.aggregate(Max("updated_at"))[
            "updated_at__max"
        ]

        plan_file = join(settings.MEDIA_ROOT, "data", "plans", "plans.zip")
        plan_size = file_size(plan_file)
        context["plan_zip_size"] = plan_size

        context["page_title"] = "Tracking the UK’s journey towards carbon zero"

        return context


class CouncilDetailView(DetailView):

    model = Council
    context_object_name = "council"
    template_name = "caps/council_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council: Council = context.get("council")

        context["emissions_data"] = False
        try:
            latest_year = council.datapoint_set.aggregate(Max("year"))["year__max"]
            context["latest_year"] = latest_year
            latest_year_per_capita_emissions = council.datapoint_set.get(
                year=latest_year, data_type__name="Per Person Emissions"
            ).value
            latest_year_per_km2_emissions = council.datapoint_set.get(
                year=latest_year, data_type__name="Emissions per km2"
            ).value
            latest_year_total_emissions = council.datapoint_set.get(
                year=latest_year, data_type__name="Total Emissions"
            ).value
            context[
                "latest_year_per_capita_emissions"
            ] = latest_year_per_capita_emissions
            context["latest_year_per_km2_emissions"] = latest_year_per_km2_emissions
            context["latest_year_total_emissions"] = latest_year_total_emissions
            context["emissions_data"] = True
        except DataPoint.DoesNotExist:
            pass

        if context["emissions_data"]:
            context[
                "current_emissions_breakdown"
            ] = council.current_emissions_breakdown(year=latest_year)
            multi_emission_chart = charts.multi_emissions_chart(council, latest_year)
            context["chart_collection"] = ChartCollection()
            context["chart_collection"].register(multi_emission_chart)

        # this covers no scoring data at all
        try:
            plan_score = PlanScore.objects.get(council=council, year=2021)

            group = council.get_scoring_group()

            average_total = PlanScore.objects.filter(
                total__gt=0,
                council__authority_type__in=group["types"],
                council__country__in=group["countries"],
                year=2021,
            ).aggregate(average_score=Avg("weighted_total"))

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
                    "example_section": top_scoring_sections[0]["description"],
                }

            context["scoring_hidden"] = getattr(settings, "SCORECARDS_PRIVATE", False)

        except PlanScore.DoesNotExist:
            context["scoring_hidden"] = True

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

        context["page_title"] = council.name
        context["feedback_form_url"] = settings.FEEDBACK_FORM

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
        "authority_type",
        "region",
        "geography",
        "population",
    ]

    def get_queryset(self):
        return Council.objects.annotate(
            num_plans=Subquery(
                PlanDocument.objects.filter(
                    council_id=OuterRef("id"), document_type=PlanDocument.ACTION_PLAN
                )
                .values("council_id")
                .annotate(num_plans=Count("id"))
                .values("num_plans")
            ),
            has_promise=Count("promise"),
            earliest_promise=Min("promise__target_year"),
            declared_emergency=Min("emergencydeclaration__date_declared"),
            last_plan_update=Max("plandocument__updated_at"),
        ).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["filter"].form

        if hasattr(form, "cleaned_data"):
            active_filters = {}
            active_advanced_filters = {}
            for field, value in form.cleaned_data.items():
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
        inorganic = self.request.GET.get("inorganic")
        if context["form"]["council_name"].value() is not None:
            context["council_name"] = context["form"]["council_name"].value()

        context["inorganic"] = False
        if inorganic == "1":
            context["inorganic"] = True

        if context["query"]:
            context["page_title"] = "{} – Search results".format(context["query"])
        else:
            context["page_title"] = "Search plans"

        query = context["query"]
        pc = is_valid_postcode(query)
        if pc is not None:
            context["postcode"] = pc

        return context

    """
    Following adapted from https://github.com/django-haystack/saved_searches/
    """

    def save_search(self, context):
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

    def render_to_response(self, context):
        self.save_search(context)
        return super().render_to_response(context)


class BaseLocationResultsView(TemplateView):
    def render_to_response(self, context):
        councils = context.get("councils")
        if councils and len(councils) == 1:
            return redirect(context["councils"][0])

        return super(BaseLocationResultsView, self).render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        postcode = self.request.GET.get("pc")
        lon = self.request.GET.get("lon")
        lat = self.request.GET.get("lat")
        mapit = MapIt()
        context["postcode"] = postcode
        context["all_councils"] = Council.objects.all()
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
            context["councils"] = list(councils) + combined_authorities
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
    extra_context = {"page_title": "Browse councils by feature"}

    def get_queryset(self):
        return Tag.objects.annotate(num_councils=Count("counciltag"))


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
