import django_filters

from caps.models import Council
from scoring.models import PlanScore


class PlanScoreFilter(django_filters.FilterSet):
    country = django_filters.ChoiceFilter(
        choices=Council.COUNTRY_CHOICES, empty_label="All"
    )

    ruc_cluster = django_filters.ChoiceFilter(
        field_name="planscore__ruc_cluster", choices=PlanScore.RUC_TYPES
    )

    population = django_filters.ChoiceFilter(
        field_name="planscore__population",
        choices=PlanScore.POPULATION_ALL_FILTER_CHOICES,
    )

    imdq = django_filters.NumberFilter(
        field_name="planscore__deprivation_quintile",
    )

    control = django_filters.CharFilter(field_name="planscore__political_control")

    class Meta:
        model = Council
        fields = []
