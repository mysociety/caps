import hashlib
import math
import os
import re
from copy import deepcopy
from itertools import groupby, chain
from pathlib import Path
from typing import Optional, Type, List, Callable, Union, Tuple
from collections import defaultdict

import dateutil.parser
import django_filters
import markdown
import pandas as pd
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models import Count, Max, Min, Q, Sum
from django.forms import Select
from django.utils.text import slugify
from simple_history.models import HistoricalRecords
from caps.filters import DefaultSecondarySortFilter


def query_lookup(
    query: models.QuerySet, key: str, value: str, default: Optional[str] = None
) -> dict:
    """
    convert a query to a lookup function with a default value
    """
    di = dict(query.values_list(key, value))
    return lambda x: di.get(x, default)


def save_df_to_model(model: Type[models.Model], df: pd.DataFrame):
    """
    Given a df with column names that match field names,
    create entries in database
    """
    ff = filter(lambda x: hasattr(x, "db_column"), model._meta.get_fields())
    field_names = [x.get_attname_column()[0] for x in ff]
    good_cols = [x for x in df.columns if x in field_names]
    records = df[good_cols].to_dict("records")
    items = [model(**kwargs) for kwargs in records]
    model.objects.bulk_create(items, batch_size=1000)


class CustomQuerySet(models.QuerySet):
    """
    Include some extra functions on querysets avaliable to models
    """

    def pipe(self, item: Callable):
        return item(self)

    def to_dataframe(
        self, *args: Union[str, Tuple[str, str]], **kwargs
    ) -> pd.DataFrame:
        """
        Args will be passed to queryset.values.
        A tuple can be passed to rename a field in the dataframe.
        e.g. ("field_in_other_model__name", "model_name")
        will return a model name
        """
        rename_map = {x[0]: x[1] for x in args if isinstance(x, tuple)}
        items = [x[0] if isinstance(x, tuple) else x for x in args]
        return (
            self.values(*items, **kwargs).pipe(pd.DataFrame).rename(columns=rename_map)
        )


class CapsModel(models.Model):
    objects = CustomQuerySet.as_manager()

    class Meta:
        abstract = True


