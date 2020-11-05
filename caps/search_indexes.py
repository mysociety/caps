from haystack import indexes
from caps.models import PlanDocument

class PlanDocumentIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True,
                             use_template=True,
                             template_name='plandocument_text_index.txt')

    def get_model(self):
        return PlanDocument

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.all()
