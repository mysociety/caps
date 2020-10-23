# -*- coding: future_fstrings -*-
from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import DetailView, ListView, TemplateView
from django.db.models import Q, Count

from caps.models import Council, PlanDocument

class HomePageView(TemplateView):

    template_name = "home.html"

class CouncilDetailView(DetailView):

    model = Council
    template_name = 'council_detail.html'

class CouncilListView(ListView):

    model = Council
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
