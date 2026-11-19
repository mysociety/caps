from io import StringIO

from django.test import TestCase

import unittest
from django.core.management import call_command
from caps.models import Council, PlanDocument, Promise, Tag, CouncilTag

from caps.management.commands.import_promises import import_promises
from caps.management.commands.import_council_tags import (
    create_tags,
    create_council_tags,
)


class ImportTestCase(TestCase):
    def setUp(self):
        plan_council = Council.objects.get_or_create(
            name="Borsetshire",
            slug="borsetshire",
            authority_code="BORS",
            authority_type="UA",
            gss_code="E00000001",
            country=Council.ENGLAND,
            whatdotheyknow_id=80,
            population=100000,
        )

    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            self.command,
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()


class ImportPlansTestCase(ImportTestCase):

    command = "import_plans"
    processed_output = "adding new plan for Borsetshire\nadding new council: East Borsetshire\nadding new plan for East Borsetshire\nadding new council: West Borsetshire\n2 councils will be added\n2 plans will be added\n"
    processed_output = "adding new plan for Borsetshire\nadding new council: East Borsetshire\nadding new plan for East Borsetshire\nadding new council: West Borsetshire\n2 councils will be added\n2 plans will be added\n"
    summary_output = "Councils with a plan went from 0 to 2\nNumber of documents went from 0 to 2\nNumber of plans went from 0 to 2\n"

    def test_import(self):
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1, verbosity=2)
            self.assertEquals(
                out, "%s%s" % (self.processed_output, self.summary_output)
            )

            council = Council.objects.get(authority_code="BORS")
            self.assertEqual(council.name, "Borsetshire")

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.ACTION_PLAN)
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY)
            self.assertEqual(plan.file_type, "pdf")
            self.assertEqual(plan.date_last_found.isoformat(), "2021-02-11")

            council = Council.objects.get(authority_code="EBRS")
            self.assertEqual(council.name, "East Borsetshire")

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.ACTION_PLAN)
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY)
            self.assertEqual(plan.file_type, "pdf")
            self.assertEqual(plan.date_last_found.isoformat(), "2021-11-02")

            council = Council.objects.get(authority_code="WBRS")
            self.assertEqual(council.name, "West Borsetshire")

            plan = PlanDocument.objects.filter(council=council).exists()
            self.assertFalse(plan)

    def test_without_confirm_changes(self):
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(verbosity=2)
            self.assertEquals(
                out,
                "%scall with --confirm_changes to update database\n"
                % self.processed_output,
            )

            council = Council.objects.get(authority_code="BORS")
            plan = PlanDocument.objects.filter(council=council).exists()
            self.assertFalse(plan)

    def test_basic_changes_message(self):
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(
                out,
                "2 councils will be added\n2 plans will be added\n%s"
                % self.summary_output,
            )

            out = self.call_command()
            self.assertEquals(out, "")

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update.csv"):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(
                out,
                "1 plan will be added\n1 plan will be updated\nCouncils with a plan went from 2 to 3\nNumber of documents went from 2 to 3\nNumber of plans went from 2 to 3\n",
            )

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update_url.csv"):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(
                out,
                "1 plan will be added\n1 plan will be deleted\nCouncils with a plan is unchanged at 3\nNumber of documents is unchanged at 3\nNumber of plans is unchanged at 3\n",
            )

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_add_plan.csv"):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(
                out,
                "1 plan will be added\nCouncils with a plan is unchanged at 3\nNumber of documents went from 3 to 4\nNumber of plans went from 3 to 4\n",
            )

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_add_non_plan.csv"):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(
                out,
                "1 plan will be added\nCouncils with a plan is unchanged at 3\nNumber of documents went from 4 to 5\nNumber of plans is unchanged at 4\n",
            )

        with self.settings(
            PROCESSED_CSV="caps/tests/test_processed_remove_council.csv"
        ):
            out = self.call_command(confirm_changes=1)
            self.assertEquals(
                out,
                "1 plan will be added\nCouncils with a plan went from 3 to 2\nNumber of documents went from 5 to 4\nNumber of plans is unchanged at 4\n",
            )

    def test_detailed_changes_message(self):
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1, verbosity=2)
            self.assertEquals(
                out, "%s%s" % (self.processed_output, self.summary_output)
            )

            out = self.call_command(verbosity=2)
            self.assertEquals(out, "")

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update.csv"):
            out = self.call_command(confirm_changes=1, verbosity=2)
            self.assertEquals(
                out,
                "updating plan for Borsetshire (date_last_found changed)\nadding new plan for West Borsetshire\n1 plan will be added\n1 plan will be updated\nCouncils with a plan went from 2 to 3\nNumber of documents went from 2 to 3\nNumber of plans went from 2 to 3\n",
            )

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update_url.csv"):
            out = self.call_command(confirm_changes=1, verbosity=2)
            self.assertEquals(
                out,
                "adding new plan for Borsetshire\ndeleting plan for Borsetshire -  (1)\n1 plan will be added\n1 plan will be deleted\nCouncils with a plan is unchanged at 3\nNumber of documents is unchanged at 3\nNumber of plans is unchanged at 3\n",
            )

    def test_update_properties(self):
        council = Council.objects.get(authority_code="BORS")
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1)

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.ACTION_PLAN)
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY)
            self.assertEqual(plan.file_type, "pdf")
            self.assertEqual(plan.date_first_found.isoformat(), "2021-02-11")
            self.assertEqual(plan.date_last_found.isoformat(), "2021-02-11")

            # use the model manager update as that bypasses auto_now
            PlanDocument.objects.filter(council=council).update(updated_at="2021-08-01")
            plan = PlanDocument.objects.get(council=council)
            self.assertEquals("2021-08-01", plan.updated_at.isoformat())

            ebrs = Council.objects.get(authority_code="EBRS")
            PlanDocument.objects.filter(council=ebrs).update(updated_at="2021-08-01")
            plan = PlanDocument.objects.get(council=ebrs)
            self.assertEquals("2021-08-01", plan.updated_at.isoformat())

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update.csv"):
            out = self.call_command(confirm_changes=1)

            plans = PlanDocument.objects.filter(council=council)
            self.assertEqual(len(plans), 1)

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")
            self.assertEqual(plan.document_type, PlanDocument.ACTION_PLAN)
            self.assertEqual(plan.scope, PlanDocument.COUNCIL_ONLY)
            self.assertEqual(plan.file_type, "pdf")
            self.assertEqual(plan.date_first_found.isoformat(), "2021-02-11")
            self.assertEqual(plan.date_last_found.isoformat(), "2021-02-17")
            self.assertTrue("2021-08-01" != plan.updated_at.isoformat())

            new_council = Council.objects.get(authority_code="WBRS")
            plan = PlanDocument.objects.get(council=new_council)
            self.assertEqual(
                plan.url, "https://west-borsetshire.gov.uk/climate_plan.pdf"
            )

            unchanged_council = Council.objects.get(authority_code="EBRS")
            plan = PlanDocument.objects.get(council=unchanged_council)
            self.assertEquals("2021-08-01", plan.updated_at.isoformat())

    def test_change_url(self):
        council = Council.objects.get(authority_code="BORS")
        with self.settings(PROCESSED_CSV="caps/tests/test_processed.csv"):
            out = self.call_command(confirm_changes=1)

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")

        with self.settings(PROCESSED_CSV="caps/tests/test_processed_update_url.csv"):
            out = self.call_command(confirm_changes=1)

            plans = PlanDocument.objects.filter(council=council)
            self.assertEqual(plans.count(), 1)

            plan = PlanDocument.objects.get(council=council)
            self.assertEqual(
                plan.url, "https://borsetshire.gov.uk/climate_plan_updated.pdf"
            )

    def test_delete_plan(self):
        bors = Council.objects.get(authority_code="BORS")
        # Import the data from test_processed_pre_delete
        with self.settings(PROCESSED_CSV="caps/tests/test_processed_pre_delete.csv"):

            out = self.call_command(confirm_changes=1)

            plan = PlanDocument.objects.get(council=bors)
            self.assertEqual(plan.url, "https://borsetshire.gov.uk/climate_plan.pdf")

        # Give it the new data sheet - with several rows removed,
        # and another row that is present but has no plan
        with self.settings(PROCESSED_CSV="caps/tests/test_processed_no_plans.csv"):
            west_bors = Council.objects.get(authority_code="WBRS")

            out = self.call_command(verbosity=2)
            self.assertEquals(
                out,
                "Borsetshire will be completely removed\nNorth Borsetshire will be completely removed\nWest Borsetshire will have all plans removed\n1 council will have all plans removed\ncall with --confirm_changes to update database\n",
            )
            plans = PlanDocument.objects.filter(council=bors)
            self.assertEqual(len(plans), 1)

            out = self.call_command(confirm_changes=1)
            self.assertEquals(
                out,
                "1 council will have all plans removed\nCouncils with a plan went from 3 to 1\nNumber of documents went from 3 to 1\nNumber of plans went from 3 to 1\n",
            )

            # BORS has been removed from the sheet - but it should continue to exist even if it's plan doesn't.
            bors_exists = Council.objects.filter(authority_code="BORS").exists()
            self.assertTrue(bors_exists)

            plans = PlanDocument.objects.filter(council=west_bors)
            self.assertEqual(len(plans), 0)