class Council(models.Model):

    ENGLAND = 1
    SCOTLAND = 2
    WALES = 3
    NORTHERN_IRELAND = 4

    COUNTRY_CHOICES = [
        (ENGLAND, "England"),
        (SCOTLAND, "Scotland"),
        (WALES, "Wales"),
        (NORTHERN_IRELAND, "Northern Ireland"),
    ]

    AUTHORITY_TYPE_CHOICES = [
        ("CC", "City of London"),
        ("COMB", "Combined Authority"),
        ("CTY", "County Council"),
        ("LBO", "London Borough"),
        ("MD", "Metropolitan District"),
        ("NMD", "Non-Metropolitan District"),
        ("UA", "Unitary Authority"),
    ]

    SCORING_GROUP_CHOICES = [
        ("single", "Single Tier"),
        ("county", "County Council"),
        ("district", "District Council"),
        ("combined", "Combined Authority"),
        ("northern-ireland", "Northern Ireland Council"),
    ]

    SCORING_GROUPS = {
        "single": {
            "name": "Single tier",
            "slug": "single",
            "types": ["CC", "LBO", "MD", "UA"],
            "countries": [ENGLAND, SCOTLAND, WALES],
        },
        "county": {
            "name": "County",
            "slug": "county",
            "types": ["CTY"],
            "countries": [ENGLAND, SCOTLAND, WALES],
        },
        "district": {
            "name": "District",
            "slug": "district",
            "types": ["NMD"],
            "countries": [ENGLAND, SCOTLAND, WALES],
        },
        "combined": {
            "name": "Combined Authority",
            "slug": "combined",
            "types": ["COMB", "SRA"],
            "countries": [ENGLAND, SCOTLAND, WALES],
        },
        "northern-ireland": {
            "name": "Northern Ireland",
            "slug": "northern-ireland",
            "types": ["UA"],
            "countries": [NORTHERN_IRELAND],
        },
    }

    PLAN_FILTER_CHOICES = [
        (None, "All"),
        (True, "Yes"),
        (False, "No"),
    ]
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    country = models.PositiveSmallIntegerField(choices=COUNTRY_CHOICES)
    authority_code = models.CharField(max_length=4, unique=True)
    authority_type = models.CharField(
        max_length=4, choices=AUTHORITY_TYPE_CHOICES, blank=True
    )
    gss_code = models.CharField(max_length=9, blank=True, unique=True)
    whatdotheyknow_id = models.IntegerField(null=True, blank=True, unique=True)
    mapit_area_code = models.CharField(max_length=3, blank=True)
    website_url = models.URLField()
    combined_authority = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True
    )
    labels = models.ManyToManyField(
        "ComparisonLabel", through="ComparisonLabelAssignment", blank=True
    )
    related_authorities = models.ManyToManyField(
        "self",
        through="Distance",
        through_fields=("council_a", "council_b"),
        blank=True,
    )
    twitter_name = models.CharField(max_length=200, null=True)
    twitter_url = models.URLField(null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return "%s" % self.name

    def get_absolute_url(self):
        return "/councils/%s/" % self.slug

    def get_related_councils(self, cut_off: int = 10) -> List[dict]:
        """
        get all related councils
        """
        councils = self.related_authorities.filter(
            distances__position__lte=cut_off + 2
        ).annotate(
            num_plans=Count("plandocument"),
            has_promise=Count("promise"),
            earliest_promise=Min("promise__target_year"),
            declared_emergency=Min("emergencydeclaration__date_declared"),
        )

        council_lookup = {council.id: council for council in councils}
        council_ids = list(council_lookup.keys()) + [self.id]

        # get label assignments in a seperate query ready to assign
        comparison_qs = (
            ComparisonLabelAssignment.objects.filter(council_id__in=council_ids)
            .prefetch_related("label")
            .order_by("label__type_id")
        )

        # change list of labels to tiered lookup (type_id, council_id)
        labels = defaultdict(dict)
        for comparison in comparison_qs.all():
            labels[comparison.label.type_id][comparison.council_id] = comparison

        processed_councils = []
        for d in self.distances.all().order_by("type_id", "-match_score"):
            # deepcopy to make sure the same council in multiple comparison types
            # are seperate objects with seperate links to Distance objects
            nc = deepcopy(council_lookup[d.council_b_id])
            nc.distance = d
            nc.label = labels[d.type_id][nc.id]
            processed_councils.append(nc)

        types = ComparisonType.objects.all()
        types = {comparison_type.id: comparison_type for comparison_type in types}

        grouped_results = groupby(
            processed_councils, key=lambda council: council.distance.type_id
        )

        results = []
        # add details for the home council
        for type_id, g in grouped_results:
            results.append(
                {
                    "type": types[type_id],
                    "label": labels[type_id][self.id].label,
                    "councils": list(g)[:cut_off],
                }
            )

        return results

    def current_emissions_breakdown(self) -> pd.DataFrame:
        """
        Get emissions breakdown for current year by Emissions profile
        """

        totals = [
            "Industry Total",
            "Commercial Total",
            "Public Sector Total",
            "Transport Total",
            "Domestic Total",
        ]

        df = (
            DataPoint.objects.filter(
                council=self, data_type__name_in_source__in=totals, year=2019
            )
            .to_dataframe(("data_type__name_in_source", "emissions_type"), "value")
            .assign(percentage=lambda df: df["value"] / df["value"].sum())
            .sort_values("emissions_type")
        )

        df["emissions_type"] = df["emissions_type"].str.replace(" Total", "")
        df["percentage"] = df["percentage"].apply("{:.0%}".format)

        return df

    def get_scoring_group(self):
        if self.country == self.NORTHERN_IRELAND:
            group = "northern-ireland"
        elif self.authority_type in ("CC", "LBO", "MD", "UA"):
            group = "single"
        elif self.authority_type == "NMD":
            group = "district"
        elif self.authority_type == "CTY":
            group = "county"
        elif self.authority_type in ["COMB", "SRA"]:
            group = "combined"
        else:
            group = "single"

        return self.SCORING_GROUPS[group]

    @property
    def powers(self):
        powers = ["staff", "spending"]

        if (
            self.country != self.NORTHERN_IRELAND
            and self.authority_type != "COMB"
            and self.authority_type != "NMD"
        ):
            powers.append("transport-planning")

        if (
            self.country != self.NORTHERN_IRELAND
            and self.authority_type == "UA"
            or self.authority_type == "MD"
            or self.authority_type == "CTY"
        ):
            powers.append("passenger-transport")

        if self.country != self.NORTHERN_IRELAND and self.authority_type not in [
            "COMB",
            "SRA",
            "NMD",
        ]:
            powers.append("schools-libraries")

        if self.authority_type not in ["COMB", "SRA"] and self.authority_type != "CTY":
            powers.append("environmental-health")

        if self.authority_type not in ["COMB", "SRA"]:
            if self.authority_type != "CTY" and self.authority_type != "NMD":
                powers.append("waste-collection")
                powers.append("waste-disposal")
            elif self.authority_type == "CTY":
                powers.append("waste-disposal")
            elif self.authority_type == "NMD":
                powers.append("waste-collection")

        if (
            self.country != self.NORTHERN_IRELAND
            and self.authority_type not in ["COMB", "SRA"]
            and self.authority_type != "CTY"
        ):
            powers.append("social-housing")

        if self.authority_type != "COMB" and self.authority_type != "CTY":
            powers.append("planning-building")

        return powers

    @property
    def is_upper_tier(self):
        return self.authority_type == "CTY" or self.authority_type == "COMB"

    @property
    def foe_slug(self):
        if self.country not in (self.ENGLAND, self.WALES) or self.is_upper_tier:
            return ""

        slug = self.name.lower()

        if slug == "city of london":
            slug = "city-london"
        elif slug == "st albans city and district council":
            slug = "st-albans"
        elif slug == "barrow-in-furness borough council":
            slug = "barrow-furness"
        else:
            slug = (
                re.sub(
                    r"([^a-z&\- ]| of|london borough of|royal borough of|metropolitan borough|borough|city of|city|council|district|county|unitary|\(unitary\))",
                    "",
                    slug,
                )
                .strip()
                .replace("&", "and")
                .replace(" ", "-")
            )

        return slug

    @classmethod
    def country_description(cls, country_code):
        codes_to_descriptions = dict(
            (code, country) for code, country in Council.COUNTRY_CHOICES
        )
        return codes_to_descriptions.get(int(country_code))

    @classmethod
    def country_code(cls, country_entry):
        """
        Return a country code given a text description, or None if the description
        isn't in the country choices
        """
        if pd.isnull(country_entry):
            return None
        descriptions_to_codes = dict(
            (country.lower(), code) for code, country in Council.COUNTRY_CHOICES
        )
        return descriptions_to_codes.get(country_entry.lower().strip())

    @classmethod
    def authority_type_code(cls, authority_type):
        """
        Return an authority type code given a text description, or None if the description
        isn't in the authority type choices
        """
        if pd.isnull(authority_type):
            return None
        descriptions_to_codes = dict(
            (type.lower(), code) for code, type in Council.AUTHORITY_TYPE_CHOICES
        )
        return descriptions_to_codes.get(authority_type.lower().strip())

    @classmethod
    def percent_with_plan(cls):
        """
        Return the percentage of councils that have a plan document
        """
        with_plan = (
            cls.objects.annotate(num_plans=Count("plandocument"))
            .filter(num_plans__gt=0)
            .count()
        )
        total = cls.objects.all().count()
        return round(with_plan / total * 100)


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
        (ACTION_PLAN, "Action plan"),
        (CLIMATE_STRATEGY, "Climate strategy"),
        (SUMMARY_DOCUMENT, "Summary document"),
        (PRE_PLAN, "Pre-plan"),
        (MEETING_MINUTES, "Meeting minutes"),
    ]

    COUNCIL_ONLY = 1
    WHOLE_AREA = 2
    SCOPE_CHOICES = [
        (COUNCIL_ONLY, "Council only"),
        (WHOLE_AREA, "Whole area"),
    ]

    DRAFT = 1
    APPROVED = 2

    STATUS_CHOICES = [(DRAFT, "Draft"), (APPROVED, "Approved")]

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    url = models.URLField(max_length=600)
    url_hash = models.CharField(max_length=7)
    date_first_found = models.DateField(null=True, blank=True)
    date_last_found = models.DateField(null=True, blank=True)
    start_year = models.PositiveSmallIntegerField(null=True, blank=True)
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    document_type = models.PositiveSmallIntegerField(
        choices=DOCUMENT_TYPE_CHOICES, null=True, blank=True
    )
    scope = models.PositiveSmallIntegerField(
        choices=SCOPE_CHOICES, null=True, blank=True
    )
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, null=True, blank=True
    )
    well_presented = models.BooleanField(null=True, blank=True)
    baseline_analysis = models.BooleanField(null=True, blank=True)
    notes = models.CharField(max_length=800, blank=True)
    file_type = models.CharField(max_length=200)
    charset = models.CharField(max_length=50, blank=True)
    text = models.TextField(blank=True)
    file = models.FileField("plans", storage=overwrite_storage)
    history = HistoricalRecords()
    title = models.CharField(max_length=800, blank=True)

    @property
    def get_document_type(self):
        for choice in self.DOCUMENT_TYPE_CHOICES:
            if choice[0] == self.document_type:
                return choice[1].lower()
        return "document"

    @property
    def get_scope(self):
        for choice in self.SCOPE_CHOICES:
            if choice[0] == self.scope:
                return choice[1].lower()
        return ""

    @property
    def get_status(self):
        for choice in self.STATUS_CHOICES:
            if choice[0] == self.status:
                return choice[1].lower()
        return ""

    @property
    def link(self):
        """
        PDFs are the only filetype we can display well locally so link out to
        the source document for other file types
        """
        if self.file_type == "pdf":
            return self.file.url
        else:
            return self.url

    @classmethod
    def make_url_hash(cls, url):
        """
        Generate a 7 character hash of the url passed
        """
        return hashlib.md5(url.encode("utf-8")).hexdigest()[:7]

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
        match = re.match(
            r"(?P<start_year>20\d\d)-(?P<end_year>20\d\d)", time_period.lstrip()
        )
        if match:
            return (int(match.group("start_year")), int(match.group("end_year")))
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
        descriptions_to_codes = dict(
            (doc_type.lower(), code)
            for code, doc_type in PlanDocument.DOCUMENT_TYPE_CHOICES
        )
        return descriptions_to_codes.get(document_type_entry.lower().strip())

    @classmethod
    def scope_code(cls, scope_entry):
        """
        Return a scope code given a text description, or None if the description
        isn't in the scope choices
        """
        if pd.isnull(scope_entry):
            return None
        descriptions_to_codes = dict(
            (scope.lower(), code) for code, scope in PlanDocument.SCOPE_CHOICES
        )
        return descriptions_to_codes.get(scope_entry.lower().strip())

    @classmethod
    def status_code(cls, status_entry):
        """
        Return a status code given a text description, or None if the description
        isn't in the status choices
        """
        if pd.isnull(status_entry):
            return None
        descriptions_to_codes = dict(
            (status.lower(), code) for code, status in PlanDocument.STATUS_CHOICES
        )
        return descriptions_to_codes.get(status_entry.lower().strip())

    @classmethod
    def date_from_text(cls, date_entry):
        """
        Return a date object given a text date, or none if there is no parsable
        date. This will strip any time information from the parsed date.
        """
        if pd.isnull(date_entry):
            return None
        return dateutil.parser.parse(date_entry, dayfirst=True).date()

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
            return ""
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
        descriptions_to_booleans = {"y": True, "n": False, "yes": True, "no": False}
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


