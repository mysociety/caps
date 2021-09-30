from django.forms import CharField
from haystack.forms import SearchForm

class HighlightedSearchForm(SearchForm):
    council_name=CharField(required=False)

    def search(self):
        kwargs = {
            'hl.simple.pre': '<mark>',
            'hl.simple.post': '</mark>',
            'hl.fragsize': 400,
            'hl.snippets': 3
        }
        sqs = super(HighlightedSearchForm, self).search()

        if self.cleaned_data['council_name']:
            # narrow makes use of fq rather than q
            sqs = sqs.narrow('council_name:%s' % self.cleaned_data['council_name'])

        return sqs.highlight(**kwargs)

