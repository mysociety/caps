# -*- coding: future_fstrings -*-
from django.db.models import Count

from rest_framework import viewsets, routers

from caps.models import Council, SavedSearch
from caps.api.serializers import CouncilSerializer, SearchTermSerializer

class APIView(routers.APIRootView):
    """
    API for data about councils and action plans.
    """
    pass

class CouncilViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Basic information about all the councils in the database.

    * url - path to the page on this site for the council.
    * website_url - URL for the council’s website
    * gss_code - standard council identifier.
    * country - which of the UK home nations the council is located in.
    * authority_type - what type of body (Unitary, District etc) the council is.
    * plan_count - number of plans we have details for.
    """
    queryset = Council.objects.annotate(plan_count=Count('plandocument')).all()
    serializer_class = CouncilSerializer

class SearchTermViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List of search terms that returned restults

    * user_query - term searched for
    * result_count - number of results returned from search
    * times_seen - number of times term was searched for
    """

    queryset = SavedSearch.objects.filter(result_count__gt=0).values('user_query', 'result_count').distinct().annotate(times_seen=Count('user_query'))
    serializer_class = SearchTermSerializer