class ImportPromisesTestCase(ImportTestCase):

    command = "import_promises"

    def setUp(self):
        super().setUp()
        Council.objects.get_or_create(
            name="East Borsetshire",
            slug="east-borsetshire",
            authority_code="EBRS",
            authority_type="UA",
            gss_code="E00000003",
            country=Council.ENGLAND,
            whatdotheyknow_id=81,
        )
        Council.objects.get_or_create(
            name="West Borsetshire",
            slug="west-borsetshire",
            authority_code="WBRS",
            authority_type="UA",
            gss_code="E00000002",
            country=Council.ENGLAND,
            whatdotheyknow_id=82,
        )

    def import_promises(self):
        with self.settings(PROMISES_CSV="caps/tests/test_promises.csv"):
            return import_promises()

    def test_import_review_outcomes(self):
        self.import_promises()
        self.assertEqual(
            dict(
                Promise.objects.exclude(review_outcome_2026=None).values_list(
                    "text", "review_outcome_2026"
                )
            ),
            {
                "carbon neutral by 2035!": Promise.REVIEW_2026_STRONGER,
                "the whole of Borsetshire will be net zero by 2050": (
                    Promise.REVIEW_2026_WITHDRAWN
                ),
            },
        )

    def test_import_promises(self):
        self.import_promises()
        council = Council.objects.get(authority_code="BORS")

        promise = Promise.objects.get(council=council, text="carbon neutral by 2035!")
        self.assertTrue(promise.has_promise)
        self.assertEqual(promise.type, Promise.PROMISE)
        self.assertEqual(promise.status, Promise.LATEST)
        self.assertEqual(promise.domain, Promise.COUNCIL_OPERATIONS)
        self.assertEqual(promise.scope, Promise.SCOPES_1_2)
        self.assertEqual(promise.target_year, 2035)
        self.assertEqual(promise.target_text, "")
        self.assertEqual(promise.source, "http://borsetshire.gov.uk/promise.html")
        self.assertEqual(promise.source_name, "Borsetshire website")
        self.assertEqual(promise.source_date, "2024-12")
        self.assertEqual(promise.last_checked, "2026-11")
        self.assertEqual(promise.notes, "brought forward from 2040")

        promise = Promise.objects.get(council=council, scope=Promise.SCOPE_3)
        self.assertIsNone(promise.target_year)
        self.assertEqual(promise.target_text, "as soon as possible")

    def test_import_past_promises_and_withdrawals(self):
        self.import_promises()
        council = Council.objects.get(authority_code="BORS")

        self.assertEqual(
            sorted(
                Promise.objects.filter(council=council).values_list(
                    "type", "status", "domain", "target_year"
                )
            ),
            sorted(
                [
                    (Promise.PROMISE, Promise.LATEST, Promise.COUNCIL_OPERATIONS, 2035),
                    (
                        Promise.PROMISE,
                        Promise.SUPERSEDED,
                        Promise.COUNCIL_OPERATIONS,
                        2040,
                    ),
                    (Promise.PROMISE, Promise.WITHDRAWN, Promise.WHOLE_AREA, 2050),
                    (Promise.WITHDRAWAL, Promise.LATEST, Promise.WHOLE_AREA, None),
                    (Promise.PROMISE, Promise.LATEST, Promise.WHOLE_AREA, None),
                ]
            ),
        )

    def test_import_no_promise_found(self):
        self.import_promises()
        council = Council.objects.get(authority_code="WBRS")

        promise = Promise.objects.get(council=council)
        self.assertFalse(promise.has_promise)
        self.assertIsNone(promise.domain)
        self.assertEqual(promise.last_checked, "2026-11")
        self.assertEqual(promise.notes, "nothing found")

    def test_import_skips_and_warnings(self):
        counts, warnings = self.import_promises()

        # East Borsetshire's rows are both skipped, so it stays unknown
        council = Council.objects.get(authority_code="EBRS")
        self.assertEqual(Promise.objects.filter(council=council).count(), 0)

        self.assertEqual(
            warnings,
            [
                "Row 6 (Borsetshire): ignored unrecognised ceuk review outcome "
                "'Better, probably'",
                "Row 7 (Borsetshire): unrecognised status 'Met'",
                "Row 8 (Borsetshire): has a blank domain, but the council also "
                "has promises",
                "Row 10 (East Borsetshire): has a blank domain and no last "
                "checked date",
                "Row 11 (East Borsetshire): has a blank domain, but also has "
                "promise details",
                "Row 12 (Ambridge Parish Council): could not match council name "
                "to a GSS code",
                "Row 13 (Felpersham): no council with GSS code E00000099",
            ],
        )
        self.assertEqual(counts["skipped"], 6)
        self.assertEqual(Promise.objects.count(), 6)

    def test_import_replaces_existing_promises(self):
        council = Council.objects.get(authority_code="BORS")
        Promise.objects.create(council=council, has_promise=True, text="old")
        self.import_promises()
        self.assertFalse(Promise.objects.filter(text="old").exists())

    def test_command_output(self):
        with self.settings(PROMISES_CSV="caps/tests/test_promises.csv"):
            out = self.call_command()
        self.assertIn("promise (latest): 2", out)
        self.assertIn("skipped: 6", out)