class DataPoint(CapsModel):

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    year = models.PositiveSmallIntegerField()
    value = models.FloatField()
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    data_type = models.ForeignKey(DataType, on_delete=models.CASCADE)

    class Meta:
        ordering = ["data_type", "year"]


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

        return (
            qs.values("user_query")
            .filter(result_count__gt=0)
            .annotate(
                most_recent=models.Max("created"), times_seen=models.Count("user_query")
            )
            .order_by("-most_recent", "user_query")
            .filter(times_seen__gte=threshold)
        )

    def most_popular(self, search_key=None, threshold=1):
        qs = self.get_queryset()

        if search_key is not None:
            qs = qs.filter(search_key=search_key)

        initial_list = (
            qs.values("user_query")
            .filter(result_count__gt=0)
            .order_by()
            .annotate(times_seen=models.Count("user_query"))
            .order_by("-times_seen", "user_query")
            .filter(times_seen__gte=threshold)
        )
        return initial_list.values("user_query", "times_seen")


class SavedSearch(models.Model):
    search_key = models.SlugField(
        max_length=100,
        help_text="A way to arbitrarily group queries. Should be a single word. Example: all-products",
    )
    user_query = models.CharField(
        max_length=1000, help_text="The text the user searched on. Useful for display."
    )
    full_query = models.CharField(
        max_length=1000,
        default="",
        blank=True,
        help_text="The full query Haystack generated. Useful for searching again.",
    )
    result_count = models.PositiveIntegerField(default=0, blank=True)
    inorganic = models.BooleanField(default=False)
    created = models.DateTimeField(blank=True, auto_now_add=True)
    council_restriction = models.CharField(
        max_length=1000, help_text="The text used to restrict by council", default=""
    )

    objects = SavedSearchManager()

    class Meta:
        verbose_name_plural = "Saved Searches"

    def __unicode__(self):
        return "'%s...%s" % (self.user_query[:50], self.search_key)


