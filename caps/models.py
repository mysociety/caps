from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import defaultdict
from copy import deepcopy
from datetime import date
from itertools import chain, groupby
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional, Tuple, Type, TypeVar, Union

import dateutil.parser
import django_filters
import markdown
import pandas as pd
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models import (
    Count,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Sum,
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import Length
from django.forms import Select, TextInput
from django.utils.http import urlencode
from django.utils.text import slugify
from simple_history.models import HistoricalRecords
from tqdm import tqdm

from caps.filters import DefaultSecondarySortFilter

# Allow length looking for CharFields
models.CharField.register_lookup(Length)


def query_lookup(
    query: models.QuerySet, key: str, value: str, default: Optional[str] = None
) -> dict:
    """
    convert a query to a lookup function with a default value
    """
    di = dict(query.values_list(key, value))
    return lambda x: di.get(x, default)


def save_df_to_model(
    model: Type[models.Model],
    df: pd.DataFrame,
    batch_size: int = 1000,
    quiet: bool = False,
):
    """
    Given a df with column names that match field names,
    create entries in database
    """
    ff = filter(lambda x: hasattr(x, "db_column"), model._meta.get_fields())
    field_names = [x.get_attname_column()[0] for x in ff]
    good_cols = [x for x in df.columns if x in field_names]

    # iterate through subsets of df of batch_size
    max_sets = math.ceil(len(df) / batch_size)
    for i in tqdm(range(max_sets), disable=quiet):
        start = i * batch_size
        end = (i + 1) * batch_size
        records = df[good_cols].iloc[start:end].to_dict("records")
        items = [model(**kwargs) for kwargs in records]
        model.objects.bulk_create(items)


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
        ("NID", "Northern Irish Council"),
    ]

    REGION_CHOICES = [
        ("East Midlands", "East Midlands"),
        ("East of England", "East of England"),
        ("London", "London"),
        ("North East", "North East"),
        ("North West", "North West"),
        ("Northern Ireland", "Northern Ireland"),
        ("Scotland", "Scotland"),
        ("South East", "South East"),
        ("South West", "South West"),
        ("Wales", "Wales"),
        ("West Midlands", "West Midlands"),
        ("Yorkshire and The Humber", "Yorkshire and The Humber"),
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
            "types": ["NID"],
            "countries": [NORTHERN_IRELAND],
        },
    }

    PLAN_FILTER_CHOICES = [
        (None, "All"),
        (True, "Yes"),
        (False, "No"),
    ]

    PLAN_GEOGRAPHY_CHOICES = [
        ("urban", "Urban"),
        ("rural", "Rural"),
        ("urban-rural-areas", "Urban with rural areas"),
        ("sparse-rural", "Sparse and rural"),
    ]

    POPULATION_FILTER_CHOICES = [
        ("0k", "0k - 100k"),
        ("100k", "100k - 250k"),
        ("250k", "250k - 500k"),
        ("500k", "500k - 750k"),
        ("750k", "750k - 1m"),
        ("1m", "1m+"),
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
    region = models.CharField(max_length=200, null=True, choices=REGION_CHOICES)
    county = models.CharField(max_length=200, null=True)
    population = models.IntegerField(default=0)
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    replaced_by = models.CharField(
        max_length=200, null=True
    )  # pipe seperated list of authority codes

    class Meta:
        ordering = ["name"]

    def __lt__(self, other):
        return self.id < other.id

    def __str__(self):
        return "%s" % self.name

    @classmethod
    def current_councils(self):
        """
        Get all councils that are currently active
        """
        q = Council.objects.filter(
            Q(end_date__isnull=True) | Q(end_date__gt=settings.COUNCILS_AS_OF_DATE)
        )
        return q

    def is_non_english(self):
        return self.country != self.ENGLAND

    def nice_country(self):
        return Council.country_description(self.country)

    def get_predecessors(self):
        """
        Get councils that have been replaced by this council
        """
        return Council.objects.filter(replaced_by__contains=self.authority_code)

    def get_successors(self):
        """
        Get councils that have replaced this council
        """
        return Council.objects.filter(authority_code__in=self.replaced_by.split("|"))

    def is_current(self) -> bool:
        """
        Is this a currently relevant council
        """
        current_cohort = settings.COUNCILS_AS_OF_DATE
        return self.end_date is None or self.end_date >= current_cohort

    def is_new_council(self) -> bool:
        """
        Is this a recently added council that should have special messages?
        """
        if self.start_date is None:
            return False
        return self.start_date >= settings.RECENTLY_ADDED_COUNCILS

    def is_old_council(self) -> bool:
        """
        Is this an old council?
        """
        not_current_council = self.is_current() is False
        has_replacement = self.replaced_by is not None
        return not_current_council and has_replacement

    def get_absolute_url(self):
        return "/councils/%s/" % self.slug

    @property
    def climate_emergency_declaration(self):
        return EmergencyDeclaration.objects.filter(council=self).first()

    @property
    def net_zero_targets(self):
        return Promise.objects.filter(council=self, has_promise=True)

    @property
    def net_zero_target_council_operations(self):
        return Promise.objects.filter(
            council=self, has_promise=True, scope=PlanDocument.COUNCIL_ONLY
        ).first()

    @property
    def net_zero_target_whole_area(self):
        return Promise.objects.filter(
            council=self, has_promise=True, scope=PlanDocument.WHOLE_AREA
        ).first()

    @property
    def last_updated_plan(self):
        return PlanDocument.objects.filter(council=self).order_by("updated_at").first()

    def keyphrase_intersection(self, other: Council) -> KeyPhraseOverlap:
        """
        Return a the unique keywords and intersections of keywords
        between two councils
        """

        joined_docs = PlanDocument.objects.filter(
            council_id__in=[self.id, other.id]
        )  # in principle, add any limiters on document type here

        return PlanDocument.keyphrase_overlap(
            docs=joined_docs,
            sort_func=lambda doc: doc.council,
            is_main=self,
        )

    def related_council_keyphrase_intersection(
        self, cut_off: int = 10
    ) -> dict[Council, KeyPhraseOverlap]:
        """
        Get the keyphrase intersection between this council and all related councils
        """
        councils = self.related_authorities.filter(distances__position__lte=cut_off + 2)

        joined_docs = PlanDocument.objects.filter(
            Q(council__in=councils) | Q(council=self)
        ).prefetch_related("council")

        return PlanDocument.keyphrase_overlap(
            docs=joined_docs,
            sort_func=lambda doc: doc.council,
            is_main=self,
        )

    def get_emissions_cluster(self):
        """
        Get the emissions cluster for this council
        """
        return ComparisonLabel.objects.get(
            assignments__council=self, type__slug="emissions"
        )

    def get_related_councils(self, cut_off: int = 10) -> List[dict]:
        """
        get all related councils
        """
        councils = self.related_authorities.filter(
            distances__position__lte=cut_off + 2
        ).annotate(
            num_plans=Subquery(
                PlanDocument.objects.filter(
                    council_id=OuterRef("id"), document_type=PlanDocument.ACTION_PLAN
                )
                .values("council_id")
                .annotate(num_plans=Count("id"))
                .values("num_plans")
            ),
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

    def data_points(self, data_group: str):
        """
        Get all data points for a given data group
        """
        data_types = DataType.objects.filter(collection=data_group)
        return DataPoint.objects.filter(
            council=self, data_type__in=data_types
        ).prefetch_related("data_type")

    def current_emissions_breakdown(self, year: int) -> pd.DataFrame:
        """
        Get emissions breakdown for current year by Emissions profile
        """

        totals = [
            "Industry Total",
            "Commercial Total",
            "Public Sector Total",
            "Transport Total",
            "Domestic Total",
            "Agriculture Total",
        ]

        df = (
            DataPoint.objects.filter(
                council=self, data_type__name_in_source__in=totals, year=year
            )
            .prefetch_related("data_type")
            .to_dataframe(("data_type__name_in_source", "emissions_type"), "value")
            .assign(percentage=lambda df: df["value"] / df["value"].sum())
            .sort_values("percentage", ascending=False)
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
    def short_name(self):
        patterns = [
            r"[^a-zA-Z]+unitary[^a-zA-Z]*$",  # " - Unitary" and " (Unitary)" suffixes
            r"\s+(metropolitan\s+)?((borough|city and district|city|county|district)\s+)?council$",
            r"^(london|royal) borough of\s+",
            r"\s+(mayoral\s+)?(combined\s+)?authority$",
        ]

        n = self.name
        for pattern in patterns:
            n = re.sub(pattern, "", n, flags=re.IGNORECASE)

        return n

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

    @property
    def feedback_form_url(self):
        return "{}?{}".format(
            settings.FEEDBACK_FORM,
            urlencode({"usp": "pp_url", "entry.393810903": self.name}),
        )

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
            cls.current_councils()
            .annotate(num_plans=Count("plandocument"))
            .filter(
                Q(plandocument__document_type=PlanDocument.ACTION_PLAN)
                | Q(plandocument__document_type=PlanDocument.CLIMATE_STRATEGY),
                num_plans__gt=0,
            )
            .count()
        )
        total = cls.current_councils().count()
        return round(with_plan / total * 100)

    @classmethod
    def get_county_choices(cls):
        choices = cls.objects.filter(authority_type="CTY").values_list(
            "authority_code", "name"
        )

        choices = [
            (code, name.replace(" County Council", "")) for (code, name) in choices
        ]

        return choices

    @classmethod
    def region_filter_choices(cls):
        countries = cls.COUNTRY_CHOICES
        regions = [
            r for r in cls.REGION_CHOICES if r[0] not in dict(countries).values()
        ]

        counties = [c for c in cls.get_county_choices()]

        return (
            ("Countries", (countries)),
            ("Regions of England", (regions)),
            ("English Counties", (counties)),
        )


class OverwriteStorage(FileSystemStorage):
    """
    Overwrite an existing file at the name given
    """

    def get_available_name(self, name, max_length):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name


overwrite_storage = OverwriteStorage()


class PlanDocumentHistoricalModel(models.Model):
    is_deleted = False

    @property
    def get_document_type(self):
        for choice in PlanDocument.DOCUMENT_TYPE_CHOICES:
            if choice[0] == self.document_type:
                return choice[1].lower()
        return "document"

    class Meta:
        abstract = True


class KeyPhraseOverlap(NamedTuple):
    """
    Structured tuple to return from key_phrase_intersection
    """

    overlap: list[KeyPhrase]
    just_in_a: list[KeyPhrase]
    just_in_b: list[KeyPhrase]


class PlanDocument(models.Model):
    ACTION_PLAN = 1
    CLIMATE_STRATEGY = 2
    SUMMARY_DOCUMENT = 3
    PRE_PLAN = 4
    MEETING_MINUTES = 5
    BIODIVERSITY_PLAN = 6
    BASELINE_REVIEW = 7
    SUPPORTING_EVIDENCE = 8
    ENGAGEMENT_PLAN = 9
    OTHER_PLAN = 10
    PROGRESS_REPORT = 11
    CITIZENS_ASSEMBLY = 12

    DOCUMENT_TYPE_CHOICES = [
        (ACTION_PLAN, "Action plan"),
        (CLIMATE_STRATEGY, "Climate strategy"),
        (SUMMARY_DOCUMENT, "Summary document"),
        (PRE_PLAN, "Pre-plan"),
        (MEETING_MINUTES, "Meeting minutes"),
        (BIODIVERSITY_PLAN, "Biodiversity plan"),
        (BASELINE_REVIEW, "Baseline review"),
        (SUPPORTING_EVIDENCE, "Supporting evidence"),
        (ENGAGEMENT_PLAN, "Engagement plan"),
        (OTHER_PLAN, "Other plan"),
        (PROGRESS_REPORT, "Progress report"),
        (CITIZENS_ASSEMBLY, "Citizens' assembly"),
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
    history = HistoricalRecords(bases=[PlanDocumentHistoricalModel])
    title = models.CharField(max_length=800, blank=True)

    # This just means the same type is expected wherever this is used
    SortKeyType = TypeVar("SortKeyType")

    @classmethod
    def keyphrase_overlap(
        cls,
        *,
        docs: QuerySet[PlanDocument],
        sort_func: Callable[[PlanDocument], SortKeyType],
        is_main: SortKeyType,
    ) -> dict[SortKeyType, KeyPhraseOverlap]:
        """
        Find the overlap of KeyPhrases between multiple sets of documents.

        docs: QuerySet of PlanDocuments
        sort_func: function to sort the documents into groups
        is_main: the key to use for the main set of documents
        the other groups will be compared to

        """

        # get all documents with their cached KeyPhrases in one query

        docs = list(docs.prefetch_related("key_terms__search_term"))
        docs.sort(key=sort_func)

        grouped_items = {key: list(items) for key, items in groupby(docs, sort_func)}

        # get unique terms used by docs for council_a
        docs_a = grouped_items.get(is_main, [])
        terms_a = set(
            chain.from_iterable(
                (
                    [key_term.search_term for key_term in doc.key_terms.all()]
                    for doc in docs_a
                )
            )
        )
        docs_a = grouped_items.pop(is_main, [])

        # default result if there were no plans assocated with the key
        results = defaultdict(
            lambda: KeyPhraseOverlap(overlap=[], just_in_a=[], just_in_b=[])
        )

        for k, docs_b in grouped_items.items():
            terms_b = set(
                chain.from_iterable(
                    (
                        [key_term.search_term for key_term in doc.key_terms.all()]
                        for doc in docs_b
                    )
                )
            )

            # get the overlap
            overlap = list(terms_a.intersection(terms_b))

            # get the terms that are only in one set
            just_in_a = list(terms_a.difference(terms_b))
            just_in_b = list(terms_b.difference(terms_a))

            kpo = KeyPhraseOverlap(
                overlap=overlap,
                just_in_a=just_in_a,
                just_in_b=just_in_b,
            )

            results[k] = kpo

        return results

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
    def get_description(self):
        if self.status == self.DRAFT:
            return f"draft {self.get_document_type}"
        else:
            return self.get_document_type

    def sorted_key_terms(self):
        """
        Return the key terms for this document
        Basic within-request caching to avoid repeated queries
        """
        if not hasattr(self, "_sorted_key_terms"):
            self._sorted_key_terms = self.key_terms.order_by(
                "search_term__keyphrase"
            ).prefetch_related("search_term")
        return self._sorted_key_terms

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
    def get_document_type_from_code(self, code):
        for choice in self.DOCUMENT_TYPE_CHOICES:
            if choice[0] == code:
                return choice[1].lower()
        return "document"

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


class DataType(models.Model):
    class DataCollection(models.TextChoices):
        EMISSIONS = "em", "Emissions"
        POLLING = "po", "Polling"

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    name = models.CharField(max_length=100)
    source_url = models.URLField(max_length=600)
    name_in_source = models.CharField(max_length=100)
    collection = models.CharField(
        max_length=2, choices=DataCollection.choices, default=DataCollection.EMISSIONS
    )
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
        ("any_promise", "Any target"),
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
    name = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=TextInput(attrs={"type": "search", "placeholder": ""}),
    )
    has_plan = django_filters.BooleanFilter(
        method="filter_plandocument",
        label="Has plan",
        widget=Select(choices=Council.PLAN_FILTER_CHOICES),
    )
    authority_type = django_filters.ChoiceFilter(
        method="filter_authority_type",
        choices=Council.AUTHORITY_TYPE_CHOICES,
        empty_label="All",
    )
    region = django_filters.ChoiceFilter(
        method="filter_region",
        choices=[],
        empty_label="All",
    )

    promise_council = django_filters.ChoiceFilter(
        method="filter_promise_council",
        label="Carbon neutral by (Council)",
        empty_label="All",
        choices=Promise.PROMISE_FILTER_CHOICES,
    )

    promise_area = django_filters.ChoiceFilter(
        method="filter_promise_area",
        label="Carbon neutral by (Area)",
        empty_label="All",
        choices=Promise.PROMISE_FILTER_CHOICES,
    )

    promise_combined = django_filters.ChoiceFilter(
        method="filter_promise",
        label="Carbon neutral by (Any)",
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

    emissions = django_filters.ChoiceFilter(
        method="filter_emissions",
        label="Emissions Profile",
        empty_label="All",
        choices=[],
    )

    geography = django_filters.ChoiceFilter(
        method="filter_geography",
        label="Geography",
        empty_label="All",
        choices=[],
    )

    imd = django_filters.ChoiceFilter(
        method="filter_imd",
        label="IMD Profile",
        empty_label="All",
        choices=[],
    )

    population = django_filters.ChoiceFilter(
        method="filter_population",
        label="Population",
        empty_label="All",
        choices=Council.POPULATION_FILTER_CHOICES,
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

    def filter_plandocument(self, queryset, name, value):
        if value:
            return queryset.filter(
                **{
                    "plandocument__document_type__in": [
                        PlanDocument.ACTION_PLAN,
                        PlanDocument.CLIMATE_STRATEGY,
                    ]
                }
            )

        return queryset.exclude(
            **{
                "plandocument__document_type__in": [
                    PlanDocument.ACTION_PLAN,
                    PlanDocument.CLIMATE_STRATEGY,
                ]
            }
        )

    def filter_authority_type(self, queryset, name, value):
        """
        London is the only strategic regional authority, but we want to treat it as a combined authority.
        """
        if value == "COMB":
            return queryset.filter(**{"authority_type__in": ["COMB", "SRA"]})
        else:
            return queryset.filter(**{name: value})

    def filter_promise_area(self, queryset, name, value):
        return self.filter_promise(queryset, name, value, scope="area")

    def filter_promise_council(self, queryset, name, value):
        return self.filter_promise(queryset, name, value, scope="council")

    def filter_promise(self, queryset, name, value, scope=""):
        promise_field = "has_promise"
        earliest_field = "earliest_promise"
        if scope:
            promise_field += "_" + scope
            earliest_field += "_" + scope

        if value is None:
            return queryset
        elif value == "any_promise":
            return queryset.filter(**{promise_field: 1})
        elif value == "unknown":
            return queryset.filter(**{promise_field: 0})
        elif value == "no_target":
            return queryset.filter(**{f"{promise_field}__gte": 1, earliest_field: None})
        else:
            return queryset.filter(**{f"{earliest_field}__lte": value})

    def filter_emissions(self, queryset, name, value):
        if value is None:
            return queryset
        else:
            return queryset.filter(
                comparisonlabelassignment__label__slug=value,
                comparisonlabelassignment__label__type__slug="emissions",
            )

    def filter_region(self, queryset, name, value):
        if value is None:
            return queryset
        elif value in dict(Council.REGION_CHOICES):
            return queryset.filter(**{"region": value})
        elif value in dict(Council.get_county_choices()):
            q = Q(county=value) | Q(authority_code=value)
            return queryset.filter(q)
        else:
            try:
                value = int(value)
                return queryset.filter(**{"country": value})
            except ValueError:
                return queryset

    def filter_geography(self, queryset, name, value):
        if value is None:
            return queryset
        else:
            return queryset.filter(
                comparisonlabelassignment__label__slug=value,
                comparisonlabelassignment__label__type__slug="ruc",
            )

    def filter_imd(self, queryset, name, value):
        if value is None:
            return queryset
        else:
            return queryset.filter(
                comparisonlabelassignment__label__slug=value,
                comparisonlabelassignment__label__type__slug="imd",
            )

    def filter_population(self, queryset, name, value):
        if value is None:
            return queryset

        filter = {"population__lt": 100000}
        if value == "100k":
            filter = {"population__gt": 100000, "population__lt": 250000}
        elif value == "250k":
            filter = {"population__gt": 250000, "population__lt": 500000}
        elif value == "500":
            filter = {"population__gt": 500000, "population__lt": 750000}
        elif value == "750k":
            filter = {"population__gt": 750000, "population__lt": 1000000}
        elif value == "1m":
            filter = {"population__gt": 1000000}

        return queryset.filter(**filter)

    # we do this here as otherwise region_filter_choices is called before
    # migrations have been run which causes problems for tests on github
    # and also causes unhelpful errors if we can't access the database
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.filters["region"].extra["choices"] = Council.region_filter_choices()
            self.filters["emissions"].extra["choices"] = ComparisonLabel.choices(
                "emissions"
            )
            self.filters["geography"].extra["choices"] = ComparisonLabel.choices("ruc")
            self.filters["imd"].extra["choices"] = ComparisonLabel.choices("imd")
        except (KeyError, AttributeError):
            pass

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
        "physical": "Nearby",
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
        file_path = Path(
            "data", "comparisons", self.slug + "_distance", "datapackage.json"
        )
        with open(file_path, "r") as f:
            self.desc = json.load(f)["description"]
        return self

    @classmethod
    def combine_files(cls, filename: str):
        """
        combine the same file from different types into a
        single dataframe, with a `type_slug` column.
        """

        dfs = []
        for slug in cls.TYPES.keys():
            file_path = Path("data", "comparisons", slug + "_distance", filename)
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

    @classmethod
    def choices(cls, comparison_type: str):
        """
        Return choices for a given comparison type
        """
        labels = cls.objects.filter(type__slug=comparison_type).order_by("name")
        return [(l.slug, l.name) for l in labels]

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


class CouncilProject(models.Model):
    MEASUREMENT_TYPE_CHOICES = [
        ("Actual", "actual"),
        ("Estimated", "estimated"),
    ]

    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.IntegerField(default=0)
    funding = models.CharField(max_length=300, blank=True, default="")
    emission_source = models.CharField(max_length=100, blank=True, default="")
    emission_savings = models.FloatField(default=0)
    capital_cost = models.FloatField(default=0)
    annual_cost = models.FloatField(default=0)
    annual_savings = models.FloatField(default=0)
    measurement_type = models.CharField(
        max_length=30, blank=True, choices=MEASUREMENT_TYPE_CHOICES
    )
    lifespan = models.FloatField(default=0)
    start_year = models.IntegerField(default=0)
    comments = models.TextField(blank=True)


class ProjectFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method="custom_project_freetext_filter",
        label="Search by project details",
        widget=TextInput(attrs={"type": "search", "placeholder": ""}),
    )
    council = django_filters.ModelChoiceFilter(
        label="Search by council",
        queryset=Council.objects.filter(
            country=2
        ),  # TODO: Yuck, mystery number (2 == SCOTLAND)
        empty_label="All councils",
    )

    sort = DefaultSecondarySortFilter(
        secondary="council__name",
        label="Sort by",
        empty_label=None,
        fields=(
            ("council__name", "council_name"),
            ("start_year", "start_year"),
            ("emission_savings", "emission_savings"),
            ("capital_cost", "capital_cost"),
            ("annual_savings", "annual_savings"),
        ),
        field_labels={
            "council__name": "Council name",
            "start_year": "Start year",
            "emission_savings": "Annual emission savings",
            "capital_cost": "Capital cost",
            "annual_savings": "Annual savings",
        },
    )

    def custom_project_freetext_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(comments__icontains=value)
            | Q(funding__icontains=value)
            | Q(emission_source__icontains=value)
        )

    class Meta:
        model = CouncilProject
        ordering = ["-emission_savings"]
        fields = []


class KeyPhrase(models.Model):
    """
    Key phrases extracted from document
    """

    keyphrase = models.CharField(max_length=200)
    nice_phrase = models.CharField(max_length=200, blank=True)
    plan_count = models.IntegerField(default=0)
    average_frequency = models.FloatField(default=0)
    highlight = models.BooleanField(default=False)

    @classmethod
    def populate(cls, quiet: bool = False):
        """
        Populate the database from the sourcefile
        """
        df = pd.read_csv(Path("data", "ml_keyphrases_with_highlights.csv"))
        # limit to keyphrases above 4 characters
        df = df[df["keyphrase"].str.len() > 4]
        df["highlight"] = df["highlight"].fillna(False)
        cls.objects.all().delete()
        save_df_to_model(cls, df, quiet=quiet)

    @classmethod
    def valid_keyphrases(cls):
        """
        Get all valid keyphrases - as defined by highlight term
        """
        return cls.objects.filter(highlight=True)

    def display_name(self) -> str:
        """
        Get the name to display for this keyphrase
        """
        return self.nice_phrase or self.keyphrase

    def related_phrases(
        self, threshold: float = settings.RELATED_SEARCH_THRESHOLD
    ) -> List[str]:
        """
        Get all similar terms to this one, with a cosine similarity above the threshold
        """
        return list(
            KeyPhrasePairWise.objects.filter(
                word_a=self, cosine_similarity__gte=threshold
            )
            .order_by("-cosine_similarity")
            .prefetch_related("word_b")
            .values_list("word_b__keyphrase", flat=True)
        )


class KeyPhrasePairWise(models.Model):
    """
    Connection of word similarity between keyphrases
    """

    word_a = models.ForeignKey(
        KeyPhrase, on_delete=models.CASCADE, related_name="word_a"
    )
    word_b = models.ForeignKey(
        KeyPhrase, on_delete=models.CASCADE, related_name="word_b"
    )
    nth_similar = models.IntegerField()
    cosine_similarity = models.FloatField()
    has_common_word = models.BooleanField()

    class Meta:
        """
        Meta settings for the model
        """

        unique_together = ("word_a", "word_b")

    @classmethod
    def populate(cls, quiet: bool = False):
        """
        Populate the lookup table from the source file
        """
        df = pd.read_csv(Path("data", "ml_keyphrases_pairwise.csv"))
        word_id_dict = {x.keyphrase: x.id for x in KeyPhrase.objects.all()}
        # get ids to bulk populate
        df["word_a_id"] = df["word_a"].map(word_id_dict)
        df["word_b_id"] = df["word_b"].map(word_id_dict)
        # drop any rows with nulls in word_a_id or word_b_id
        df = df.dropna(subset=["word_a_id", "word_b_id"])
        # drop original cols
        df = df.drop(columns=["word_a", "word_b"])
        df = df.rename(
            columns={
                "cosine similarity": "cosine_similarity",
                "nth similar": "nth_similar",
            }
        )

        # do not store any with a cosine_similarity below 0.5
        df = df[df["cosine_similarity"] > 0.5]
        cls.objects.all().delete()
        word_id_dict = None
        save_df_to_model(cls, df, batch_size=10000, quiet=quiet)


class CachedSearch(models.Model):
    search_term = models.ForeignKey(KeyPhrase, on_delete=models.CASCADE)
    document = models.ForeignKey(
        PlanDocument, on_delete=models.CASCADE, related_name="key_terms"
    )
    count = models.IntegerField()

    class Meta:
        unique_together = ("search_term", "document")
