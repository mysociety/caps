from collections import defaultdict

from caps.models import Council
from django.conf import settings
from django.db import models
from django.db.models import Avg, Count, F, Max, Q


# define this here as mixins imports PlanScore so if we import that then we get
# circular references
class ScoreFilterMixin:
    @classmethod
    def filter_for_council_and_plan_year(
        cls, queryset, council_group=None, plan_year=None
    ):
        if council_group is not None:
            queryset = queryset.filter(
                plan_score__council__authority_type__in=council_group["types"],
                plan_score__council__country__in=council_group["countries"],
            )

        if plan_year is not None:
            year_filter = {cls.year_filter: plan_year}
            queryset = queryset.filter(**year_filter)

        return queryset


class PlanScore(models.Model):
    """
    Overall score for a council's plan for a particular year
    """

    RUC_TYPES = [
        ("urban", "Urban"),
        ("rural", "Rural"),
        ("urban-rural-areas", "Urban with rural areas"),
        ("sparse-rural", "Sparse and rural"),
    ]

    POPULATION_ALL_FILTER_CHOICES = [
        ("0k - 140k", "0k - 140k"),
        ("50k - 80k", "50k - 80k"),
        ("80k - 90k", "80k - 90k"),
        ("90k - 100k", "90k - 100k"),
        ("110k - 120k", "110k - 120k"),
        ("120k - 130k", "120k - 130k"),
        ("140k - 160k", "140k - 160k"),
        ("140k - 210k", "140k - 210k"),
        ("170k - 250k", "170k - 250k"),
        ("210k - 290k", "210k - 290k"),
        ("290k - 410k", "290k - 410k"),
        ("440k - 640k", "440k - 640k"),
        ("800k - 1140k", "800k - 1140k"),
        ("under 800k", "under 800k"),
        ("800k - 1m", "800k - 1m"),
        ("1m +", "1m +"),
    ]

    POPULATION_FILTER_CHOICES = {
        "single": [
            ("0k - 140k", "0k - 140k"),
            ("140k - 210k", "140k - 210k"),
            ("210k - 290k", "210k - 290k"),
            ("290k - 410k", "290k - 410k"),
            ("440k - 640k", "440k - 640k"),
            ("800k - 1140k", "800k - 1140k"),
        ],
        "county": [
            ("under 800k", "under 800k"),
            ("800k - 1m", "800k - 1m"),
            ("1m +", "1m +"),
        ],
        "district": [
            ("50k - 80k", "50k - 80k"),
            ("80k - 90k", "80k - 90k"),
            ("90k - 100k", "90k - 100k"),
            ("110k - 120k", "110k - 120k"),
            ("120k - 130k", "120k - 130k"),
            ("140k - 160k", "140k - 160k"),
            ("170k - 250k", "170k - 250k"),
        ],
    }

    POLITICAL_CONTROL_FILTER_CHOICES = []

    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(null=True, blank=True)

    # these are percentages
    weighted_total = models.FloatField(default=0)
    total = models.FloatField(default=0)

    top_performer = models.CharField(
        max_length=20, choices=Council.SCORING_GROUP_CHOICES, null=True
    )

    # filter data
    deprivation_quintile = models.SmallIntegerField(default=0)
    population = models.CharField(max_length=20, null=True, blank=True)
    region = models.CharField(max_length=100, blank=True)
    ruc_cluster = models.CharField(
        max_length=100, choices=RUC_TYPES, null=True, blank=True
    )
    political_control = models.CharField(max_length=100, null=True, blank=True)

    def questions_answered(self):
        # do this in raw SQL as otherwise we need an extra query
        questions = PlanQuestion.objects.raw(
            "select q.id, q.code, q.text, q.question_type, q.max_score, s.code as section_code, a.answer, a.score, a.max_score as header_max, q.weighting, q.how_marked, a.evidence_links \
            from scoring_planquestion q join scoring_plansection s on q.section_id = s.id \
            left join scoring_planquestionscore a on q.id = a.plan_question_id \
            where s.year = %s and ( a.plan_score_id = %s or a.plan_score_id is null) and a.plan_question_id is not null\
            order by q.code",
            [self.year, self.id],
        )

        return questions

    @classmethod
    def questions_answered_for_councils(cls, plan_ids=None, plan_year=None):
        # do this in raw SQL as otherwise we need an extra query
        questions = PlanQuestion.objects.raw(
            "select q.id, q.code, q.text, q.question_type, q.max_score, s.code as section_code, a.answer, a.score, a.max_score as header_max, q.weighting, q.how_marked, a.evidence_links, c.name as council_name \
            from scoring_planquestion q join scoring_plansection s on q.section_id = s.id \
            left join scoring_planquestionscore a on q.id = a.plan_question_id \
            join scoring_planscore ps on a.plan_score_id = ps.id \
            join caps_council c on ps.council_id = c.id \
            where s.year = %s and ( a.plan_score_id in %s or a.plan_score_id is null) and (q.question_type = 'HEADER' or a.plan_question_id is not null)\
            order by q.code, c.name",
            [plan_year, tuple(plan_ids)],
        )

        return questions

    @classmethod
    def ruc_cluster_description(cls, ruc_cluster):
        codes_to_descriptions = dict(
            (cluster, description) for cluster, description in cls.RUC_TYPES
        )
        return codes_to_descriptions.get(ruc_cluster)


