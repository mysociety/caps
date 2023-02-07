from django.conf import settings
from django_hosts import host, patterns

host_patterns = patterns(
    "",
    host(r"cape.mysociety.org", settings.ROOT_URLCONF, name="cape"),
    host(r"((?:www.)?councilclimatescorecards)", "scoring.urls", name="scoring"),
)
