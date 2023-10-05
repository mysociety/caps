import django_filters

from caps.models import Council
from scoring.models import PlanScore, PlanQuestionScore


class PlanScoreFilter(django_filters.FilterSet):
    country = django_filters.ChoiceFilter(
        field_name="council__country",
        choices=Council.COUNTRY_CHOICES,
        empty_label="All",
    )

    ruc_cluster = django_filters.ChoiceFilter(
        field_name="ruc_cluster", choices=PlanScore.RUC_TYPES
    )

    population = django_filters.ChoiceFilter(
        field_name="population",
        choices=PlanScore.POPULATION_ALL_FILTER_CHOICES,
    )

    imdq = django_filters.NumberFilter(
        field_name="deprivation_quintile",
    )

    control = django_filters.CharFilter(field_name="planscore__political_control")

    region = django_filters.ChoiceFilter(
        field_name="council__region", choices=Council.REGION_CHOICES
    )

    county = django_filters.ChoiceFilter(
        field_name="council__county",
        choices=Council.get_county_choices(),
    )

    class Meta:
        model = PlanScore
        fields = []


class QuestionScoreFilter(django_filters.FilterSet):
    country = django_filters.ChoiceFilter(
        field_name="plan_score__council__country",
        choices=Council.COUNTRY_CHOICES,
        empty_label="All",
    )

    ruc_cluster = django_filters.ChoiceFilter(
        field_name="plan_score__ruc_cluster", choices=PlanScore.RUC_TYPES
    )

    population = django_filters.ChoiceFilter(
        field_name="plans_core__population",
        choices=PlanScore.POPULATION_ALL_FILTER_CHOICES,
    )

    imdq = django_filters.NumberFilter(
        field_name="plan_score__deprivation_quintile",
    )

    control = django_filters.CharFilter(field_name="plan_score__political_control")

    class Meta:
        model = PlanQuestionScore
        fields = []