# this needs to handle councils that use district plan. possibly just have duplicates?
class PlanScoreDocument(models.Model):
    plan_score = models.ForeignKey(PlanScore, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, null=True)
    plan_url = models.URLField(max_length=1000)


class PlanSection(models.Model):
    """
    Details of a section in the scoring
    """

    FILTER_FIELD_MAP = {
        "imdq": "deprivation_quintile",
        "ruc_cluster": "ruc_cluster",
        "control": "political_control",
        "population": "population",
        "country": "council__country",
    }

    ALT_MAP = {
        "s1_b_h": "s1_b_h_gs_ca",
        "s2_tran": "s2_tran_ca",
        "s3_p_lu": "s3_p_b_ca",
        "s4_g_f": "s5_g_f_ca",
        "s6_c_e": "s6_c_e_ca",
    }

    COMBINED_ALT_MAP = dict((ca, non_ca) for non_ca, ca in ALT_MAP.items())

    code = models.CharField(max_length=100)
    description = models.CharField(max_length=1000)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    top_performer = models.CharField(
        max_length=20, choices=Council.SCORING_GROUP_CHOICES, null=True
    )

    def get_averages_by_council_group(self):
        averages = {}

        scores = PlanSectionScore.objects.filter(
            plan_score__total__gt=0,
            plan_section=self,
        ).select_related("plan_score", "plan_section")

        for group, props in Council.SCORING_GROUPS.items():
            councils = Council.objects.filter(
                authority_type__in=props["types"], country__in=props["countries"]
            )

            avg = scores.filter(plan_score__council__in=councils).aggregate(
                avg=Avg("score"),
                max=Max("max_score"),
            )

            averages[group] = {"average": avg["avg"], "maximum": avg["max"]}

        return averages

    @property
    def is_combined(self):
        return self.code.find("_ca") > 0

    @property
    def get_alternative(self):
        alt = None
        if self.is_combined:
            alt = self.COMBINED_ALT_MAP.get(self.code, None)
        else:
            alt = self.ALT_MAP.get(self.code, None)

        if alt is not None:
            alt = PlanSection.objects.get(code=alt)

        return alt

    @classmethod
    def section_codes(cls, year=settings.PLAN_YEAR):
        return (
            cls.objects.filter(year=year)
            .distinct("code")
            .values_list("code", flat=True)
        )

    @classmethod
    def get_average_scores(
        cls, council_group=None, filter=None, year=settings.PLAN_YEAR
    ):
        """
        This excludes plans with zero score as it's assumed that if they have 0 then they
        were not marked, or the council has no plan, and hence including them would artificially
        reduce the average.
        """
        has_score = PlanScore.objects.filter(total__gt=0, year=year)
        if council_group is not None:
            group = Council.SCORING_GROUPS[council_group]
            has_score = has_score.filter(
                council__authority_type__in=group["types"],
                council__country__in=group["countries"],
            )

        if filter is not None:
            kwargs = {}
            for field in PlanSection.FILTER_FIELD_MAP.keys():
                if filter.get(field):
                    kwargs[PlanSection.FILTER_FIELD_MAP[field]] = filter[field]

            has_score = has_score.filter(Q(**kwargs))

        has_score_avg = has_score.aggregate(
            maximum=Max("weighted_total"), average=Avg("weighted_total")
        )
        has_score_list = has_score.values_list("pk", flat=True)

        scores = cls.objects.filter(
            plansectionscore__plan_score__in=list(has_score_list)
        ).annotate(
            average_score=Avg("plansectionscore__score"),
            max_score=Max("plansectionscore__max_score"),
        )

        averages = {}
        for score in scores:
            averages[score.code] = {
                "score": round(score.average_score),
                "max": score.max_score,
            }

        max_score = 0
        avg_score = 0
        if has_score_avg["average"] is not None:
            avg_score = round(has_score_avg["average"])
            max_score = round(has_score_avg["maximum"])

        averages["total"] = {
            "score": avg_score,
            "max": max_score,
            "percentage": round(avg_score),
        }

        return averages


