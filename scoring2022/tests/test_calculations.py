from django.test import TestCase

from caps.models import Council
from scoring.models import PlanScore, PlanSection, PlanSectionScore


class TestAverageSectionScores(TestCase):
    fixtures = ["2022_test_averages.json"]

    def test_basic_averages(self):
        averages = PlanSection.get_average_scores(year=2021)

        self.assertEquals(
            averages,
            {
                "total": {"score": 23, "max": 25, "percentage": 23},
                "s1_gov": {
                    "code": "s1_gov",
                    "score": 13,
                    "title": "Governance, development and funding",
                    "max": 19,
                    "weighted": 13,
                },
                "s2_m_a": {
                    "code": "s2_m_a",
                    "score": 10,
                    "title": "Mitigation and adaptation",
                    "max": 18,
                    "weighted": 10,
                },
            },
        )

    def test_zero_scores_excluded(self):
        averages = PlanSection.get_average_scores(year=2021)

        self.assertEqual(
            averages,
            {
                "total": {"score": 23, "max": 25, "percentage": 23},
                "s1_gov": {
                    "code": "s1_gov",
                    "score": 13,
                    "title": "Governance, development and funding",
                    "max": 19,
                    "weighted": 13,
                },
                "s2_m_a": {
                    "code": "s2_m_a",
                    "score": 10,
                    "title": "Mitigation and adaptation",
                    "max": 18,
                    "weighted": 10,
                },
            },
        )

        council = Council.objects.get(authority_code="NBS")
        plan_score = PlanScore.objects.create(
            council=council, year=2021, weighted_total=0, total=0
        )

        averages = PlanSection.get_average_scores(year=2021)

        self.assertEqual(
            averages,
            {
                "total": {"score": 23, "max": 25, "percentage": 23},
                "s1_gov": {
                    "code": "s1_gov",
                    "score": 13,
                    "title": "Governance, development and funding",
                    "max": 19,
                    "weighted": 13,
                },
                "s2_m_a": {
                    "code": "s2_m_a",
                    "score": 10,
                    "title": "Mitigation and adaptation",
                    "max": 18,
                    "weighted": 10,
                },
            },
        )


class TestGetAllScores(TestCase):
    fixtures = ["2022_test_averages.json"]

    def test_all_scores(self):
        all_scores = PlanSectionScore.get_all_council_scores(2021)

        self.assertEqual(
            all_scores,
            {
                1: {
                    "s1_gov": {
                        "code": "s1_gov",
                        "score": 15,
                        "max": 19,
                        "weighted": 15,
                        "change": None,
                    },
                    "s2_m_a": {
                        "code": "s2_m_a",
                        "score": 10,
                        "max": 18,
                        "weighted": 10,
                        "change": None,
                    },
                },
                2: {
                    "s1_gov": {
                        "code": "s1_gov",
                        "score": 14,
                        "max": 19,
                        "weighted": 14,
                        "change": None,
                    },
                    "s2_m_a": {
                        "code": "s2_m_a",
                        "score": 4,
                        "max": 18,
                        "weighted": 4,
                        "change": None,
                    },
                },
                3: {
                    "s1_gov": {
                        "code": "s1_gov",
                        "score": 11,
                        "max": 19,
                        "weighted": 11,
                        "change": None,
                    },
                    "s2_m_a": {
                        "code": "s2_m_a",
                        "score": 13,
                        "max": 18,
                        "weighted": 13,
                        "change": None,
                    },
                },
                4: {
                    "s1_gov": {
                        "code": "s1_gov",
                        "score": 12,
                        "max": 19,
                        "weighted": 12,
                        "change": None,
                    },
                    "s2_m_a": {
                        "code": "s2_m_a",
                        "score": 12,
                        "max": 18,
                        "weighted": 12,
                        "change": None,
                    },
                },
            },
        )
