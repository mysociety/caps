"""
Forms for the CAPS app
"""


from django.forms import CharField, ChoiceField, ModelChoiceField, RadioSelect, Select
from haystack.forms import SearchForm
from haystack.inputs import Exact
from haystack.query import SearchQuerySet

from caps.models import ComparisonType, Council, Distance, PlanDocument
from caps.search_funcs import (
    condense_highlights,
    get_semantic_query,
    highlighter_config,
    fuller_highlighter_config,
)
from django.conf import settings


class HighlightedSearchForm(SearchForm):
    """
    Search form for Haystack/Solr searches of the documents
    """

    council_name = CharField(required=False)

    MATCH_NORMAL = "normal"
    MATCH_EXACT = "exact"
    MATCH_RELATED = "related"
    MATCH_RELATED_LOOSE = "related_loose"

    DEFAULT_SEARCH = MATCH_RELATED

    MATCH_CHOICES = (
        (MATCH_RELATED_LOOSE, "Include as many terms as possible"),
        (MATCH_RELATED, "Include closely related terms (default)"),
        (MATCH_NORMAL, "Search for any of the provided words"),
        (MATCH_EXACT, "Search for the provided phrase exactly"),
    )

    DOCUMENT_TYPE_CHOICES = PlanDocument.DOCUMENT_TYPE_CHOICES
    DOCUMENT_TYPE_CHOICES.insert(0, ("-1", "All document types"))

    match_method = ChoiceField(
        widget=RadioSelect, choices=MATCH_CHOICES, required=False
    )

    document_type = ChoiceField(
        widget=RadioSelect, choices=DOCUMENT_TYPE_CHOICES, required=False
    )

    similar_council = ModelChoiceField(
        queryset=Council.objects.all(),
        to_field_name="slug",
        required=False,
        empty_label=None,
    )

    similar_type = ModelChoiceField(
        queryset=ComparisonType.objects.all(),
        to_field_name="slug",
        required=False,
        empty_label=None,
        widget=Select(attrs={"class": "form-control"}),
    )
    # add hidden document_id field
    document_id = CharField(
        required=False, widget=Select(attrs={"class": "form-control"})
    )

    def search(self):
        highlighter_kwargs = highlighter_config

        possible_related_terms = []

        match_method = self.cleaned_data["match_method"] or self.DEFAULT_SEARCH

        document_type = self.cleaned_data["document_type"] or "-1"
        if document_type != "-1":
            id_limit = PlanDocument.objects.filter(
                document_type=int(document_type)
            ).values_list("id", flat=True)
        else:
            id_limit = None

        if not self.cleaned_data["q"]:
            # if no query
            sqs = self.no_query_found()
        else:
            if match_method == HighlightedSearchForm.MATCH_EXACT:
                # for 'exact match' use the text_exact field in solr which doesn't stem
                query = self.cleaned_data["q"]
                sqs = SearchQuerySet().filter(text=Exact(query))
                if self.load_all:
                    sqs = sqs.load_all()

            elif match_method in [
                HighlightedSearchForm.MATCH_RELATED,
                HighlightedSearchForm.MATCH_RELATED_LOOSE,
            ]:
                # for 'include related', import additional search terms to exactly match against
                highlighter_kwargs = fuller_highlighter_config
                threshold = settings.RELATED_SEARCH_THRESHOLD
                if match_method == HighlightedSearchForm.MATCH_RELATED_LOOSE:
                    threshold = settings.RELATED_SEARCH_THRESHOLD_LOOSE
                sqs, possible_related_terms = get_semantic_query(
                    self.cleaned_data["q"], threshold, limit_to_ids=id_limit
                )
                if sqs is None:
                    sqs = super(HighlightedSearchForm, self).search()
                    if id_limit:
                        sqs = sqs.filter(document_type__in=id_limit)
            else:
                sqs = super(HighlightedSearchForm, self).search()
                if id_limit:
                    sqs = sqs.filter(document_type__in=id_limit)

        if self.cleaned_data["similar_type"]:
            # limiting to councils that are similar
            similar_council = self.cleaned_data["similar_council"]
            comparison_type = self.cleaned_data["similar_type"]
            cut_off = 15
            names = Distance.objects.filter(
                council_a=similar_council,
                type=comparison_type,
                position__lte=cut_off,
            ).values_list("council_b__name", flat=True)

            query_names = [f'council_name:"{name}"' for name in names]
            sqs = sqs.narrow(" OR ".join(query_names))

        if self.cleaned_data["council_name"]:
            # limiting to a specific council
            sqs = sqs.filter(council_name=self.cleaned_data["council_name"])

        # get the highlights so we can do some post-processing on them
        result = sqs.highlight(**highlighter_kwargs)

        if self.cleaned_data["document_id"]:
            # adjust the returned object to only include matches for the specific document
            result = [x for x in result if x.pk == self.cleaned_data["document_id"]]

        return result, possible_related_terms
