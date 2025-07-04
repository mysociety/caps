from django.conf import settings
from django.contrib.auth.mixins import AccessMixin
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
    def setup_filter_context(self, context, filter, scoring_group):
        if getattr(filter.form, "cleaned_data", None) is not None:
            params = filter.form.cleaned_data
            descs = []
            if (
                params.get("population", None) is not None
                and params["population"] != ""
            ):
                descs.append(params.get("population", None))
            if params.get("control", None) is not None and params["control"] != "":
                descs.append(params.get("control", None))
            if (
                params.get("ruc_cluster", None) is not None
                and params["ruc_cluster"] != ""
            ):
                descs.append(
                    PlanScore.ruc_cluster_description(params.get("ruc_cluster", None))
                )
            if params.get("imdq", None) is not None and params["imdq"] != "":
                descs.append("deprivation quintile {}".format(params.get("imdq", None)))
            if params.get("country", None) is not None and params["country"] != "":
                descs.append(Council.country_description(params["country"]))
            if (
                params.get("authority_type", None) is not None
                and params["authority_type"] != ""
            ):
                descs.append(Council.authority_type_desc(params["authority_type"]))
            if params.get("region", None) is not None and params["region"] != "":
                descs.append(params["region"])
            if params.get("county", None) is not None and params["county"] != "":
                descs.append(params["county"])

            context["filter_params"] = params
            context["filter_descs"] = descs

        context["urbanisation_filter"] = PlanScore.RUC_TYPES
        context["population_filter"] = PlanScore.POPULATION_FILTER_CHOICES.get(
            scoring_group["slug"]
        )
        context["county_filter"] = Council.get_county_choices()
        context["authority_type_filter"] = (
            Council.get_authority_type_choices_for_scoring_group("single")
        )

        return context


# For council search autocompletes (eg: in navbar)
class SearchAutocompleteMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.year.year == 2023:
            context["all_councils"] = Council.objects.exclude(
                start_date__gte="2023-01-01"
            )
        else:
            context["all_councils"] = Council.objects.exclude(
                end_date__lte="2024-01-01"
            )
        return context
