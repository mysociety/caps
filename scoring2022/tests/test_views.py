from caps.models import Council
from django.test import Client, TestCase
from django.urls import reverse
from scoring.models import PlanScore, PlanSectionScore


class TestHomePageView(TestCase):
    fixtures = ["2022_test_homepage.json"]

    def setUp(self):
        self.client = Client()

    def test_homepage(self):
        url = reverse("home", urlconf="scoring2022.urls")
        response = self.client.get(
            "/plan-scorecards-2022" + url, HTTP_HOST="councilclimatescorecards.com"
        )

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
            url = reverse("scoring", urlconf="scoring2022.urls", args=[slug])
            response = self.client.get(
                "/plan-scorecards-2022" + url, HTTP_HOST="councilclimatescorecards.com"
            )

            councils = response.context["council_data"]
            self.assertEquals(len(councils), 1)
            self.assertEquals(councils[0]["name"], name)


class TestAnswerView(TestCase):
    fixtures = ["2022_test_answers.json"]

    def setUp(self):
        self.client = Client()

    def test_answer_view(self):
        url = reverse("council", urlconf="scoring2022.urls", args=["borsetshire"])
        response = self.client.get(
            "/plan-scorecards-2022" + url, HTTP_HOST="councilclimatescorecards.com"
        )
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": None,
                    "code": "s1_gov",
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 2,
                            "comparisons": [],
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 2,
                            "comparisons": [],
                        },
                    ],
                    "avg": 13.0,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Governance, development and funding",
                    "score": 15,
                    "comparisons": [],
                },
                {
                    "top_performer": None,
                    "code": "s2_m_a",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                    "comparisons": [],
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

        url = reverse("council", urlconf="scoring2022.urls", args=["borsetshire"])
        response = self.client.get(
            "/plan-scorecards-2022" + url, HTTP_HOST="councilclimatescorecards.com"
        )
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": None,
                    "code": "s1_gov",
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 1,
                            "comparisons": [],
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 1,
                            "comparisons": [],
                        },
                    ],
                    "avg": 13.7,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Governance, development and funding",
                    "score": 15,
                    "comparisons": [],
                },
                {
                    "top_performer": None,
                    "code": "s2_m_a",
                    "answers": [],
                    "avg": 8.7,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                    "comparisons": [],
                },
            ],
        )

    def test_zero_sections_scores_used_in_averages(self):
        council = Council.objects.get(authority_code="WBS")
        section = PlanSectionScore.objects.get(
            plan_score__council_id=council.id, plan_section__code="s1_gov"
        )
        section.score = 0
        section.weighted_score = 0
        section.save()

        url = reverse("council", urlconf="scoring2022.urls", args=["borsetshire"])
        response = self.client.get(
            "/plan-scorecards-2022" + url, HTTP_HOST="councilclimatescorecards.com"
        )
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": None,
                    "code": "s1_gov",
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 2,
                            "comparisons": [],
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 2,
                            "comparisons": [],
                        },
                    ],
                    "avg": 10.2,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Governance, development and funding",
                    "score": 15,
                    "comparisons": [],
                },
                {
                    "top_performer": None,
                    "code": "s2_m_a",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                    "comparisons": [],
                },
            ],
        )

    def test_zero_plan_score_not_used_in_averages(self):
        council = Council.objects.get(authority_code="WBS")
        plan = PlanScore.objects.get(council=council)
        plan.total = 0
        plan.weighted_score = 0
        plan.save()

        url = reverse("council", urlconf="scoring2022.urls", args=["borsetshire"])
        response = self.client.get(
            "/plan-scorecards-2022" + url, HTTP_HOST="councilclimatescorecards.com"
        )
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": None,
                    "code": "s1_gov",
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 2,
                            "comparisons": [],
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 2,
                            "comparisons": [],
                        },
                    ],
                    "avg": 13.7,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Governance, development and funding",
                    "score": 15,
                    "comparisons": [],
                },
                {
                    "top_performer": None,
                    "code": "s2_m_a",
                    "answers": [],
                    "avg": 8.7,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                    "comparisons": [],
                },
            ],
        )


class TestTopPerormersInViews(TestCase):
    fixtures = ["2022_test_top_performers.json"]

    def setUp(self):
        self.client = Client()

    def test_homepage_view(self):
        url = reverse("home", urlconf="scoring2022.urls", current_app="scoring2022")
        response = self.client.get(
            "/plan-scorecards-2022" + url, HTTP_HOST="councilclimatescorecards.com"
        )
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
                {"score": 24.0, "code": "WBS", "top_performer": None},
                {"score": 24.0, "code": "SBS", "top_performer": None},
                {"score": 19.0, "code": "EBS", "top_performer": None},
                {"score": None, "code": "NBS", "top_performer": None},
            ],
        )

    def test_answer_view(self):
        url = reverse("council", urlconf="scoring2022.urls", args=["borsetshire"])
        response = self.client.get(
            "/plan-scorecards-2022" + url, HTTP_HOST="councilclimatescorecards.com"
        )
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            [
                {
                    "top_performer": "unitary",
                    "code": "s1_gov",
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "pretty_code": "1.1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "HEADER",
                            "council_count": 1,
                            "comparisons": [],
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "pretty_code": "1.1.1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                            "council_count": 2,
                            "comparisons": [],
                        },
                    ],
                    "avg": 13.0,
                    "max_score": 19,
                    "max_count": 0,
                    "description": "Governance, development and funding",
                    "score": 15,
                    "comparisons": [],
                },
                {
                    "top_performer": None,
                    "code": "s2_m_a",
                    "answers": [],
                    "avg": 9.8,
                    "max_score": 18,
                    "max_count": 0,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                    "comparisons": [],
                },
            ],
        )
