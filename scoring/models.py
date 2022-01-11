from collections import defaultdict

from django.db import models
from django.db.models import Avg, Max

from caps.models import Council

class PlanScore(models.Model):
    """
    Overall score for a council's plan for a particular year
    """
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(null=True, blank=True)

    # these are percentages
    weighted_total = models.FloatField(default=0)
    total = models.FloatField(default=0)


class PlanSection(models.Model):
    """
    Details of a section in the scoring
    """

    code = models.CharField(max_length=100)
    description = models.CharField(max_length=1000)
    year = models.PositiveSmallIntegerField(null=True, blank=True)

    @classmethod
    def section_codes(cls):
        return cls.objects.distinct('code').values_list('code', flat=True)

    @classmethod
    def get_average_scores(cls):
        """
        This excludes plans with zero score as it's assumed that if they have 0 then they
        were not marked, or the council has no plan, and hence including them would artificially
        reduce the average.
        """
        has_score = PlanScore.objects.filter(total__gt=0)
        has_score_avg = has_score.aggregate(average=Avg('weighted_total'))
        has_score_list = has_score.values_list('pk', flat=True)

        scores = cls.objects.filter(
            plansectionscore__plan_score__in=list(has_score_list)
        ).annotate(
            average_score=Avg('plansectionscore__score'),
            max_score=Max('plansectionscore__max_score')
        )

        averages = {}
        max_score = 0
        for score in scores:
            max_score = max_score + score.max_score
            averages[score.code] = { 'score': round(score.average_score), 'max': score.max_score }

        avg_score = round(has_score_avg['average'])
        averages['total'] = { 'score': avg_score, 'max': max_score, 'percentage': round( ( avg_score / max_score ) * 100 ) }

        return averages


class PlanSectionScore(models.Model):
    """
    Score for a section of a council's plan
    """

    plan_score = models.ForeignKey(PlanScore, on_delete=models.CASCADE)
    plan_section = models.ForeignKey(PlanSection, on_delete=models.CASCADE)
    score = models.PositiveSmallIntegerField(default=0)
    # store the max score here because not all council types get asked the same set of questions
    # so there may not be a consistent per section max score
    max_score = models.PositiveSmallIntegerField(default=0)
    # this is a percentage
    weighted_score = models.FloatField(default=0)

    @classmethod
    def get_all_council_scores(cls):
        """
        This excludes plans with zero score as it's assumed that if they have 0 then they
        were not marked, or the council has no plan
        """
        scores = cls.objects.all().select_related('plan_section', 'plan_score').filter(plan_score__total__gt=0).values('plan_score__total', 'plan_score__council_id', 'score', 'weighted_score', 'plan_section__code', 'max_score')
        councils = defaultdict(dict)
        for score in scores:
            councils[score['plan_score__council_id']][score['plan_section__code']] = { 'score': score['score'], 'max': score['max_score'] }

        return councils

class PlanQuestion(models.Model):
    """
    Details of an individual question in the scoring.

    NB: some question types might be sub section headers and have no score
    """

    section = models.ForeignKey(PlanSection, on_delete=models.CASCADE)
    code = models.CharField(max_length=100)
    text = models.TextField(null=True, default='')
    max_score = models.PositiveSmallIntegerField(default=0)
    question_type = models.CharField(max_length=100) # needs choices

class PlanQuestionScore(models.Model):
    """
    Score for an individual question for a council's plan
    """

    plan_score = models.ForeignKey(PlanScore, on_delete=models.CASCADE)
    plan_question = models.ForeignKey(PlanQuestion, on_delete=models.CASCADE, related_name='questions')
    answer = models.TextField(null=True, default='')
    score = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(null=True, default='')
