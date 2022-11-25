import re

from string import capwords

from django import template
from django.template.defaultfilters import stringfilter

from cape.models import PlanDocument

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


@register.filter
@stringfilter
def document_type(value):
    value = int(value)
    for choice in PlanDocument.DOCUMENT_TYPE_CHOICES:
        if choice[0] == value:
            return choice[1].lower()
    return "document"
