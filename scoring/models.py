from collections import defaultdict

from django.db import models
from django.db.models import Avg, Max, Q

from caps.models import Council


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

    code = models.CharField(max_length=100)
    description = models.CharField(max_length=1000)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    top_performer = models.CharField(
        max_length=20, choices=Council.SCORING_GROUP_CHOICES, null=True
    )

    @classmethod
    def section_codes(cls):
        return cls.objects.distinct("code").values_list("code", flat=True)

    @classmethod
    def get_average_scores(cls, council_group=None, filter=None):
        """
        This excludes plans with zero score as it's assumed that if they have 0 then they
        were not marked, or the council has no plan, and hence including them would artificially
        reduce the average.
        """
        has_score = PlanScore.objects.filter(total__gt=0)
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
    top_performer = models.CharField(
        max_length=20, choices=Council.SCORING_GROUP_CHOICES, null=True
    )

    @classmethod
    def get_all_council_scores(cls):
        """
        This excludes plans with zero score as it's assumed that if they have 0 then they
        were not marked, or the council has no plan
        """
        scores = (
            cls.objects.all()
            .select_related("plan_section", "plan_score")
            .filter(plan_score__total__gt=0)
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


class PlanQuestion(models.Model):
    """
    Details of an individual question in the scoring.

    NB: some question types might be sub section headers and have no score
    """

    section = models.ForeignKey(PlanSection, on_delete=models.CASCADE)
    code = models.CharField(max_length=100)
    text = models.TextField(null=True, default="")
    max_score = models.PositiveSmallIntegerField(default=0)
    question_type = models.CharField(max_length=100)  # needs choices
    parent = models.CharField(max_length=100, null=True, default="")

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


class PlanQuestionScore(models.Model):
    """
    Score for an individual question for a council's plan
    """

    plan_score = models.ForeignKey(PlanScore, on_delete=models.CASCADE)
    plan_question = models.ForeignKey(
        PlanQuestion, on_delete=models.CASCADE, related_name="questions"
    )
    answer = models.TextField(null=True, default="")
    score = models.PositiveSmallIntegerField(default=0)
    max_score = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(null=True, default="")
