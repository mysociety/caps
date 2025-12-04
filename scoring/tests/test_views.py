from django.test import Client, TestCase, override_settings
from django.urls import reverse

from caps.models import Council
from scoring.models import PlanScore, PlanSectionScore


def strip_sections(sections):
    return [{k: v for k, v in s.items() if k != "section_score"} for s in sections]


class TestHomePageView(TestCase):
    fixtures = ["test_homepage.json"]

    def setUp(self):
        self.client = Client()

    def test_homepage(self):
        url = reverse("scoring:home", urlconf="scoring.urls")
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")

        councils = response.context["council_data"]
        self.assertEquals(len(councils), 1)
        self.assertEquals(councils[0]["name"], "Borsetshire County")

    def test_council_lists(self):
        types = {
            "district": "South Borsetshire",
            "combined": "North Borsetshire",
            "county": "West Borsetshire",
            "northern-ireland": "East Borsetshire",
        }

        for slug, name in types.items():
            url = reverse("scoring:scoring", urlconf="scoring.urls", args=[slug])
            response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")

            councils = response.context["council_data"]
            self.assertEquals(len(councils), 1)
            self.assertEquals(councils[0]["name"], name)


@override_settings(PLAN_YEAR="2023")
class TestAnswerView(TestCase):
    fixtures = ["test_answers.json"]

    def setUp(self):
        self.client = Client()

    def test_answer_view(self):
        url = reverse("scoring:council", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        sections = strip_sections(response.context["sections"])

        self.assertEqual(
            sections,
            [
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s1_b_h",
                    "description": "Buildings & Heating",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "criteria": "",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 2,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": True,
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "criteria": "",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 1,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": False,
                        },
                    ],
                    "avg": 13.0,
                    "max_score": 19,
                    "max_count": 0,
                    "score": 15,
                    "weighted_score": 15.0,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
                    "weighted_score": 10.0,
                    "comparisons": [],
                    "non_negative_max": 10,
                    "negative_points": 0,
                },
            ],
        )

    def test_averages_use_groupings(self):
        """
        When calculating average scores we should only be generating them for councils
        in the same group
        """
        council = Council.objects.get(authority_code="WBS")
        council.authority_type = "NMD"
        council.save()

        url = reverse("scoring:council", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        sections = strip_sections(response.context["sections"])

        self.assertEquals(
            sections,
            [
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s1_b_h",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "criteria": "",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 1,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": True,
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "criteria": "",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 1,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": False,
                        },
                    ],
                    "avg": 13.7,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Buildings & Heating",
                    "score": 15,
                    "weighted_score": 15.0,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 8.7,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
                    "weighted_score": 10.0,
                    "comparisons": [],
                    "non_negative_max": 10,
                    "negative_points": 0,
                },
            ],
        )

    def test_zero_sections_scores_used_in_averages(self):
        council = Council.objects.get(authority_code="WBS")
        section = PlanSectionScore.objects.get(
            plan_score__council_id=council.id, plan_section__code="s1_b_h"
        )
        section.score = 0
        section.weighted_score = 0
        section.save()

        url = reverse("scoring:council", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        sections = strip_sections(response.context["sections"])

        self.assertEquals(
            sections,
            [
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s1_b_h",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "criteria": "",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 2,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": True,
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "criteria": "",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 1,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": False,
                        },
                    ],
                    "avg": 10.2,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Buildings & Heating",
                    "score": 15,
                    "weighted_score": 15.0,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
                    "weighted_score": 10.0,
                    "comparisons": [],
                    "non_negative_max": 10,
                    "negative_points": 0,
                },
            ],
        )

    def test_zero_plan_score_not_used_in_averages(self):
        council = Council.objects.get(authority_code="WBS")
        plan = PlanScore.objects.get(council=council)
        plan.total = 0
        plan.weighted_score = 0
        plan.save()

        url = reverse("scoring:council", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        sections = strip_sections(response.context["sections"])

        self.assertEquals(
            sections,
            [
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s1_b_h",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "criteria": "",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 2,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": True,
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "criteria": "",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 1,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": False,
                        },
                    ],
                    "avg": 13.7,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Buildings & Heating",
                    "score": 15,
                    "weighted_score": 15.0,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 8.7,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
                    "weighted_score": 10.0,
                    "comparisons": [],
                    "non_negative_max": 10,
                    "negative_points": 0,
                },
            ],
        )


@override_settings(PLAN_YEAR="2023")
class TestTopPerormersInViews(TestCase):
    fixtures = ["test_top_performers.json"]

    def setUp(self):
        self.client = Client()

    def test_homepage_view(self):
        url = reverse("scoring:home", urlconf="scoring.urls")
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        councils = response.context["council_data"]

        performers = [
            {
                "score": council["score"],
                "code": council["authority_code"],
                "top_performer": council["top_performer"],
            }
            for council in councils
        ]

        self.assertEquals(
            performers,
            [
                {"score": 25.0, "code": "BRS", "top_performer": "unitary"},
                {"score": 24.0, "code": "SBS", "top_performer": None},
                {"score": 24.0, "code": "WBS", "top_performer": None},
                {"score": 19.0, "code": "EBS", "top_performer": None},
                {"score": None, "code": "NBS", "top_performer": None},
            ],
        )

    def test_answer_view(self):
        url = reverse("scoring:council", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        sections = strip_sections(response.context["sections"])

        self.assertEquals(
            sections,
            [
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": "unitary",
                    "most_improved": None,
                    "code": "s1_b_h",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "criteria": "",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 1,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": True,
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "criteria": "",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 1,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                            "is_council_operations_only": False,
                        },
                    ],
                    "avg": 13.0,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Buildings & Heating",
                    "score": 15,
                    "weighted_score": 15.0,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
                    "weighted_score": 10.0,
                    "comparisons": [],
                    "non_negative_max": 10,
                    "negative_points": 0,
                },
            ],
        )


