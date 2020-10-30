# -*- coding: future_fstrings -*-
from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import DetailView, ListView, TemplateView
from django.db.models import Q, Count
from django.shortcuts import redirect

from caps.models import Council, CouncilFilter, PlanDocument
from django_filters.views import FilterView

from caps.mapit import MapIt, NotFoundException, BadRequestException

class HomePageView(TemplateView):

    template_name = "home.html"

class CouncilDetailView(DetailView):

    model = Council
    context_object_name = 'council'
    template_name = 'council_detail.html'

class CouncilListView(FilterView):

    filterset_class = CouncilFilter
    template_name = 'council_list.html'

    def get_queryset(self):
        return Council.objects.annotate(num_plans=Count('plandocument'))

class SearchResultsView(ListView):

    model = Council

    template_name = 'search_results.html'

    def get_queryset(self):
        query = self.request.GET.get('q')
        object_list = Council.objects.filter(Q(plandocument__text__icontains=query))
        return object_list

class PostcodeResultsView(TemplateView):

    template_name = "postcode_results.html"

    def render_to_response(self, context):
        councils = context.get('councils')
        if councils and len(councils) == 1:
            return redirect(context['councils'] [0])

        return super(PostcodeResultsView, self).render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        postcode = self.request.GET.get('pc')
        mapit = MapIt()
        context['postcode'] = postcode
        try:
            gss_codes = mapit.postcode_point_to_gss_codes(postcode)
            councils = Council.objects.filter(gss_code__in=gss_codes)
            combined_authorities = [ council.combined_authority for council in councils if council.combined_authority ]
            context['councils'] = list(councils) + combined_authorities
        except (NotFoundException, BadRequestException) as error:
            context['error'] = error
        return context
