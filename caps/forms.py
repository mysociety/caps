from django.forms import CharField, BooleanField
from haystack.forms import SearchForm
from haystack.query import SearchQuerySet
from haystack.inputs import Exact

class HighlightedSearchForm(SearchForm):
    council_name=CharField(required=False)
    exact=BooleanField(required=False)

    def search(self):
        kwargs = {
            'hl.simple.pre': '<mark>',
            'hl.simple.post': '</mark>',
            'hl.fragsize': 400,
            'hl.snippets': 3
        }
        sqs = self.no_query_found()

        # use the text_exact field in solr which doesn't stem
        if self.cleaned_data['q'] and self.cleaned_data['exact'] is True:
            query = self.cleaned_data['q']
            kwargs['hl.fl'] = 'text_exact'
            sqs = SearchQuerySet().filter(text_exact=Exact(query))
            if self.load_all:
                sqs = sqs.load_all()
        else:
            sqs = super(HighlightedSearchForm, self).search()

        if self.cleaned_data['council_name']:
            # narrow makes use of fq rather than q
            sqs = sqs.narrow('council_name:%s' % self.cleaned_data['council_name'])

        return sqs.highlight(**kwargs)

