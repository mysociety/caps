# -*- coding: future_fstrings -*-
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.generic import View, DetailView, ListView, TemplateView
from django.db.models import Q, Count, Max
from django.shortcuts import redirect
from django.conf import settings
import mailchimp_marketing as MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError

from django_filters.views import FilterView
from haystack.generic_views import SearchView as HaystackSearchView

from caps.models import Council, CouncilFilter, PlanDocument, DataPoint
from caps.forms import HighlightedSearchForm
from caps.mapit import MapIt, NotFoundException, BadRequestException, InternalServerErrorException, ForbiddenException

class HomePageView(TemplateView):

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_councils'] = Council.objects.all()
        context['total_councils'] = Council.objects.all().count()
        context['percent_councils_with_plan'] = Council.percent_with_plan()
        context['search_suggestions'] = [
            '"electric taxis"',
            '"green homes grant"',
            '"ground source heat pumps"',
            '"circular economy"',
        ]
        return context

class CouncilDetailView(DetailView):

    model = Council
    context_object_name = 'council'
    template_name = 'council_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council = context.get('council')
        try:
            latest_year = council.datapoint_set.aggregate(Max('year'))['year__max']
            context['latest_year'] = latest_year
            latest_year_per_capita_emissions = council.datapoint_set.get(year=latest_year, data_type__name='Per Capita Emissions').value
            latest_year_per_km2_emissions = council.datapoint_set.get(year=latest_year, data_type__name='Emissions per km2').value
            latest_year_total_emissions = council.datapoint_set.get(year=latest_year, data_type__name='Total Emissions').value
            context['latest_year_per_capita_emissions'] = latest_year_per_capita_emissions
            context['latest_year_per_km2_emissions'] = latest_year_per_km2_emissions
            context['latest_year_total_emissions'] = latest_year_total_emissions
        except DataPoint.DoesNotExist:
            context['no_emissions_data'] = True
        context['related_councils'] = council.related_councils.all().annotate(num_plans=Count('plandocument'))

        # TODO: Replace these with real figures for this council!
        context['council_scores'] = [
            {
                "section_label": "Governance, Development and Funding",
                "section_colour": "green",
                "section_weight_percent": 20,
                "score_percent": 65
            },
            {
                "section_label": "Mitigation and Adaptation",
                "section_colour": "cyan",
                "section_weight_percent": 15,
                "score_percent": 40
            },
            {
                "section_label": "Commitment and Integration",
                "section_colour": "blue",
                "section_weight_percent": 15,
                "score_percent": 80
            },
            {
                "section_label": "Community Engagement and Communications",
                "section_colour": "navy",
                "section_weight_percent": 20,
                "score_percent": 45
            },
            {
                "section_label": "Measuring and Setting Emissions Targets",
                "section_colour": "purple",
                "section_weight_percent": 10,
                "score_percent": 66
            },
            {
                "section_label": "Co-benefits",
                "section_colour": "pink",
                "section_weight_percent": 5,
                "score_percent": 40
            },
            {
                "section_label": "Diversity and Social Inclusion",
                "section_colour": "red",
                "section_weight_percent": 5,
                "score_percent": 25
            },
            {
                "section_label": "Education, Skills and Training",
                "section_colour": "orange",
                "section_weight_percent": 5,
                "score_percent": 50
            },
            {
                "section_label": "Ecological Emergency",
                "section_colour": "yellow",
                "section_weight_percent": 5,
                "score_percent": 65
            },
        ]

        context['council_score_total'] = 0

        # Calculate some totals to avoid doing math in the template.
        for i, s in enumerate(context['council_scores']):
            context['council_scores'][i]['score_percent_of_total'] = s['score_percent'] * s['section_weight_percent'] / 100
            context['council_score_total'] = context['council_score_total'] + context['council_scores'][i]['score_percent_of_total']

        # TODO: Replace these with real figures for this council!
        context['average_scores'] = [
            {
                "section_label": "Governance, Development and Funding",
                "section_colour": "green",
                "section_weight_percent": 20,
                "score_percent": 52
            },
            {
                "section_label": "Mitigation and Adaptation",
                "section_colour": "cyan",
                "section_weight_percent": 15,
                "score_percent": 35
            },
            {
                "section_label": "Commitment and Integration",
                "section_colour": "blue",
                "section_weight_percent": 15,
                "score_percent": 62
            },
            {
                "section_label": "Community Engagement and Communications",
                "section_colour": "navy",
                "section_weight_percent": 20,
                "score_percent": 25
            },
            {
                "section_label": "Measuring and Setting Emissions Targets",
                "section_colour": "purple",
                "section_weight_percent": 10,
                "score_percent": 48
            },
            {
                "section_label": "Co-benefits",
                "section_colour": "pink",
                "section_weight_percent": 5,
                "score_percent": 25
            },
            {
                "section_label": "Diversity and Social Inclusion",
                "section_colour": "red",
                "section_weight_percent": 5,
                "score_percent": 20
            },
            {
                "section_label": "Education, Skills and Training",
                "section_colour": "orange",
                "section_weight_percent": 5,
                "score_percent": 45
            },
            {
                "section_label": "Ecological Emergency",
                "section_colour": "yellow",
                "section_weight_percent": 5,
                "score_percent": 52
            },
        ]

        context['average_score_total'] = 0

        # Calculate some totals to avoid doing math in the template.
        for i, s in enumerate(context['average_scores']):
            context['average_scores'][i]['score_percent_of_total'] = s['score_percent'] * s['section_weight_percent'] / 100
            context['average_score_total'] = context['average_score_total'] + context['average_scores'][i]['score_percent_of_total']

        return context

