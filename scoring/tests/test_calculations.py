from django.test import TestCase

from cape.models import Council
from scoring.models import PlanSection, PlanSectionScore, PlanScore


class TestAverageSectionScores(TestCase):
    fixtures = ["test_averages.json"]

    def test_basic_averages(self):
        averages = PlanSection.get_average_scores()

        self.assertEquals(
            averages,
            {
                "total": {"score": 23, "max": 25, "percentage": 23},
                "s1_gov": {"score": 13, "max": 19},
                "s2_m_a": {"score": 10, "max": 18},
            },
        )

    def test_zero_scores_excluded(self):
        averages = PlanSection.get_average_scores()

        self.assertEqual(
            averages,
            {
                "total": {"score": 23, "max": 25, "percentage": 23},
                "s1_gov": {"score": 13, "max": 19},
                "s2_m_a": {"score": 10, "max": 18},
            },
        )

        council = Council.objects.get(authority_code="NBS")
        plan_score = PlanScore.objects.create(
            council=council, year=2021, weighted_total=0, total=0
        )

        averages = PlanSection.get_average_scores()

        self.assertEqual(
            averages,
            {
                "total": {"score": 23, "max": 25, "percentage": 23},
                "s1_gov": {"score": 13, "max": 19},
                "s2_m_a": {"score": 10, "max": 18},
            },
        )


class TestGetAllScores(TestCase):
    fixtures = ["test_averages.json"]

    def test_all_scores(self):
        all_scores = PlanSectionScore.get_all_council_scores()

        self.assertEqual(
            all_scores,
            {
                1: {
                    "s1_gov": {
                        "score": 15,
                        "max": 19,
                    },
                    "s2_m_a": {
                        "score": 10,
                        "max": 18,
                    },
                },
                2: {
                    "s1_gov": {
                        "score": 14,
                        "max": 19,
                    },
                    "s2_m_a": {
                        "score": 4,
                        "max": 18,
                    },
                },
                3: {
                    "s1_gov": {
                        "score": 11,
                        "max": 19,
                    },
                    "s2_m_a": {
                        "score": 13,
                        "max": 18,
                    },
                },
                4: {
                    "s1_gov": {
                        "score": 12,
                        "max": 19,
                    },
                    "s2_m_a": {
                        "score": 12,
                        "max": 18,
                    },
                },
            },
        )
