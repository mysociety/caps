import re

from string import capwords

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def domain_human(value):
    return re.sub(r"^(https?:[/][/])?(www[.])?([^/]+).*", r"\3", value)


@register.filter
@stringfilter
def url_human(value):
    return re.sub(r"^(https?:[/][/])?(www[.])?(.*)", r"\3", value)


@register.filter
@stringfilter
def document_title(value):
    """
    The standard title filter regards apostrophes as a word boundary which
    means you end up with things like "Aberdeen'S", so use capwords which
    is a much better match for our use case.
    """
    return capwords(value)
