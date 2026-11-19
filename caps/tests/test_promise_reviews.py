from django.test import TestCase
from django.urls import reverse

from caps.management.commands.import_promises import review_outcome_2026_code
from caps.models import Council, Promise
from caps.promise_reviews import review_categories


class ReviewOutcomeCodeTestCase(TestCase):
    def test_review_outcome_2026_code(self):
        for outcome, expected in [
            ("Updated target - stronger", Promise.REVIEW_2026_STRONGER),
            ("Updated target - weaker", Promise.REVIEW_2026_WEAKER),
            ("New target", Promise.REVIEW_2026_NEW),
            ("New authority - new target", Promise.REVIEW_2026_NEW),
            ("Withdrawn", Promise.REVIEW_2026_WITHDRAWN),
            ("Target missed - no further target set", Promise.REVIEW_2026_MISSED),
            (
                "Target met; Target missed - no further target set",
                Promise.REVIEW_2026_MISSED,
            ),
            ("Target still current", Promise.REVIEW_2026_UNCHANGED),
            ("Wrong initially - target still current", Promise.REVIEW_2026_UNCHANGED),
            (" target STILL current ", Promise.REVIEW_2026_UNCHANGED),
            ("No Promise", None),
            ("", None),
        ]:
            with self.subTest(outcome):
                self.assertEqual(review_outcome_2026_code(outcome), expected)


class ReviewCategoriesTestCase(TestCase):
    def setUp(self):
        self.councils = {}

        council_ops = {"domain": Promise.COUNCIL_OPERATIONS}
        whole_area = {"domain": Promise.WHOLE_AREA}

        # stronger, plus an unchanged target in another domain
        self.create(
            "Strongshire",
            {**council_ops, "target_year": 2040, "status": Promise.SUPERSEDED},
            {
                **council_ops,
                "target_year": 2030,
                "review_outcome_2026": Promise.REVIEW_2026_STRONGER,
            },
            {
                **whole_area,
                "target_year": 2050,
                "review_outcome_2026": Promise.REVIEW_2026_UNCHANGED,
            },
        )
        # weaker, and narrowed from the whole area to council operations
        self.create(
            "Narrowshire",
            {**whole_area, "target_year": 2030, "status": Promise.SUPERSEDED},
            {
                **council_ops,
                "target_year": 2030,
                "review_outcome_2026": Promise.REVIEW_2026_WEAKER,
            },
        )
        self.create(
            "Newshire",
            {
                **whole_area,
                "target_year": 2045,
                "review_outcome_2026": Promise.REVIEW_2026_NEW,
            },
        )
        self.create(
            "Withdrawnshire",
            {
                **council_ops,
                "target_year": 2030,
                "status": Promise.WITHDRAWN,
                "review_outcome_2026": Promise.REVIEW_2026_WITHDRAWN,
            },
            {**council_ops, "type": Promise.WITHDRAWAL},
        )
        self.create(
            "Missedshire",
            {
                **council_ops,
                "target_year": 2025,
                "review_outcome_2026": Promise.REVIEW_2026_MISSED,
            },
        )
        # no review outcome, so not in any category
        self.create("Unreviewedshire", {**council_ops, "target_year": 2030})

    def create(self, name, *promises):
        council = Council.objects.create(
            name=name,
            slug=name.lower(),
            authority_code=name[:4].upper(),
            gss_code=f"E0000000{len(self.councils)}",
            country=Council.ENGLAND,
        )
        self.councils[name] = council
        for fields in promises:
            Promise.objects.create(council=council, has_promise=True, **fields)

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