class ImportTagsTestCase(TestCase):
    fixtures = ["test_council_tags.json"]

    def test_import_tags(self):
        with self.settings(TAGS_CSV="caps/tests/test_tags.csv"):
            create_tags()

            tag = Tag.objects.get(slug="a-tag")
            self.assertEqual(tag.name, "A Tag")
            self.assertEqual(tag.colour, "red")
            self.assertEqual(tag.description_singular, "Singular description")
            self.assertEqual(tag.description_plural, "Plural description")
            self.assertEqual(tag.image_url, "http://example.org/image.png")

    def test_import_council_tags(self):
        with self.settings(
            TAGS_CSV="caps/tests/test_tags.csv",
            COUNCIL_TAGS_CSV="caps/tests/test_council_tags.csv",
        ):
            create_tags()
            create_council_tags()

            tag = Tag.objects.get(slug="a-tag")
            council = Council.objects.get(authority_code="BRS")

            council_tag = CouncilTag.objects.get(tag=tag, council=council)
            self.assertIsNotNone(council_tag)

            tag = Tag.objects.get(slug="top-gov")
            count = CouncilTag.objects.filter(tag=tag).count()
            self.assertEqual(count, 1)

            tag = Tag.objects.get(slug="listed")
            count = CouncilTag.objects.filter(tag=tag).count()
            self.assertEqual(count, 2)

            tag = Tag.objects.get(slug="question")
            count = CouncilTag.objects.filter(tag=tag).count()
            self.assertEqual(count, 2)
