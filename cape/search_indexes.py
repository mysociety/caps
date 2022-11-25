from haystack import indexes
from cape.models import PlanDocument
from django.utils.html import strip_tags


class PlanDocumentIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(
        document=True, use_template=True, template_name="plandocument_text_index.txt"
    )
    council_name = indexes.CharField()

    def get_model(self):
        return PlanDocument

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.all()

    def prepare_council_name(self, document):
        return document.council.name

    def prepare_text(self, document):
        file = document.file.open()
        extracted_data = self.get_backend().extract_file_contents(file)

        # data is converted to html as part of the extraction
        return strip_tags(extracted_data["contents"])