class Promise(models.Model):

    PROMISE_FILTER_CHOICES = [
        (2025, "2025"),
        (2030, "2030"),
        (2035, "2035"),
        (2040, "2040"),
        (2045, "2045"),
        (2050, "2050"),
        ("no_target", "No target"),
        ("unknown", "Unknown"),
    ]

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    has_promise = models.BooleanField(blank=True, null=True)
    target_year = models.IntegerField(blank=True, null=True)
    scope = models.PositiveSmallIntegerField(
        choices=PlanDocument.SCOPE_CHOICES, null=True, blank=True
    )
    text = models.TextField(blank=True)
    source = models.URLField(max_length=600)
    source_name = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=800, blank=True, null=True)
    history = HistoricalRecords()

    @property
    def get_scope(self):
        for choice in PlanDocument.SCOPE_CHOICES:
            if choice[0] == self.scope:
                return choice[1].lower()
        return ""


class EmergencyDeclaration(models.Model):
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    date_declared = models.DateField(null=True, blank=True)
    source_url = models.URLField(max_length=600)
    council = models.ForeignKey(Council, on_delete=models.CASCADE)


class CouncilFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    has_plan = django_filters.BooleanFilter(
        field_name="plandocument",
        lookup_expr="isnull",
        exclude=True,
        label="Has plan",
        widget=Select(choices=Council.PLAN_FILTER_CHOICES),
    )
    authority_type = django_filters.ChoiceFilter(
        choices=Council.AUTHORITY_TYPE_CHOICES, empty_label="All"
    )
    country = django_filters.ChoiceFilter(
        choices=Council.COUNTRY_CHOICES, empty_label="All"
    )

    promise_combined = django_filters.ChoiceFilter(
        method="filter_promise",
        label="Carbon neutral by",
        empty_label="All",
        choices=Promise.PROMISE_FILTER_CHOICES,
    )

    declared_emergency = django_filters.BooleanFilter(
        field_name="emergencydeclaration",
        lookup_expr="isnull",
        label="Declared emergency",
        exclude=True,
        widget=Select(choices=Council.PLAN_FILTER_CHOICES),
    )

    sort = DefaultSecondarySortFilter(
        secondary="name",
        label="Sort by",
        empty_label=None,
        fields=(
            ("name", "name"),
            ("promise__target_year", "promise_year"),
            ("emergencydeclaration__date_declared", "declaration_date"),
            ("plandocument__updated_at", "last_update"),
        ),
        field_labels={
            "name": "Council name",
            "promise__target_year": "Carbon neutral target",
            "emergencydeclaration__date_declared": "Declaration date",
            "last_update": "Last update",
        },
    )

    def filter_promise(self, queryset, name, value):
        if value is None:
            return queryset
        elif value == "unknown":
            return queryset.filter(**{"has_promise": 0})
        elif value == "no_target":
            return queryset.filter(**{"has_promise__gte": 1, "earliest_promise": None})
        else:
            return queryset.filter(**{"earliest_promise__lte": value})

    class Meta:
        model = Council
        fields = []


