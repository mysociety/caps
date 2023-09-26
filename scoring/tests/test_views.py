from caps.models import Council
from django.test import Client, TestCase
from django.urls import reverse
from scoring.models import PlanScore, PlanSectionScore


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


class TestAnswerView(TestCase):
    fixtures = ["test_answers.json"]

    def setUp(self):
        self.client = Client()

    def test_answer_view(self):
        url = reverse("scoring:council", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        sections = response.context["sections"]

        self.assertEqual(
            sections,
            [
                {
                    "top_performer": None,
                    "code": "s1_b_h",
                    "description": "Buildings & Heating",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
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
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 2,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                        },
                    ],
                    "avg": 13.0,
                    "max_score": 19,
                    "max_count": 0,
                    "score": 15,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "top_performer": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
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
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": None,
                    "code": "s1_b_h",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
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
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
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
                        },
                    ],
                    "avg": 13.7,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Buildings & Heating",
                    "score": 15,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "top_performer": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 8.7,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
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
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": None,
                    "code": "s1_b_h",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
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
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 2,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                        },
                    ],
                    "avg": 10.2,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Buildings & Heating",
                    "score": 15,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "top_performer": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
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
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": None,
                    "code": "s1_b_h",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
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
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 2,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                        },
                    ],
                    "avg": 13.7,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Buildings & Heating",
                    "score": 15,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "top_performer": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 8.7,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
                    "comparisons": [],
                    "non_negative_max": 10,
                    "negative_points": 0,
                },
            ],
        )


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
            for council in councils.all()
        ]

        self.assertEquals(
            performers,
            [
                {"score": 25.0, "code": "BRS", "top_performer": "unitary"},
                {"score": 24.0, "code": "WBS", "top_performer": None},
                {"score": 24.0, "code": "SBS", "top_performer": None},
                {"score": 19.0, "code": "EBS", "top_performer": None},
                {"score": None, "code": "NBS", "top_performer": None},
            ],
        )

    def test_answer_view(self):
        url = reverse("scoring:council", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": "unitary",
                    "code": "s1_b_h",
                    "answers": [
                        {
                            "code": "s1_b_h_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
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
                        },
                        {
                            "code": "s1_b_h_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_b_h",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 2,
                            "comparisons": [],
                            "negative": False,
                            "evidence_links": [],
                            "how_marked": "",
                            "how_marked_display": "",
                            "weighting": "Low",
                        },
                    ],
                    "avg": 13.0,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Buildings & Heating",
                    "score": 15,
                    "comparisons": [],
                    "non_negative_max": 15,
                    "negative_points": 0,
                },
                {
                    "top_performer": None,
                    "code": "s2_tran",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Transport",
                    "score": 10,
                    "comparisons": [],
                    "non_negative_max": 10,
                    "negative_points": 0,
                },
            ],
        )
