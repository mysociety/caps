from caps.models import Council
from django.conf import settings
from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect

from scoring.models import PlanScore


class CheckForDownPageMixin(AccessMixin):
    login_url = "/login/"
    redirect_field_name = "redirect_to"

    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "SCORECARDS_PRIVATE", False):
            return super().dispatch(request, *args, **kwargs)

        if not request.user.is_authenticated:
            return redirect("scoring:downpage")

        return super().dispatch(request, *args, **kwargs)


class AdvancedFilterMixin:
    def setup_filter_context(self, context, filter, authority_type):
        if getattr(filter.form, "cleaned_data", None) is not None:
            params = filter.form.cleaned_data
            descs = []
            if params["population"] and params["population"] != "":
                descs.append(params["population"])
            if params["control"] and params["control"] != "":
                descs.append(params["control"])
            if params["ruc_cluster"] and params["ruc_cluster"] != "":
                descs.append(PlanScore.ruc_cluster_description(params["ruc_cluster"]))
            if params["imdq"] and params["imdq"] != "":
                descs.append("deprivation quintile {}".format(params["imdq"]))
            if params["country"] and params["country"] != "":
                descs.append(Council.country_description(params["country"]))
            if params.get("region", None) is not None and params["region"] != "":
                descs.append(params["region"])
            if params.get("county", None) is not None and params["county"] != "":
                descs.append(params["county"])

            context["filter_params"] = params
            context["filter_descs"] = descs

        context["urbanisation_filter"] = PlanScore.RUC_TYPES
        context["population_filter"] = PlanScore.POPULATION_FILTER_CHOICES.get(
            authority_type["slug"]
        )
        context["county_filter"] = Council.get_county_choices()

        return context
