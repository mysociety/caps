import json
import os
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from caps.models import Council, Promise
from caps.promise_reviews import (
    load_review_outcomes,
    outcome_category,
    review_categories,
    write_review_outcomes,
)


class OutcomeCategoryTestCase(TestCase):
    def test_outcome_category(self):
        for outcome, expected in [
            ("Updated target - stronger", "stronger"),
            ("Updated target - weaker", "weaker"),
            ("New target", "new"),
            ("New authority - new target", "new"),
            ("Withdrawn", "withdrawn"),
            ("Target missed - no further target set", "missed"),
            ("Target met; Target missed - no further target set", "missed"),
            ("Target still current", "unchanged"),
            ("Wrong initially - target still current", "unchanged"),
            (" target STILL current ", "unchanged"),
            ("No Promise", None),
            ("", None),
        ]:
            with self.subTest(outcome):
                self.assertEqual(outcome_category(outcome), expected)


class ReviewOutcomesFileTestCase(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name, "promise_reviews.json"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file(self):
        self.assertIsNone(load_review_outcomes(self.path))

    def test_round_trip(self):
        write_review_outcomes({1: "New target", 2: "Withdrawn"}, self.path)
        self.assertEqual(
            load_review_outcomes(self.path), {1: "New target", 2: "Withdrawn"}
        )

    def test_reloads_when_file_changes(self):
        write_review_outcomes({1: "New target"}, self.path)
        self.assertEqual(load_review_outcomes(self.path), {1: "New target"})

        write_review_outcomes({1: "Withdrawn"}, self.path)
        # make sure the modification time changes, however fast the test runs
        mtime = os.path.getmtime(self.path) + 10
        os.utime(self.path, (mtime, mtime))
        self.assertEqual(load_review_outcomes(self.path), {1: "Withdrawn"})


class ReviewCategoriesTestCase(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name, "promise_reviews.json"))
        self.settings_override = override_settings(PROMISE_REVIEWS_JSON=self.path)
        self.settings_override.enable()

        self.outcomes = {}
        self.councils = {}

        council_ops = {"domain": Promise.COUNCIL_OPERATIONS}
        whole_area = {"domain": Promise.WHOLE_AREA}

        # stronger, plus an unchanged target in another domain
        self.create(
            "Strongshire",
            ({**council_ops, "target_year": 2040, "status": Promise.SUPERSEDED}, ""),
            ({**council_ops, "target_year": 2030}, "Updated target - stronger"),
            ({**whole_area, "target_year": 2050}, "Target still current"),
        )
        # weaker, and narrowed from the whole area to council operations
        self.create(
            "Narrowshire",
            ({**whole_area, "target_year": 2030, "status": Promise.SUPERSEDED}, ""),
            ({**council_ops, "target_year": 2030}, "Updated target - weaker"),
        )
        self.create(
            "Newshire",
            ({**whole_area, "target_year": 2045}, "New target"),
        )
        self.create(
            "Withdrawnshire",
            (
                {**council_ops, "target_year": 2030, "status": Promise.WITHDRAWN},
                "Withdrawn",
            ),
            ({**council_ops, "type": Promise.WITHDRAWAL}, ""),
        )
        self.create(
            "Missedshire",
            (
                {**council_ops, "target_year": 2025},
                "Target missed - no further target set",
            ),
        )
        # no review outcome, so not in any category
        self.create("Unreviewedshire", ({**council_ops, "target_year": 2030}, ""))

        write_review_outcomes(self.outcomes, self.path)

    def tearDown(self):
        self.settings_override.disable()
        self.tmp.cleanup()

    def create(self, name, *promises):
        council = Council.objects.create(
            name=name,
            slug=name.lower(),
            authority_code=name[:4].upper(),
            gss_code=f"E0000000{len(self.councils)}",
            country=Council.ENGLAND,
        )
        self.councils[name] = council
        for fields, outcome in promises:
            promise = Promise.objects.create(
                council=council, has_promise=True, **fields
            )
            if outcome:
                self.outcomes[promise.pk] = outcome

    def get_categories(self):
        return {category.slug: category for category in review_categories()}

    def test_councils_in_each_category(self):
        categories = self.get_categories()
        self.assertEqual(
            {
                slug: [entry.council.name for entry in category.entries]
                for slug, category in categories.items()
            },
            {
                "stronger": ["Strongshire"],
                "weaker": ["Narrowshire"],
                "new": ["Newshire"],
                "withdrawn": ["Withdrawnshire"],
                "missed": ["Missedshire"],
                "unchanged": ["Strongshire"],
            },
        )

    def test_before_and_after(self):
        categories = self.get_categories()

        def years(promises):
            return [(p.get_status_display(), p.target_year) for p in promises]

        stronger = categories["stronger"].entries[0]
        self.assertEqual(years(stronger.before), [("Superseded", 2040)])
        self.assertEqual(years(stronger.after), [("Latest", 2030)])

        # no superseded council operations promise, so any domain
        weaker = categories["weaker"].entries[0]
        self.assertEqual(years(weaker.before), [("Superseded", 2030)])

        withdrawn = categories["withdrawn"].entries[0]
        self.assertEqual(years(withdrawn.before), [("Withdrawn", 2030)])
        self.assertEqual([p.type for p in withdrawn.after], [Promise.WITHDRAWAL])

        new = categories["new"].entries[0]
        self.assertEqual(new.before, [])

    def test_summaries(self):
        categories = self.get_categories()
        self.assertEqual(
            {
                slug: [entry.summary for entry in category.entries]
                for slug, category in categories.items()
            },
            {
                "stronger": ["2040 → 2030"],
                "weaker": ["Whole area 2030 → Council operations 2030"],
                "new": ["2045"],
                "withdrawn": ["Council operations 2030 → withdrawn"],
                "missed": ["2025"],
                "unchanged": ["2050"],
            },
        )

    def test_targets_page(self):
        response = self.client.get(reverse("targets"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<section id="stronger"')
        self.assertContains(response, 'href="#stronger"')
        self.assertContains(response, "2040 → 2030")
        self.assertContains(response, "Whole area 2030 → Council operations 2030")
        self.assertNotContains(response, "Unreviewedshire")

    def test_targets_page_without_review_file(self):
        os.remove(self.path)
        response = self.client.get(reverse("targets"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["categories"])
        self.assertContains(
            response, "We don’t have the results of the 2026 review yet"
        )