class PlanSectionScore(ScoreFilterMixin, models.Model):
    """
    Score for a section of a council's plan
    """

    year_filter = "plan_section__year"

    plan_score = models.ForeignKey(PlanScore, on_delete=models.CASCADE)
    plan_section = models.ForeignKey(PlanSection, on_delete=models.CASCADE)
    score = models.SmallIntegerField(default=0)
    # store the max score here because not all council types get asked the same set of questions
    # so there may not be a consistent per section max score
    max_score = models.PositiveSmallIntegerField(default=0)
    # this is a percentage
    weighted_score = models.FloatField(default=0)
    top_performer = models.CharField(
        max_length=20, choices=Council.SCORING_GROUP_CHOICES, null=True
    )

    def questions_answered(self):
        questions = PlanQuestionScore.objects.filter(
            plan_score=self.plan_score, plan_question__section=self.plan_section
        ).select_related("plan_question")

        return questions

    @classmethod
    def make_section_object(cls, section):
        return {
            "section_score": section,
            "council_name": section.plan_score.council.name,
            "council_slug": section.plan_score.council.slug,
            "top_performer": section.top_performer,
            "code": section.plan_section.code,
            "description": section.plan_section.description,
            "max_score": section.max_score,
            # default this to zero as the query below won't return a row if no
            # councils got full marks
            "max_count": 0,
            "score": section.score,
            "answers": [],
            "comparisons": [],
            "non_negative_max": section.max_score,
            "negative_points": 0,
        }

    @classmethod
    def sections_for_council(cls, council=None, plan_year=None):
        sections = {}
        section_qs = cls.objects.select_related("plan_section").filter(
            plan_score__council=council, plan_section__year=plan_year
        )

        sections = {}
        for section in section_qs.all():
            sections[section.plan_section.code] = cls.make_section_object(section)

        return sections

    @classmethod
    def sections_for_plans(cls, plans=None, plan_year=None, plan_sections=None):
        sections = {}
        section_qs = (
            cls.objects.select_related("plan_section", "plan_score__council")
            .filter(plan_score__in=plans, plan_section__year=plan_year)
            .order_by("plan_section__code", "plan_score__council__name")
        )

        if sections is not None:
            section_qs = section_qs.filter(plan_section__in=plan_sections)

        sections = defaultdict(list)
        for section in section_qs.all():
            sections[section.plan_section.code].append(cls.make_section_object(section))

        return sections

    @classmethod
    def get_all_council_scores(cls, plan_year=settings.PLAN_YEAR):
        """
        This excludes plans with zero score as it's assumed that if they have 0 then they
        were not marked, or the council has no plan
        """
        scores = (
            cls.objects.all()
            .select_related("plan_section", "plan_score")
            .filter(plan_score__year=plan_year, plan_score__total__gt=0)
            .values(
                "plan_score__total",
                "plan_score__council_id",
                "score",
                "weighted_score",
                "plan_section__code",
                "max_score",
            )
        )
        councils = defaultdict(dict)
        for score in scores:
            councils[score["plan_score__council_id"]][score["plan_section__code"]] = {
                "score": score["score"],
                "max": score["max_score"],
            }

        return councils

    @classmethod
    def get_all_section_averages(cls, council_group=None, plan_year=None):
        section_avgs = cls.objects.select_related("plan_section").filter(
            plan_score__total__gt=0
        )
        section_avgs = cls.filter_for_council_and_plan_year(
            section_avgs, council_group=council_group, plan_year=plan_year
        )

        section_avgs = section_avgs.values("plan_section__code").annotate(
            avg_score=Avg("score")
        )

        return section_avgs

    @classmethod
    def get_all_section_top_mark_counts(cls, council_group=None, plan_year=None):
        section_top_marks = cls.objects.select_related("plan_section").filter(
            score=F("max_score")
        )
        section_top_marks = cls.filter_for_council_and_plan_year(
            section_top_marks, council_group=council_group, plan_year=plan_year
        )

        section_top_marks = section_top_marks.values("plan_section__code").annotate(
            max_score_count=Count("pk")
        )

        return section_top_marks


