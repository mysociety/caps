from collections import defaultdict

from django.db import models

from caps.models import Council

class PlanScore(models.Model):
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    weighted_total = models.PositiveSmallIntegerField(default=0)
    total = models.PositiveSmallIntegerField(default=0)


class PlanSection(models.Model):
    code = models.CharField(max_length=100)
    description = models.CharField(max_length=1000)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    max_score = models.PositiveSmallIntegerField(null=True)
    max_weighted_score = models.PositiveSmallIntegerField(null=True)
    weight = models.PositiveSmallIntegerField(null=True)

    @classmethod
    def section_codes(cls):
        return cls.objects.distinct('code').values_list('code', flat=True)


class PlanSectionScore(models.Model):
    plan_score = models.ForeignKey(PlanScore, on_delete=models.CASCADE)
    plan_section = models.ForeignKey(PlanSection, on_delete=models.CASCADE)
    score = models.PositiveSmallIntegerField(default=0)
    weighted_score = models.PositiveSmallIntegerField(default=0)

    @classmethod
    def get_all_council_scores(cls):
        scores = cls.objects.all().select_related('plan_section', 'plan_score').filter(plan_score__total__gt=0).values('plan_score__total', 'plan_score__council_id', 'score', 'weighted_score', 'plan_section__code', 'plan_section__max_score')
        councils = defaultdict(dict)
        for score in scores:
            if score['plan_section__code'].find('(') != -1:
                continue
            councils[score['plan_score__council_id']][score['plan_section__code']] = { 'score': score['weighted_score'], 'max': score['plan_section__max_score'] }

        return councils

class PlanQuestion(models.Model):
    section = models.ForeignKey(PlanSection, on_delete=models.CASCADE)
    code = models.CharField(max_length=100)
    text = models.TextField(null=True, default='')
    max_score = models.PositiveSmallIntegerField(default=0)
    question_type = models.CharField(max_length=100) # needs choices

class PlanQuestionScore(models.Model):
    plan_score = models.ForeignKey(PlanScore, on_delete=models.CASCADE)
    plan_question = models.ForeignKey(PlanQuestion, on_delete=models.CASCADE, related_name='questions')
    answer = models.TextField(null=True, default='')
    score = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(null=True, default='')
