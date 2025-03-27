from django.conf import settings
from django.http import Http404, HttpResponseServerError

from scoring.models import PlanYear


class AddYearMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.host.name == "scoring" and request.path not in ["/down/"]:
            if request.resolver_match.app_name == "scoring2022":
                request.year = 2021
            elif request.host.name == "scoring":
                year = None
                if view_kwargs.get("year") is not None:
                    try:
                        year = int(view_kwargs["year"])
                    except ValueError:
                        year = None

                if year is not None:
                    try:
                        plan_year = PlanYear.objects.get(year=year)
                    except PlanYear.DoesNotExist:
                        raise Http404("No such year")
                else:
                    try:
                        plan_year = PlanYear.objects.get(is_current=True)
                    except PlanYear.DoesNotExist:
                        raise HttpResponseServerError("No current Plan Year found")

                request.year = plan_year
