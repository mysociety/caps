import re

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
@stringfilter
def url_human(value):
    return re.sub(r'^(https?:[/][/])?(www[.])?([^/]+).*', r'\3', value)