@override_settings(PLAN_YEAR="2025")
class TestPreviousYearAnswerView(TestCase):
    fixtures = ["test_previous_years_answers.json"]

    def setUp(self):
        self.client = Client()

    def test_answer_view(self):
        url = reverse("scoring:council", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        sections = strip_sections(response.context["sections"])

        self.assertEqual(
            sections,
            [
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s1_b_h",
                    "description": "Buildings & Heating",
                    "max_score": 19,
                    "max_count": 0,
                    "score": 18,
                    "weighted_score": 18.0,
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "criteria": "",
                            "type": "HEADER",
                            "max": 1,
                            "section": "s1_b_h",
                            "answer": "-",
                            "score": 0,
                            "negative": False,
                            "how_marked": "",
                            "how_marked_display": "",
                            "is_council_operations_only": True,
                            "weighting": "Low",
                            "evidence_links": [],
                            "council_count": 1,
                            "comparisons": [],
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "criteria": "",
                            "type": "CHECKBOX",
                            "max": 1,
                            "section": "s1_b_h",
                            "answer": "False",
                            "score": 1.0,
                            "negative": False,
                            "how_marked": "",
                            "how_marked_display": "",
                            "is_council_operations_only": False,
                            "weighting": "Low",
                            "evidence_links": [],
                            "previous_q_code": "s1_b_h_q1_sp1",
                            "previous_score": 1.0,
                            "previous_max": 1,
                            "change": 0,
                            "council_count": 0,
                            "comparisons": [],
                        },
                    ],
                    "comparisons": [],
                    "non_negative_max": 18,
                    "negative_points": 0,
                    "previous_score": 15.0,
                    "change": 3.0,
                    "avg": 14.3,
                },
                {
                    "council_name": "Borsetshire County",
                    "council_slug": "borsetshire",
                    "top_performer": None,
                    "most_improved": None,
                    "code": "s2_tran",
                    "description": "Transport",
                    "max_score": 18,
                    "max_count": 0,
                    "score": 10,
                    "weighted_score": 10.0,
                    "answers": [],
                    "comparisons": [],
                    "non_negative_max": 10,
                    "negative_points": 0,
                    "previous_score": 10.0,
                    "change": 0.0,
                    "avg": 9.0,
                },
            ],
        )


@override_settings(PLAN_YEAR="2023")
class TestQuestionViewFilters(TestCase):
    """Test filtering functionality on QuestionView"""

    fixtures = ["test_answers.json"]

    def setUp(self):
        self.client = Client()

    def test_question_view_without_filters(self):
        """Test question view loads without filters applied"""
        url = reverse("scoring:question", urlconf="scoring.urls", args=["s1_b_h_q1"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")

        self.assertEqual(response.status_code, 200)
        # Note: test fixture doesn't have scoring groups, so no scores context

    def test_question_view_with_country_filter(self):
        """Test filtering by country parameter"""
        url = reverse("scoring:question", urlconf="scoring.urls", args=["s1_b_h_q1"])
        response = self.client.get(
            url, {"country": "1"}, HTTP_HOST="councilclimatescorecards.com"  # England
        )

        # Verify page loads successfully with filter parameter
        self.assertEqual(response.status_code, 200)

    def test_question_view_with_population_filter(self):
        """Test filtering by population parameter"""
        url = reverse("scoring:question", urlconf="scoring.urls", args=["s1_b_h_q1"])
        response = self.client.get(
            url, {"population": "50k-80k"}, HTTP_HOST="councilclimatescorecards.com"
        )

        # Verify page loads successfully with filter parameter
        self.assertEqual(response.status_code, 200)

    def test_question_view_with_multiple_filters(self):
        """Test applying multiple filters simultaneously"""
        url = reverse("scoring:question", urlconf="scoring.urls", args=["s1_b_h_q1"])
        response = self.client.get(
            url,
            {"country": "1", "ruc_cluster": "urban"},
            HTTP_HOST="councilclimatescorecards.com",
        )

        # Verify page loads successfully with multiple filter parameters
        self.assertEqual(response.status_code, 200)

    def test_question_view_filter_with_type_parameter(self):
        """Test that filters work alongside authority type parameter"""
        url = reverse("scoring:question", urlconf="scoring.urls", args=["s1_b_h_q1"])
        response = self.client.get(
            url,
            {"type": "single", "country": "1"},
            HTTP_HOST="councilclimatescorecards.com",
        )

        # Verify page loads successfully with type and filter parameters
        self.assertEqual(response.status_code, 200)

    def test_question_view_accepts_all_filter_parameters(self):
        """Test that all filter parameters are accepted without errors"""
        url = reverse("scoring:question", urlconf="scoring.urls", args=["s1_b_h_q1"])
        response = self.client.get(
            url,
            {
                "country": "1",
                "ruc_cluster": "urban",
                "population": "50k-80k",
                "imdq": "1",
                "control": "Labour",
                "region": "London",
            },
            HTTP_HOST="councilclimatescorecards.com",
        )

        # Verify page loads successfully with all filter parameters
        self.assertEqual(response.status_code, 200)
