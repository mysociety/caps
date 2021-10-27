# -*- coding: future_fstrings -*-
import os
import hashlib
import re
import math
import dateutil.parser

import pandas as pd

from django.db import models
from django.utils.text import slugify
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.forms import Select
from django.db.models import Count

import django_filters

class Council(models.Model):

    ENGLAND = 1
    SCOTLAND = 2
    WALES = 3
    NORTHERN_IRELAND = 4

    COUNTRY_CHOICES = [
        (ENGLAND, 'England'),
        (SCOTLAND, 'Scotland'),
        (WALES, 'Wales'),
        (NORTHERN_IRELAND, 'Northern Ireland')
    ]

    AUTHORITY_TYPE_CHOICES = [
        ('CC', 'City of London'),
        ('COMB', 'Combined Authority'),
        ('CTY', 'County Council'),
        ('LBO', 'London Borough'),
        ('MD', 'Metropolitan District'),
        ('NMD', 'Non-Metropolitan District'),
        ('UA', 'Unitary Authority')
    ]

    PLAN_FILTER_CHOICES = [
        (None, 'All'),
        (True, 'Yes'),
        (False, 'No'),
    ]
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    country = models.PositiveSmallIntegerField(choices=COUNTRY_CHOICES)
    authority_code = models.CharField(max_length=4, unique=True)
    authority_type = models.CharField(max_length=4, choices=AUTHORITY_TYPE_CHOICES, blank=True)
    gss_code = models.CharField(max_length=9, blank=True, unique=True)
    whatdotheyknow_id = models.IntegerField(null=True, blank=True, unique=True)
    mapit_area_code = models.CharField(max_length=3, blank=True)
    website_url = models.URLField()
    combined_authority = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    related_councils = models.ManyToManyField("self", blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return u"%s" % self.name

    def get_absolute_url(self):
        return "/councils/%s/" % self.slug

    @property
    def powers(self):
        powers = ['staff', 'spending']

        if self.country != self.NORTHERN_IRELAND and self.authority_type != 'COMB' and self.authority_type != 'NMD':
            powers.append('transport-planning')

        if self.country != self.NORTHERN_IRELAND and self.authority_type == 'UA' or self.authority_type == 'MD' or self.authority_type == 'CTY':
            powers.append('passenger-transport')

        if self.country != self.NORTHERN_IRELAND and self.authority_type != 'COMB' and self.authority_type != 'NMD':
            powers.append('schools-libraries')

        if self.authority_type != 'COMB' and self.authority_type != 'CTY':
            powers.append('environmental-health')

        if self.authority_type != 'COMB':
                if self.authority_type != 'CTY' and self.authority_type != 'NMD':
                    powers.append('waste-collection')
                    powers.append('waste-disposal')
                elif self.authority_type == 'CTY':
                    powers.append('waste-disposal')
                elif self.authority_type == 'NMD':
                    powers.append('waste-collection')

        if self.country != self.NORTHERN_IRELAND and self.authority_type != 'COMB' and self.authority_type != 'CTY':
            powers.append('social-housing')

        if self.authority_type != 'COMB' and self.authority_type != 'CTY':
            powers.append('planning-building')

        return powers

    @classmethod
    def country_code(cls, country_entry):
        """
        Return a country code given a text description, or None if the description
        isn't in the country choices
        """
        if pd.isnull(country_entry):
            return None
        descriptions_to_codes = dict((country.lower(), code) for code, country in Council.COUNTRY_CHOICES)
        return descriptions_to_codes.get(country_entry.lower().strip())

    @classmethod
    def percent_with_plan(cls):
        """
        Return the percentage of councils that have a plan document
        """
        with_plan = cls.objects.annotate(num_plans=Count('plandocument')).filter(num_plans__gt=0).count()
        total = cls.objects.all().count()
        return(round(with_plan / total * 100))

class CouncilFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    has_plan = django_filters.BooleanFilter(field_name='plandocument',
                                            lookup_expr='isnull',
                                            exclude=True,
                                            label='Has plan',
                                            widget=Select(choices=Council.PLAN_FILTER_CHOICES))
    authority_type = django_filters.ChoiceFilter(choices=Council.AUTHORITY_TYPE_CHOICES,
                                                empty_label='All')
    country = django_filters.ChoiceFilter(choices=Council.COUNTRY_CHOICES,
                                          empty_label='All')

    class Meta:
        model = Council
        fields = []

class OverwriteStorage(FileSystemStorage):
    """
    Overwrite an existing file at the name given
    """
    def get_available_name(self, name, max_length):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name

overwrite_storage = OverwriteStorage()

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
    file = models.FileField('plans', storage=overwrite_storage)

    @property
    def get_document_type(self):
        for choice in self.DOCUMENT_TYPE_CHOICES:
            if choice[0] == self.document_type:
                return choice[1].lower()
        return 'document'

    @property
    def get_scope(self):
        for choice in self.SCOPE_CHOICES:
            if choice[0] == self.scope:
                return choice[1].lower()
        return ''

    @property
    def get_status(self):
        for choice in self.STATUS_CHOICES:
            if choice[0] == self.status:
                return choice[1].lower()
        return ''

    @property
    def link(self):
        """
        PDFs are the only filetype we can display well locally so link out to
        the source document for other file types
        """
        if self.file_type == 'pdf':
            return self.file.url
        else:
            return self.url

    @classmethod
    def make_url_hash(cls, url):
        """
        Generate a 7 character hash of the url passed
        """
        return hashlib.md5(url.encode('utf-8')).hexdigest()[:7]

    @classmethod
    def council_slug(cls, council_name):
        return slugify(council_name, allow_unicode=True)

    @classmethod
    def plan_filename(cls, council_name, url):
        return f"{cls.council_slug(council_name)}-{cls.make_url_hash(url)}"

    @classmethod
    def start_and_end_year_from_time_period(cls, time_period):
        """
        Return a start and end year from a time period. Returns (None, None) if
        the time period is not in the form DDDD-DDDD
        """
        if pd.isnull(time_period):
            return (None, None)
        match = re.match(r'(?P<start_year>20\d\d)-(?P<end_year>20\d\d)', time_period.lstrip())
        if match:
            return (int(match.group('start_year')), int(match.group('end_year')))
        else:
            return (None, None)

    @classmethod
    def document_type_code(cls, document_type_entry):
        """
        Return a document type code given a text description, or None if the
        description isn't in the document_type choices
        """
        if pd.isnull(document_type_entry):
            return None
        descriptions_to_codes = dict((doc_type.lower(), code) for code, doc_type in PlanDocument.DOCUMENT_TYPE_CHOICES)
        return descriptions_to_codes.get(document_type_entry.lower().strip())

    @classmethod
    def scope_code(cls, scope_entry):
        """
        Return a scope code given a text description, or None if the description
        isn't in the scope choices
        """
        if pd.isnull(scope_entry):
            return None
        descriptions_to_codes = dict((scope.lower(), code) for code, scope in PlanDocument.SCOPE_CHOICES)
        return descriptions_to_codes.get(scope_entry.lower().strip())

    @classmethod
    def status_code(cls, status_entry):
        """
        Return a status code given a text description, or None if the description
        isn't in the status choices
        """
        if pd.isnull(status_entry):
            return None
        descriptions_to_codes = dict((status.lower(), code) for code, status in PlanDocument.STATUS_CHOICES)
        return descriptions_to_codes.get(status_entry.lower().strip())

    @classmethod
    def date_from_text(cls, date_entry):
        """
        Return a date object given a text date, or none if there is no parsable
        date. This will strip any time information from the parsed date.
        """
        if pd.isnull(date_entry):
            return None
        return dateutil.parser.parse(date_entry).date()

    @classmethod
    def integer_from_text(cls, entry):
        """
        Return a value from a pandas data field is it's not null
        """
        if pd.isnull(entry):
            return None
        else:
            return entry

    @classmethod
    def char_from_text(cls, entry):
        """
        Return a value from a pandas data field is it's not null
        """
        if pd.isnull(entry):
            return ''
        else:
            return entry

    @classmethod
    def boolean_from_text(cls, entry):
        """
        Return a boolean value given a text description, or None if the
        description isn't a coercible entry
        """
        if pd.isnull(entry):
            return None
        descriptions_to_booleans = { 'y': True,
                                     'n': False,
                                     'yes': True,
                                     'no': False }
        return descriptions_to_booleans.get(entry.strip().lower())

class DataType(models.Model):

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    name = models.CharField(max_length=100)
    source_url = models.URLField(max_length=600)
    name_in_source = models.CharField(max_length=100)
    unit = models.CharField(max_length=10)

    def __str__(self):
        return self.name

class DataPoint(models.Model):

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    year = models.PositiveSmallIntegerField()
    value = models.FloatField()
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    data_type = models.ForeignKey(DataType, on_delete=models.CASCADE)

    class Meta:
        ordering = ['data_type', 'year']

"""
Following adapted from https://github.com/django-haystack/saved_searches/

Both of these limit results to those returning a result partly as a way to
avoid abuse and also because it's unclear what the point of displaying results
that return no results are
"""
class SavedSearchManager(models.Manager):
    def most_recent(self, search_key=None, threshold=1):
        qs = self.get_queryset()

        if search_key is not None:
            qs = qs.filter(search_key=search_key)

        return qs.values('user_query').filter(result_count__gt=0).annotate(most_recent=models.Max('created'),times_seen=models.Count('user_query')).order_by('-most_recent', 'user_query').filter(times_seen__gte=threshold)

    def most_popular(self, search_key=None, threshold=1):
        qs = self.get_queryset()

        if search_key is not None:
            qs = qs.filter(search_key=search_key)

        initial_list = qs.values('user_query').filter(result_count__gt=0).order_by().annotate(times_seen=models.Count('user_query')).order_by('-times_seen', 'user_query').filter(times_seen__gte=threshold)
        return initial_list.values('user_query', 'times_seen')


class SavedSearch(models.Model):
    search_key = models.SlugField(max_length=100, help_text="A way to arbitrarily group queries. Should be a single word. Example: all-products")
    user_query = models.CharField(max_length=1000, help_text="The text the user searched on. Useful for display.")
    full_query = models.CharField(max_length=1000, default='', blank=True, help_text="The full query Haystack generated. Useful for searching again.")
    result_count = models.PositiveIntegerField(default=0, blank=True)
    inorganic = models.BooleanField(default=False)
    created = models.DateTimeField(blank=True, auto_now_add=True)

    objects = SavedSearchManager()

    class Meta:
        verbose_name_plural = 'Saved Searches'

    def __unicode__(self):
        return u"'%s...%s" % (self.user_query[:50], self.search_key)

class Promise(models.Model):

    PROMISE_FILTER_CHOICES = [
        (None, 'All'),
        (2025, '2025'),
        (2030, '2030'),
        (2035, '2035'),
        (2040, '2040'),
        (2045, '2045'),
        (2050, '2050'),
    ]

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    has_promise = models.BooleanField(blank=True, null=True)
    target_year = models.IntegerField(blank=True, null=True)
    scope = models.PositiveSmallIntegerField(choices=PlanDocument.SCOPE_CHOICES, null=True, blank=True)
    text = models.TextField(blank=True)
    source = models.URLField(max_length=600)
    source_name = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=800, blank=True, null=True)

