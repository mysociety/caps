# -*- coding: future_fstrings -*-
from random import shuffle

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.generic import View, DetailView, ListView, TemplateView
from django.db.models import Q, Count, Max
from django.shortcuts import redirect
from django.conf import settings
import mailchimp_marketing as MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError

from os.path import join

from django_filters.views import FilterView
from haystack.generic_views import SearchView as HaystackSearchView

from caps.models import Council, CouncilFilter, PlanDocument, DataPoint, SavedSearch
from caps.forms import HighlightedSearchForm
from caps.mapit import MapIt, NotFoundException, BadRequestException, InternalServerErrorException, ForbiddenException
from caps.utils import file_size

class HomePageView(TemplateView):

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_councils'] = Council.objects.all()
        context['total_councils'] = Council.objects.all().count()
        context['total_plans'] = PlanDocument.objects.all().count()
        context['percent_councils_with_plan'] = Council.percent_with_plan()
        # can't shuffle querysets because they don't support assignment
        context['popular_searches'] = [ s for s in SavedSearch.objects.most_popular()[:6] ]
        shuffle(context['popular_searches'])
        context['last_update'] = PlanDocument.objects.aggregate(Max('updated_at'))['updated_at__max']

        plan_file = join(settings.MEDIA_ROOT, 'data', 'plans', 'plans.zip')
        plan_size = file_size(plan_file)
        context['plan_zip_size'] = plan_size

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
        context['last_updated'] = council.plandocument_set.aggregate(last_update=Max('updated_at'),last_found=Max('date_first_found'))
        return context

class CouncilListView(FilterView):

    filterset_class = CouncilFilter
    template_name = 'council_list.html'

    def get_queryset(self):
        return Council.objects.annotate(num_plans=Count('plandocument')).order_by('name')

class SearchResultsView(HaystackSearchView):

    template_name = 'search_results.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        inorganic = self.request.GET.get('inorganic')
        context['inorganic'] = False
        if inorganic == '1':
            context['inorganic'] = True

        return context

    """
    Following adapted from https://github.com/django-haystack/saved_searches/
    """
    def save_search(self, context):
        if context['query'] and context['page_obj'].number == 1:
            # Save the search.
            saved_search = SavedSearch(
                search_key=self.search_field,
                user_query=context['query'],
                result_count=context['paginator'].count,
                inorganic=context['inorganic']
            )
            saved_search.save()

    def render_to_response(self, context):
        self.save_search(context)
        return super().render_to_response(context)

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