class ComparisonType(models.Model):
    """
    Type of comparison (emissions, distance)
    """

    slug = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    desc = models.TextField(default="")

    TYPES = {
        "composite": "Overall",
        "emissions": "Emissions",
        "geographic_distance": "Nearby",
        "imd": "IMD",
        "ruc": "Rural/Urban",
    }

    def __str__(self):
        return self.name

    def markdown_desc(self):
        return markdown.markdown(self.desc)

    @classmethod
    def populate(cls):
        """
        Create general types
        """
        to_create = []
        for slug, name in cls.TYPES.items():
            c = cls(name=name, slug=slug)
            c.get_desc()
            to_create.append(c)

        cls.objects.all().delete()
        cls.objects.bulk_create(to_create)

    def get_desc(self):
        """
        read in markdown description
        """
        file_path = Path("data", "comparisons", self.slug, "description.md")
        with open(file_path, "r") as f:
            self.desc = f.read()
        return self

    @classmethod
    def combine_files(cls, filename: str):
        """
        combine the same file from different types into a
        single dataframe, with a `type_slug` column.
        """

        dfs = []
        for slug in cls.TYPES.keys():
            file_path = Path("data", "comparisons", slug, filename)
            df = pd.read_csv(file_path)
            df["type_slug"] = slug
            dfs.append(df)

        return pd.concat(dfs)


