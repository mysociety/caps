from io import StringIO

from django.test import TestCase

import unittest
from django.core.management import call_command
from caps.models import Council, PlanDocument

class ImportPlansTestCase(TestCase):

    processed_output = 'adding new plan for Borsetshire\nadding new council: East Borsetshire\nadding new plan for East Borsetshire\nadding new council: West Borsetshire\n2 councils will be added\n2 plans will be added\n';
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
            out = self.call_command(confirm_changes=1,verbosity=2)
            self.assertEquals(out, self.processed_output)

            council = Council.objects.get(authority_code='BORS');
            self.assertEqual(council.name, "Borsetshire")

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.PRE_PLAN);
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY);
            self.assertEqual(plan.file_type, "pdf");

            council = Council.objects.get(authority_code='EBRS');
            self.assertEqual(council.name, "East Borsetshire")

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.PRE_PLAN);
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY);
            self.assertEqual(plan.file_type, "pdf");

            council = Council.objects.get(authority_code='WBRS');
            self.assertEqual(council.name, "West Borsetshire")

            plan = PlanDocument.objects.filter(council=council).exists()
            self.assertFalse(plan)


    def test_without_confirm_changes(self):
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(verbosity=2)
            self.assertEquals(out, '%scall with --confirm_changes to update database\n' % self.processed_output);

            council = Council.objects.get(authority_code='BORS');
            plan = PlanDocument.objects.filter(council=council).exists()
            self.assertFalse(plan)

    def test_basic_changes_message(self):
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(out, '2 councils will be added\n2 plans will be added\n');

            out = self.call_command()
            self.assertEquals(out, '');

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update.csv"):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(out, '1 plan will be added\n1 plan will be updated\n');

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update_url.csv"):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(out, '1 plan will be added\n1 plan will be deleted\n');

    def test_detailed_changes_message(self):
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1,verbosity=2)
            self.assertEquals(out, self.processed_output);

            out = self.call_command(verbosity=2)
            self.assertEquals(out, '');

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update.csv"):
            out = self.call_command(confirm_changes=1,verbosity=2)
            self.assertEquals(out, 'updating plan for Borsetshire\nadding new plan for West Borsetshire\n1 plan will be added\n1 plan will be updated\n');

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update_url.csv"):
            out = self.call_command(confirm_changes=1,verbosity=2)
            self.assertEquals(out, 'adding new plan for Borsetshire\ndeleting plan for Borsetshire\n1 plan will be added\n1 plan will be deleted\n');


    def test_update_properties(self):
        council = Council.objects.get(authority_code='BORS');
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1)

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.PRE_PLAN);
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY);
            self.assertEqual(plan.file_type, "pdf");

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update.csv"):
            out = self.call_command(confirm_changes=1)

            plans = PlanDocument.objects.filter(council=council)
            self.assertEqual(len(plans), 1)

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.ACTION_PLAN);
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY);
            self.assertEqual(plan.file_type, "pdf");

            new_council = Council.objects.get(authority_code='WBRS');
            plan = PlanDocument.objects.get(council=new_council)
            self.assertEqual(plan.url, "https://west-borsetshire.gov.uk/climate_plan.pdf")

    def test_change_url(self):
        council = Council.objects.get(authority_code='BORS');
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1)

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update_url.csv"):
            out = self.call_command(confirm_changes=1)

            plans = PlanDocument.objects.filter(council=council)
            self.assertEqual(len(plans), 1)

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan_updated.pdf")

    def test_delete_plan(self):
        bors = Council.objects.get(authority_code='BORS');
        with self.settings(PROCESSED_CSV="caps/tests/test_processed_pre_delete.csv"):

            out = self.call_command(confirm_changes=1)

            plan = PlanDocument.objects.get(council=bors)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_no_plans.csv"):
            west_bors = Council.objects.get(authority_code='WBRS');

            out = self.call_command(verbosity=2)
            self.assertEquals(out, 'Borsetshire will have all plans removed\nWest Borsetshire will have all plans removed\n2 councils will have all plans removed\ncall with --confirm_changes to update database\n')
            plans = PlanDocument.objects.filter(council=bors)
            self.assertEqual(len(plans), 1)

            out = self.call_command(confirm_changes=1)
            self.assertEquals(out, '2 councils will have all plans removed\n')

            plans = PlanDocument.objects.filter(council=bors)
            self.assertEqual(len(plans), 0)
            plans = PlanDocument.objects.filter(council=west_bors)
            self.assertEqual(len(plans), 0)
