import django_filters

from caps.models import Council
from scoring.models import PlanQuestionScore, PlanScore


class BaseScoreFilter(django_filters.FilterSet):
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

    control = django_filters.CharFilter(field_name="political_control")

    county = django_filters.ChoiceFilter(
        field_name="council__county",
        choices=Council.get_county_choices(),
    )

    region = django_filters.ChoiceFilter(
        field_name="council__region", choices=Council.REGION_CHOICES
    )

    class Meta:
        model = PlanScore
        fields = []


class NationPlanScoreFilter(BaseScoreFilter):
    pass


class PlanScoreFilter(BaseScoreFilter):
    authority_type = django_filters.ChoiceFilter(
        field_name="council__authority_type",
        choices=Council.get_authority_type_choices_for_scoring_group("single"),
    )

    country = django_filters.ChoiceFilter(
        field_name="council__country",
        choices=Council.COUNTRY_CHOICES,
        empty_label="All",
    )


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
