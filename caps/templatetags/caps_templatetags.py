import re
import markdown
import random
from string import capwords

from django import template
from django.template.defaultfilters import stringfilter
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.utils.safestring import mark_safe

from caps.models import PlanDocument

register = template.Library()


@register.filter
@stringfilter
def prevent_widow(s):
    # Replace final space in string with &nbsp;
    return mark_safe("&nbsp;".join(s.rsplit(" ", 1)))


@register.filter
def randomize_and_limit(value: list, limit: int = 10) -> list:
    """
    Shuffle and return the top of a list
    """
    random.shuffle(value)
    return value[:limit]


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


@register.filter
def percentage(value: float):
    """
    Convert value between 0 and 1 to a nice human readable percentage
    """
    return f"{value * 100:.0f}%"


@register.simple_tag(takes_context=True)
def council_card(context: dict, slug: str, title="", color: str = "red"):
    """
    Simplifies the process of rendering a council card.

    """
    if not title:
        title = slug

    ctx = {
        "color": color,
        "title": title,
        "slug": slug,
    }

    with context.push(ctx):
        return render_to_string(
            f"caps/council_cards/{slug}.html",
            context.flatten(),
        )


@register.tag(name="markdown")
def markdown_tag(parser, token):
    """
    Between {% markdown %} and {% endmarkdown %} tags,
    render the text as markdown.

    Django tags used within the markdown will be rendered first.
    """
    nodelist = parser.parse(("endmarkdown",))
    parser.delete_first_token()
    return MarkdownNode(nodelist)


class MarkdownNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        # render items below in the stack into markdown
        markdown_text = self.nodelist.render(context)

        # if the text is indented, we want to remove the indentation so that the smallest indent becomes 0, but all others are relative to that
        # this is so that we can have indented code blocks in markdown
        # we do this by finding the smallest indent, and then removing that from all lines

        smallest_indent = None
        for line in markdown_text.splitlines():
            if line.strip() == "":
                continue
            indent = len(line) - len(line.lstrip())
            if smallest_indent is None or indent < smallest_indent:
                smallest_indent = indent

        # remove the smallest indent from all lines
        if smallest_indent is not None:
            markdown_text = "\n".join(
                [line[smallest_indent:] for line in markdown_text.splitlines()]
            )

        text = markdown.markdown(markdown_text, extensions=["toc"])
        return text


@register.tag(name="infobox")
def infobox_tag(parser, token):
    """
    Between infobox and endinfobox tags,
    render the contents into the caps/includes/infobox.html
    """

    bits = token.split_contents()
    kwargs = {}

    # Parse the arguments
    for bit in bits[1:]:
        try:
            name, value = bit.split("=")
            kwargs[name] = value
        except ValueError as exc:
            raise template.TemplateSyntaxError(
                f"Badly formatted arguments: {token.contents}"
            ) from exc

    nodelist = parser.parse(("endinfobox",))
    parser.delete_first_token()
    return InfoboxNode(nodelist, **kwargs)


class InfoboxNode(template.Node):
    def __init__(self, nodelist, **kwargs):
        self.nodelist = nodelist
        self.kwargs = kwargs

    def render(self, context):
        infobox = self.nodelist.render(context)
        return render_to_string(
            "caps/includes/info-box.html",
            context={"infobox": infobox, **self.kwargs},
        )
