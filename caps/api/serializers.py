from caps.models import Council, SavedSearch
from rest_framework import serializers


class CouncilSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.URLField(source='get_absolute_url')
    plan_count = serializers.IntegerField()
    country = serializers.CharField(source='get_country_display')
    authority_type = serializers.CharField(source='get_authority_type_display')

    class Meta:
        model = Council
        fields = ['name', 'url', 'website_url', 'gss_code', 'country', 'authority_type', 'plan_count']

class SearchTermSerializer(serializers.HyperlinkedModelSerializer):
    times_seen = serializers.IntegerField()

    class Meta:
        model = SavedSearch
        fields = ['user_query', 'result_count', 'times_seen']