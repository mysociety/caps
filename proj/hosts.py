from django.conf import settings
from django_hosts import patterns, host

host_patterns = patterns('',
    host(r'data.climateemergency.uk', settings.ROOT_URLCONF, name='cape'),
    host(r'(league)', 'league.urls', name='league'),
)
