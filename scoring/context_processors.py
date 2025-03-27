from django.conf import settings

from scoring.models import PlanYear


def site_title(request):
    context = {}

    # Scorecards requests are given a "year" attribute by AddYearMiddleware.
    if hasattr(request, "year"):
        year_is_int = isinstance(request.year, int)
        year_is_planyear = isinstance(request.year, PlanYear)
        if year_is_int and request.year == 2021:
            context["site_title"] = "Council Climate Plan Scorecards"
        elif year_is_planyear and not request.year.is_current:
            context["site_title"] = f"{request.year.year} Council Climate Scorecards"
        else:
            context["site_title"] = "Council Climate Scorecards"

    return context