class CouncilListView(FilterView):

    filterset_class = CouncilFilter
    template_name = 'council_list.html'

    def get_queryset(self):
        return Council.objects.annotate(num_plans=Count('plandocument'))

class SearchResultsView(HaystackSearchView):

    template_name = 'search_results.html'

class LocationResultsView(TemplateView):

    template_name = "location_results.html"

    def render_to_response(self, context):
        councils = context.get('councils')
        if councils and len(councils) == 1:
            return redirect(context['councils'] [0])

        return super(LocationResultsView, self).render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        postcode = self.request.GET.get('pc')
        lon = self.request.GET.get('lon')
        lat = self.request.GET.get('lat')
        mapit = MapIt()
        context['postcode'] = postcode
        context['all_councils'] = Council.objects.all()
        try:
            if lon and lat:
                gss_codes = mapit.wgs84_point_to_gss_codes(lon, lat)
            elif postcode:
                gss_codes = mapit.postcode_point_to_gss_codes(postcode)
            else:
                return context
            councils = Council.objects.filter(gss_code__in=gss_codes)
            combined_authorities = [ council.combined_authority for council in councils if council.combined_authority ]
            context['councils'] = list(councils) + combined_authorities
        except (NotFoundException, BadRequestException, InternalServerErrorException, ForbiddenException) as error:
            context['error'] = error
        return context

class AboutView(TemplateView):

    template_name = "about.html"


class MailchimpView(View):
    """
    View that accepts a post request of an email address
    and adds that to the mailchimp list.

    Returns a JSON object, as per https://jsonapi.org
    """

    def post(self, request):

        email = request.POST.get("email")
        client = MailchimpMarketing.Client()
        client.set_config({
            "api_key": settings.MAILCHIMP_KEY,
            "server": settings.MAILCHIMP_SERVER_PREFIX
        })

        content = {"email_address":email,
                   "status":"subscribed"}
        body = {"members":[content],
                "update_existing": True}

        http_status = 200
        response_data = {"data": content}

        try:
            client.lists.batch_list_members(settings.MAILCHIMP_LIST_ID, body)
        except ApiClientError as error:
            http_status = 500
            response_data = {
                "errors": [{
                    "status": 500,
                    "title": "mailchimp_marketing ApiClientError",
                    "detail": error.text,
                }]
            }

        return JsonResponse(response_data, status=http_status)


class StyleView(TemplateView):

    template_name = "style.html"
