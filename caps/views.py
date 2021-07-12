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
