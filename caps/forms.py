from django.forms import BooleanField, CharField, ModelChoiceField, Select
from haystack.forms import SearchForm
from haystack.inputs import Exact
from haystack.query import SearchQuerySet

from caps.models import ComparisonType, Council, Distance


class HighlightedSearchForm(SearchForm):
    council_name = CharField(required=False)
    exact = BooleanField(required=False)
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

    def search(self):
        kwargs = {
            "hl.simple.pre": "<mark>",
            "hl.simple.post": "</mark>",
            "hl.fragsize": 400,
            "hl.snippets": 3,
        }
        sqs = self.no_query_found()

        # use the text_exact field in solr which doesn't stem
        if self.cleaned_data["q"] and self.cleaned_data["exact"] is True:
            query = self.cleaned_data["q"]
            kwargs["hl.fl"] = "text_exact"
            sqs = SearchQuerySet().filter(text_exact=Exact(query))
            if self.load_all:
                sqs = sqs.load_all()
        else:
            sqs = super(HighlightedSearchForm, self).search()

        if self.cleaned_data["similar_type"]:
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
            # narrow makes use of fq rather than q
            sqs = sqs.narrow("council_name:%s" % self.cleaned_data["council_name"])

        return sqs.highlight(**kwargs)
