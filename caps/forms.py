from haystack.forms import SearchForm

class HighlightedSearchForm(SearchForm):

    def search(self):
        kwargs = {
            'hl.simple.pre': '<span class="highlighted">',
            'hl.simple.post': '</span>',
            'hl.fragsize': 400,
            'hl.snippets': 3
        }
        return super(HighlightedSearchForm, self).search().highlight(**kwargs)
