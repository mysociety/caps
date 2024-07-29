from rest_framework import reverse, serializers

from caps.models import Council, PlanDocument, Promise, SavedSearch


class CouncilSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.URLField(source="get_absolute_url")
    plan_count = serializers.IntegerField()
    document_count = serializers.IntegerField()
    country = serializers.CharField(source="get_country_display")
    authority_type = serializers.CharField(source="get_authority_type_display")
    plans_last_update = serializers.DateField()
    carbon_reduction_commitment = serializers.BooleanField()
    carbon_neutral_date = serializers.IntegerField()
    declared_emergency = serializers.DateField()
    carbon_reduction_statements = serializers.HyperlinkedIdentityField(
        view_name="council-commitments", lookup_field="authority_code"
    )
    climate_documents = serializers.HyperlinkedIdentityField(
        view_name="council-documents", lookup_field="authority_code"
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
            "document_count",
            "climate_documents",
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
        if ret["document_count"] is None:
            ret["document_count"] = 0
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


class PlanDocumentSerializer(serializers.HyperlinkedModelSerializer):
    council = serializers.SerializerMethodField()
    document_type = serializers.SerializerMethodField()
    cached_url = serializers.CharField(source="file")

    class Meta:
        model = PlanDocument
        fields = [
            "council",
            "title",
            "document_type",
            "file_type",
            "url",
            "cached_url",
            "updated_at",
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

    def get_document_type(self, obj):
        type_code = obj.get_document_type_display()
        if type_code is None:
            type_code = "unknown"

        return type_code


class SearchTermSerializer(serializers.HyperlinkedModelSerializer):
    times_seen = serializers.IntegerField()

    class Meta:
        model = SavedSearch
        fields = ["user_query", "result_count", "times_seen", "council_restriction"]
