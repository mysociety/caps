from django.contrib.auth.mixins import AccessMixin
from django.conf import settings
from django.shortcuts import redirect

from caps.models import Council
from scoring.models import PlanScore


class PrivateScorecardsAccessMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if (
            getattr(settings, "SCORECARDS_PRIVATE", False)
            and not request.user.is_authenticated
        ):
            return self.handle_no_permission()

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
            if params["region"] and params["region"] != "":
                descs.append(params["region"])
            if params["county"] and params["county"] != "":
                descs.append(params["county"])

            context["filter_params"] = params
            context["filter_descs"] = descs

        context["urbanisation_filter"] = PlanScore.RUC_TYPES
        context["population_filter"] = PlanScore.POPULATION_FILTER_CHOICES.get(
            authority_type["slug"]
        )
        context["county_filter"] = Council.get_county_choices()

        return context
