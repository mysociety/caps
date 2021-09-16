# -*- coding: future_fstrings -*-
from datetime import datetime
from django.utils.timezone import make_aware
from django.db.models import Count, Max
from django.forms import ValidationError

from rest_framework import viewsets, routers
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination

from caps.models import Council, SavedSearch
from caps.api.serializers import CouncilSerializer, SearchTermSerializer

class InvalidParamException(APIException):
    status_code = 400
    default_status = "bad_request"

    def __init__(self, *args):
        self.default_detail = self.default_detail % args
        super().__init__()

class InvalidCountException(InvalidParamException):
    default_detail = "%s must be an integer greater than or equal to %d"


class InvalidDateException(InvalidParamException):
    default_detail = "%s must be a valid date with the format YYYY-MM-DD"


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
    * plans_last_update - the date of the most recent update to a plan
    """
    queryset = Council.objects.annotate(plan_count=Count('plandocument'),plans_last_update=Max('plandocument__updated_at')).all()
    serializer_class = CouncilSerializer
    # don't paginate this as there's a fixed number of results that doesn't really
    # change so is very amenable to caching
    pagination_class = None

class SearchTermViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List of search terms that returned results, ordered by most popular terms

    * user_query - term searched for
    * result_count - number of results returned from search
    * times_seen - number of times term was searched for

    Can optionally filter against the following query parameters in the URL:

    * start_date - only include queries made on or after this date in YYYY-MM-DD format
    * end_date - only include queries made on or before this date in YYYY-MM-DD format
    * min_count - only include queries that have been made at least this number of times (min 5)
    * min_results - only include queries that have returned at least this many results

    NB: all filter terms are inclusive so e.g. a start_date of 2021-08-12 will include
    searches made on that date.
    """

    queryset = SavedSearch.objects.filter(result_count__gt=0).values('user_query', 'result_count').distinct().annotate(times_seen=Count('user_query')).filter(times_seen__gt=5).order_by('-times_seen')
    serializer_class = SearchTermSerializer

    def get_queryset(self):
        queryset = SavedSearch.objects.filter(result_count__gt=0).values('user_query', 'result_count').distinct().annotate(times_seen=Count('user_query')).filter(times_seen__gte=5).order_by('-times_seen')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        min_count = self.request.query_params.get('min_count')
        min_results = self.request.query_params.get('min_results')

        if start_date is not None:
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
                queryset = queryset.filter(created__date__gte=make_aware(start_date))
            except ValueError:
                raise InvalidDateException('start_date')

        if end_date is not None:
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
                queryset = queryset.filter(created__date__lte=make_aware(end_date))
            except ValueError:
                raise InvalidDateException('end_date')

        if min_count is not None:
            try:
                min_count = int(min_count)
                if min_count < 5:
                    raise InvalidCountException('min_count', 5)
                queryset = queryset.filter(times_seen__gte=min_count)
            except ValueError as error:
                raise InvalidCountException('min_count', 5)

        if min_results is not None:
            try:
                min_results = int(min_results)
                if min_results < 1:
                    raise InvalidCountException('min_results', 1)
                queryset = queryset.filter(result_count__gte=min_results)
            except ValueError as error:
                raise InvalidCountException('min_results', 1)

        return queryset

