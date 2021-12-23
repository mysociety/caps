from django.test import TestCase, Client

from django.urls import reverse

from caps.models import Council


class TestAnswerView(TestCase):
    fixtures = ["test_answers.json"]

    def setUp(self):
        self.client = Client()

    def test_answer_view(self):
        url = reverse("answers", urlconf="scoring.urls", args=["borsetshire"])
        response = self.client.get(url, HTTP_HOST="councilclimatescorecards.com")
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
                    "answers": [],
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
                    "answers": [],
                    "avg": 8.7,
                    "max_score": 18,
                    "description": "Mitigation and adaptation",
                    "score": 10,
                },
            },
        )
