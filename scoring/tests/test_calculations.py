from django.test import TestCase

from caps.models import Council
from scoring.models import PlanSection, PlanScore


class TestAverageSectionScores(TestCase):
    fixtures = ["test_averages.json"]

    def test_basic_averages(self):
        averages = PlanSection.get_average_scores()

        self.assertEquals(
            averages,
            {
                "total": {"score": 23, "max": 37, "percentage": 62},
                "s1_gov": {"score": 13, "max": 19},
                "s2_m_a": {"score": 10, "max": 18},
            },
        )

    def test_zero_scores_excluded(self):
        averages = PlanSection.get_average_scores()

        self.assertEqual(
            averages,
            {
                "total": {"score": 23, "max": 37, "percentage": 62},
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
                "total": {"score": 23, "max": 37, "percentage": 62},
                "s1_gov": {"score": 13, "max": 19},
                "s2_m_a": {"score": 10, "max": 18},
            },
        )
