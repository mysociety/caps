from haystack.forms import SearchForm

class HighlightedSearchForm(SearchForm):

    def search(self):
        kwargs = {
            'hl.simple.pre': '<mark>',
            'hl.simple.post': '</mark>',
            'hl.fragsize': 400,
            'hl.snippets': 3
        }
        return super(HighlightedSearchForm, self).search().highlight(**kwargs)