class ComparisonLabel(models.Model):
    """
    Group in comparison type ("low emissions", "high imd")
    """

    slug = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    desc = models.TextField(default="")
    type = models.ForeignKey(ComparisonType, on_delete=models.CASCADE)

    @classmethod
    def populate(cls):
        df = ComparisonType.combine_files("label_desc.csv")
        slug_to_id = query_lookup(ComparisonType.objects.all(), "slug", "id")
        df["slug"] = df["label"].apply(slugify)
        df["type_id"] = df["type_slug"].apply(slug_to_id)
        df = df.rename(columns={"label": "name"})
        cls.objects.all().delete()
        save_df_to_model(cls, df)

    def markdown_desc(self):
        return markdown.markdown(self.desc)


class ComparisonLabelAssignment(models.Model):
    """
    Relation of label to council
    """

    label = models.ForeignKey(
        ComparisonLabel, on_delete=models.CASCADE, related_name="assignments"
    )
    council = models.ForeignKey(Council, on_delete=models.CASCADE)

    @classmethod
    def populate(cls):
        df = ComparisonType.combine_files("la_labels.csv")
        slug_to_id = query_lookup(ComparisonType.objects.all(), "slug", "id")
        code_to_id = query_lookup(Council.objects.all(), "authority_code", "id")
        df["council_id"] = df["local-authority-code"].apply(code_to_id)
        df["type_id"] = df["type_slug"].apply(slug_to_id)

        # remove councils not in cape
        df = df[~df["council_id"].isnull()]

        # possibility of duplicate label names in different types
        # need to join on both the type and label name to get the id
        q = ComparisonLabel.objects.all().values("id", "name", "type_id")
        label_df = pd.DataFrame(q).rename(columns={"name": "label", "id": "label_id"})
        df = df.merge(label_df, on=["type_id", "label"], how="left")
        cls.objects.all().delete()
        save_df_to_model(cls, df)


class Distance(models.Model):
    """
    match score between two councils
    """

    council_a = models.ForeignKey(
        Council, on_delete=models.CASCADE, related_name="distances"
    )
    council_b = models.ForeignKey(
        Council, on_delete=models.CASCADE, related_name="reverse_distance"
    )
    type = models.ForeignKey(ComparisonType, on_delete=models.CASCADE)
    distance = models.FloatField()
    match_score = models.FloatField()
    position = models.IntegerField()

    @classmethod
    def populate(cls):
        df = ComparisonType.combine_files("distance_map.csv")

        # will never access almost all distances, only save the top 30
        df = df[lambda x: x["position"] <= 31]

        slug_to_id = query_lookup(ComparisonType.objects.all(), "slug", "id")
        code_to_id = query_lookup(Council.objects.all(), "authority_code", "id")
        df["type_id"] = df["type_slug"].apply(slug_to_id)
        df["council_a_id"] = df["local-authority-code_A"].apply(code_to_id)
        df["council_b_id"] = df["local-authority-code_B"].apply(code_to_id)
        df = df.rename(columns={"match": "match_score"})

        # need some handling for if a council is not in the caps database
        # this requires both id columns to have a value
        has_both = ~(df["council_a_id"].isnull() | df["council_b_id"].isnull())
        df = df[has_both]
        cls.objects.all().delete()
        save_df_to_model(cls, df)


class Tag(models.Model):
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=200, unique=True)
    description_singular = models.TextField()
    description_plural = models.TextField()
    colour = models.CharField(max_length=50)
    image_url = models.URLField(blank=True)


class CouncilTag(models.Model):
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
