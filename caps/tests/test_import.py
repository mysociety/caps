from io import StringIO

from django.test import TestCase

from django.core.management import call_command
from caps.models import Council, PlanDocument

class ImportPlansTestCase(TestCase):

    def setUp(self):
        plan_council = Council.objects.get_or_create(name='Borsetshire',
                                              slug='borsetshire',
                                              authority_code='BORS',
                                              authority_type='UA',
                                              gss_code='E00000001',
                                              country=Council.ENGLAND,
                                              whatdotheyknow_id=80)

    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "import_plans",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_import(self):
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):

            out = self.call_command()

            council = Council.objects.get(authority_code='BORS');
            self.assertEqual(council.name, "Borsetshire")

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.PRE_PLAN);
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY);
            self.assertEqual(plan.file_type, "pdf");
