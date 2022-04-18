import operator
from datetime import datetime
from functools import reduce
from django.utils.timezone import make_aware
from django.db.models import Q, Count, Max, Min, Subquery, OuterRef, Exists

from django.forms import ValidationError

from rest_framework import viewsets, routers, generics
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination

from caps.models import Council, SavedSearch, PlanDocument, Promise
from caps.api.serializers import (
    CouncilSerializer,
    SearchTermSerializer,
    PromiseSerializer,
)


class BiggerPageSize(PageNumberPagination):
    page_size = 250
    page_size_query_param = "page_size"
    max_page_size = 1000


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

    The raw data for action plans is also available <a href="/media/data/plans.csv">as a csv</a>.
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
    * plans_last_update - the date of the most recent update to a plan (null if no plans)
    * carbon_reduction_commitment - True if the council has public commitments to reduce emissions
    * carbon_neutral_date - the earliest date for a carbon neutral target (null if no date)
    * carbon_neutral_commitments - link to list of commitments made by council
    * declared_emergency - date, if any, council declared a climate emergency

    ###Filters

    You can filter the list of councils using the following query parameters:

    * country - one of England, Northern Ireland, Scotland, Wales
    * authority_type - one of City of London, Combined Authority, County Council, London Borough,
    Metropolitan District, Non-Metropolitan District, Unitary Authority

    Multiple values can be combined with commas.
    """

    serializer_class = CouncilSerializer
    # don't paginate this as there's a fixed number of results that doesn't really
    # change so is very amenable to caching
    pagination_class = None
    lookup_field = "authority_code"

    def get_queryset(self):
        # need to use subqueries otherwise the joins mean we get bad counts
        plans = (
            PlanDocument.objects.filter(council=OuterRef("pk"))
            .order_by()
            .values("council")
            .annotate(plan_count=Count("council"))
            .values("plan_count")
        )
        promised = Promise.objects.filter(council=OuterRef("pk"), has_promise=True)
        queryset = Council.objects.annotate(
            plan_count=Subquery(plans),
            carbon_reduction_commitment=Exists(promised),
            carbon_neutral_date=Min("promise__target_year"),
            declared_emergency=Min("emergencydeclaration__date_declared"),
            plans_last_update=Max("plandocument__updated_at"),
        ).order_by("name")

        country = self.request.query_params.get("country")
        authority_type = self.request.query_params.get("authority_type")

        if country is not None:
            codes = []
            for c in country.split(","):
                code = Council.country_code(c)
                if code is not None:
                    codes.append(Q(country=code))
            if codes:
                code_filter = reduce(operator.or_, codes)
                queryset = queryset.filter(code_filter)

        if authority_type is not None:
            types = []
            for t in authority_type.split(","):
                code = Council.authority_type_code(t)
                if code is not None:
                    types.append(Q(authority_type=code))
            if types:
                type_filter = reduce(operator.or_, types)
                queryset = queryset.filter(type_filter)

        return queryset


class CommitmentsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Information about the climate commitments made by councils.

    Includes both carbon reduction commitments and net zero ones. If the commitment
    is for net zero then has_promise will be `true` otherwise `false'

    * council - link to the council making the promise
    * has_promise - if the promise includes a commitment to net zero
    * target_year - the year the commitment is targeting
    * scope - if the commitment is limited to council operations or the whole council area
    * text - the text of the commitment
    * source - URL of the document the commitment comes from
    * source_name - name of the document the commitment comes from
    """

    queryset = (
        Promise.objects.order_by("council__name", "target_year")
        .select_related("council")
        .order_by("target_year")
        .all()
    )
    serializer_class = PromiseSerializer
    pagination_class = BiggerPageSize


class CouncilCommitmentsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Information about a council's climate commitments.

    Includes both carbon reduction commitments and net zero ones. If the commitment
    is for net zero then has_promise will be `true` otherwise `false'

    * council - link to the council making the promise
    * has_promise - if the promise includes a commitment to net zero
    * target_year - the year the commitment is targeting
    * scope - if the commitment is limited to council operations or the whole council area
    * text - the text of the commitment
    * source - URL of the document the commitment comes from
    * source_name - name of the document the commitment comes from
    """

    queryset = Promise.objects.order_by("target_year").all()
    serializer_class = PromiseSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Promise.objects.filter(
                council__authority_code=self.kwargs["authority_code"]
            )
            .select_related("council")
            .order_by("target_year")
            .all()
        )


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

    queryset = (
        SavedSearch.objects.filter(result_count__gt=0)
        .values("user_query", "result_count", "council_restriction")
        .distinct()
        .annotate(times_seen=Count("user_query"))
        .filter(times_seen__gt=5)
        .order_by("-times_seen")
    )
    serializer_class = SearchTermSerializer

    def get_queryset(self):
        queryset = (
            SavedSearch.objects.filter(result_count__gt=0)
            .values("user_query", "result_count", "council_restriction")
            .distinct()
            .annotate(times_seen=Count("user_query"))
            .filter(times_seen__gte=5)
            .order_by("-times_seen")
        )
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        min_count = self.request.query_params.get("min_count")
        min_results = self.request.query_params.get("min_results")

        if start_date is not None:
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
                queryset = queryset.filter(created__date__gte=make_aware(start_date))
            except ValueError:
                raise InvalidDateException("start_date")

        if end_date is not None:
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
                queryset = queryset.filter(created__date__lte=make_aware(end_date))
            except ValueError:
                raise InvalidDateException("end_date")

        if min_count is not None:
            try:
                min_count = int(min_count)
                if min_count < 5:
                    raise InvalidCountException("min_count", 5)
                queryset = queryset.filter(times_seen__gte=min_count)
            except ValueError as error:
                raise InvalidCountException("min_count", 5)

        if min_results is not None:
            try:
                min_results = int(min_results)
                if min_results < 1:
                    raise InvalidCountException("min_results", 1)
                queryset = queryset.filter(result_count__gte=min_results)
            except ValueError as error:
                raise InvalidCountException("min_results", 1)

        return queryset