class PlanQuestionGroup(models.Model):
    description = models.TextField(max_length=200)


class PlanQuestion(models.Model):
    """
    Details of an individual question in the scoring.

    NB: some question types might be sub section headers and have no score
    """

    MARKING_TYPES = [
        ("foi", "FOI"),
        ("national_data", "National Data"),
        ("volunteer", "Volunteer Research"),
        ("national_volunteer", "National Data and Volunteer Research"),
    ]

    WEIGHTINGS = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("unweighted", "Unweighted"),
    ]

    section = models.ForeignKey(PlanSection, on_delete=models.CASCADE)
    code = models.CharField(max_length=100)
    text = models.TextField(null=True, default="")
    max_score = models.PositiveSmallIntegerField(default=0)
    question_type = models.CharField(max_length=100)  # needs choices
    parent = models.CharField(max_length=100, null=True, default="")
    how_marked = models.CharField(
        max_length=30, null=True, default="", choices=MARKING_TYPES
    )
    weighting = models.CharField(max_length=20, default="low", choices=WEIGHTINGS)
    criteria = models.TextField(null=True, default="")
    topic = models.TextField(null=True, default="")
    clarifications = models.TextField(null=True, default="")

    questiongroup = models.ManyToManyField(PlanQuestionGroup, null=True, blank=True)

    def pretty_code(self):
        """
        returns a more human-readable version of the question code
        """
        parts = self.code.split("_")
        section = parts[0][1:]
        section_text = parts[1]
        question = [x for x in parts if x[0] == "q"][0][1:]
        components = [section, question]
        if "SP" in self.code.upper():
            sub_point = [x for x in parts if x.startswith("sp")][0][2:]
            components.append(sub_point)
        if parts[-1] == "b":
            components.append("b")

        code = ".".join(components)

        # 4.13.1 was deleted
        # easier to fix here than rename all references
        if code == "4.13.2":
            code = "4.13.1"
        if code == "4.13.3":
            code = "4.13.2"

        return code

    @classmethod
    def get_average_scores(cls, section=None, council_group=None):
        qs = PlanQuestionScore.objects.all()
        if section is not None:
            qs = qs.filter(plan_question__section=section)
        # XXX fix this when relevant code is merged
        # if council_group is not None:
        # qs = qs.filter(question__=section)

        qs = qs.values("plan_question__code").annotate(average=Avg("score"))

        return qs


class PlanQuestionScore(ScoreFilterMixin, models.Model):
    """
    Score for an individual question for a council's plan
    """

    year_filter = "plan_score__year"

    plan_score = models.ForeignKey(PlanScore, on_delete=models.CASCADE)
    plan_question = models.ForeignKey(
        PlanQuestion, on_delete=models.CASCADE, related_name="questions"
    )
    answer = models.TextField(null=True, default="")
    score = models.SmallIntegerField(default=0)
    max_score = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(null=True, default="")
    evidence_links = models.TextField(null=True, default="")

    @classmethod
    def all_question_max_score_counts(cls, council_group=None, plan_year=None):
        max_counts = PlanQuestionScore.objects.filter(
            score=F("plan_question__max_score"),
        ).exclude(
            plan_question__question_type="HEADER",
        )

        max_counts = cls.filter_for_council_and_plan_year(
            max_counts, council_group=council_group, plan_year=plan_year
        )

        max_counts = max_counts.values("plan_question__code").annotate(
            council_count=Count("pk")
        )

        header_max_counts = PlanQuestionScore.objects.filter(
            plan_question__question_type="HEADER",
            score=F("max_score"),
        )

        header_max_counts = cls.filter_for_council_and_plan_year(
            header_max_counts, council_group=council_group, plan_year=plan_year
        )

        header_max_counts = header_max_counts.values("plan_question__code").annotate(
            council_count=Count("pk")
        )

        question_max_counts = {}
        for count in max_counts:
            question_max_counts[count["plan_question__code"]] = count["council_count"]

        for count in header_max_counts:
            question_max_counts[count["plan_question__code"]] = count["council_count"]

        return question_max_counts
