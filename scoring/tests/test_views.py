from django.test import TestCase, Client

from django.urls import reverse

from caps.models import Council
from scoring.models import PlanSectionScore, PlanScore


class TestAnswerView(TestCase):
    fixtures = ["test_answers.json"]

    def setUp(self):
        self.client = Client()

    def test_answer_view(self):
        url = reverse("answers", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="scoring.example.com")
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            {
                "s1_gov": {
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 0,
                            "section": "s1_gov",
                            "score": 0,
                            "type": "HEADER",
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                        },
                    ],
                    "avg": 13.0,
                    "max_score": 19,
                    "description": "Governance, development and funding",
                    "score": 15,
                },
                "s2_m_a": {
                    "answers": [
                        {
                            "code": "s2_m_a_q1_sp1",
                            "display_code": "q1_sp1",
                            "question": "The answer is a Boolean",
                            "answer": "-",
                            "max": 1,
                            "section": "s2_m_a",
                            "score": 0,
                            "type": "CHECKBOX",
                        },
                    ],
                    "avg": 9.8,
                    "max_score": 18,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                },
            },
        )

    def test_averages_use_groupings(self):
        """
        When calculating average scores we should only be generating them for councils
        in the same group
        """
        council = Council.objects.get(authority_code="WBS")
        council.authority_type = "NMD"
        council.save()

        url = reverse("answers", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="scoring.example.com")
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            {
                "s1_gov": {
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 0,
                            "section": "s1_gov",
                            "score": 0,
                            "type": "HEADER",
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                        },
                    ],
                    "avg": 13.7,
                    "max_score": 19,
                    "description": "Governance, development and funding",
                    "score": 15,
                },
                "s2_m_a": {
                    "answers": [
                        {
                            "code": "s2_m_a_q1_sp1",
                            "display_code": "q1_sp1",
                            "question": "The answer is a Boolean",
                            "answer": "-",
                            "max": 1,
                            "section": "s2_m_a",
                            "score": 0,
                            "type": "CHECKBOX",
                        },
                    ],
                    "avg": 8.7,
                    "max_score": 18,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                },
            },
        )

    def test_zero_sections_scores_used_in_averages(self):
        council = Council.objects.get(authority_code="WBS")
        section = PlanSectionScore.objects.get(
            plan_score__council_id=council.id, plan_section__code="s1_gov"
        )
        section.score = 0
        section.weighted_score = 0
        section.save()

        url = reverse("answers", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="scoring.example.com")
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            {
                "s1_gov": {
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 0,
                            "section": "s1_gov",
                            "score": 0,
                            "type": "HEADER",
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                        },
                    ],
                    "avg": 10.2,
                    "max_score": 19,
                    "description": "Governance, development and funding",
                    "score": 15,
                },
                "s2_m_a": {
                    "answers": [
                        {
                            "code": "s2_m_a_q1_sp1",
                            "display_code": "q1_sp1",
                            "question": "The answer is a Boolean",
                            "answer": "-",
                            "max": 1,
                            "section": "s2_m_a",
                            "score": 0,
                            "type": "CHECKBOX",
                        },
                    ],
                    "avg": 9.8,
                    "max_score": 18,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                },
            },
        )

    def test_zero_plan_score_not_used_in_averages(self):
        council = Council.objects.get(authority_code="WBS")
        plan = PlanScore.objects.get(council=council)
        plan.total = 0
        plan.weighted_score = 0
        plan.save()

        url = reverse("answers", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="scoring.example.com")
        sections = response.context["sections"]

        self.assertEquals(
            sections,
            {
                "s1_gov": {
                    "answers": [
                        {
                            "code": "s1_gov_q1",
                            "display_code": "q1",
                            "question": "This is a sub header",
                            "answer": "-",
                            "max": 0,
                            "section": "s1_gov",
                            "score": 0,
                            "type": "HEADER",
                        },
                        {
                            "code": "s1_gov_q1_sp1",
                            "display_code": "q1_sp1",
                            "question": "The answer is True or False",
                            "answer": "True",
                            "max": 1,
                            "section": "s1_gov",
                            "score": 1,
                            "type": "CHECKBOX",
                        },
                    ],
                    "avg": 13.7,
                    "max_score": 19,
                    "description": "Governance, development and funding",
                    "score": 15,
                },
                "s2_m_a": {
                    "answers": [
                        {
                            "code": "s2_m_a_q1_sp1",
                            "display_code": "q1_sp1",
                            "question": "The answer is a Boolean",
                            "answer": "-",
                            "max": 1,
                            "section": "s2_m_a",
                            "score": 0,
                            "type": "CHECKBOX",
                        },
                    ],
                    "avg": 8.7,
                    "max_score": 18,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                },
            },
        )