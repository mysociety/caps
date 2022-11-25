from cape.models import Council, SavedSearch, Promise
from rest_framework import serializers, reverse


class CouncilSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.URLField(source="get_absolute_url")
    plan_count = serializers.IntegerField()
    country = serializers.CharField(source="get_country_display")
    authority_type = serializers.CharField(source="get_authority_type_display")
    plans_last_update = serializers.DateField()
    carbon_reduction_commitment = serializers.BooleanField()
    carbon_neutral_date = serializers.IntegerField()
    declared_emergency = serializers.DateField()
    carbon_reduction_statements = serializers.HyperlinkedIdentityField(
        view_name="council-commitments", lookup_field="authority_code"
    )

    class Meta:
        model = Council
        fields = [
            "name",
            "url",
            "website_url",
            "gss_code",
            "country",
            "authority_type",
            "authority_code",
            "plan_count",
            "plans_last_update",
            "carbon_reduction_commitment",
            "carbon_neutral_date",
            "carbon_reduction_statements",
            "declared_emergency",
        ]

    # we don't get a count where there aren't any plans so force this
    # to 0 rather than null
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if ret["plan_count"] is None:
            ret["plan_count"] = 0
        return ret


class PromiseSerializer(serializers.HyperlinkedModelSerializer):
    council = serializers.SerializerMethodField()
    scope = serializers.CharField(source="get_scope_display")

    class Meta:
        model = Promise
        fields = [
            "council",
            "has_promise",
            "target_year",
            "scope",
            "text",
            "source",
            "source_name",
        ]

    def get_council(self, obj):
        code = obj.council.authority_code
        # do this is a string otherwise you get an array as the result
        result = "{}".format(
            reverse.reverse(
                "council-detail", args=[code], request=self.context["request"]
            ),
        )
        return result


class SearchTermSerializer(serializers.HyperlinkedModelSerializer):
    times_seen = serializers.IntegerField()

    class Meta:
        model = SavedSearch
        fields = ["user_query", "result_count", "times_seen", "council_restriction"]
