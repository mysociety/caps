from django.db import models

class Council(models.Model):
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    authority_code = models.CharField(max_length=4)
    authority_type = models.CharField(max_length=4, blank=True)
    whatdotheyknow_id = models.IntegerField(null=True, blank=True)
    mapit_area_code = models.CharField(max_length=3, blank=True)
    website_url = models.URLField()

class PlanDocument(models.Model):

    ACTION_PLAN = 1
    CLIMATE_STRATEGY = 2
    SUMMARY_DOCUMENT = 3
    PRE_PLAN = 4
    MEETING_MINUTES = 5
    DOCUMENT_TYPE_CHOICES = [
        (ACTION_PLAN, 'Action plan'),
        (CLIMATE_STRATEGY, 'Climate strategy'),
        (SUMMARY_DOCUMENT, 'Summary document'),
        (PRE_PLAN, 'Pre-plan'),
        (MEETING_MINUTES, 'Meeting minutes'),
    ]

    COUNCIL_ONLY = 1
    WHOLE_AREA = 2
    SCOPE_CHOICES = [
        (COUNCIL_ONLY, 'Council only'),
        (WHOLE_AREA, 'Whole area'),
    ]

    DRAFT = 1
    APPROVED = 2

    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (APPROVED, 'Approved')
    ]

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    url = models.URLField(max_length=600)
    url_hash = models.CharField(max_length=7)
    date_first_found = models.DateField(null=True, blank=True)
    date_last_found = models.DateField(null=True, blank=True)
    start_year = models.PositiveSmallIntegerField(null=True, blank=True)
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    document_type = models.PositiveSmallIntegerField(choices=DOCUMENT_TYPE_CHOICES, null=True, blank=True)
    scope = models.PositiveSmallIntegerField(choices=SCOPE_CHOICES, null=True, blank=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, null=True, blank=True)
    well_presented = models.BooleanField(null=True, blank=True)
    baseline_analysis = models.BooleanField(null=True, blank=True)
    notes = models.CharField(max_length=800, blank=True)
    file_type = models.CharField(max_length=200)
    charset = models.CharField(max_length=50, blank=True)
    text = models.TextField(blank=True)
    file = models.FileField('plans')
