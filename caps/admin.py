from django.contrib import admin

from caps.models import Council, DataPoint, DataType, PlanDocument
from scoring.models import (
    PlanQuestion,
    PlanScore,
    PlanSection,
    PlanYear,
    PlanYearConfig,
)


class CouncilAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "authority_code",
        "authority_type",
        "gss_code",
        "country",
        "website_url",
        "is_current",
    )
    list_filter = ("authority_type", "country")
    search_fields = ("name", "authority_code", "gss_code")


admin.site.register(Council, CouncilAdmin)


class PlanDocumentAdmin(admin.ModelAdmin):
    list_display = ("council", "document_type", "status", "scope", "file_type")
    list_filter = ("document_type", "status", "scope", "file_type")
    search_fields = ("council__name",)


admin.site.register(PlanDocument, PlanDocumentAdmin)


class DataTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "source_url", "unit", "name_in_source")


admin.site.register(DataType, DataTypeAdmin)


class DataPointAdmin(admin.ModelAdmin):
    list_display = ("year", "value", "council", "data_type")

    search_fields = ("council__name", "data_type__name")
    list_filter = ("data_type__name", "year")


admin.site.register(DataPoint, DataPointAdmin)


class PlanSectionAdmin(admin.ModelAdmin):
    list_display = ("description", "code", "year")
    list_filter = ("year",)


admin.site.register(PlanSection, PlanSectionAdmin)


class PlanQuestionAdmin(admin.ModelAdmin):
    list_display = ("code", "text")
    list_filter = ("section__description", "section__year")


admin.site.register(PlanQuestion, PlanQuestionAdmin)


class PlanScoreAdmin(admin.ModelAdmin):
    list_display = ("council", "year")
    search_fields = ("council__name",)


admin.site.register(PlanScore, PlanScoreAdmin)


class PlanYearAdmin(admin.ModelAdmin):
    list_display = (
        "year",
        "previous_year",
        "old_council_date",
        "new_council_date",
        "is_current",
    )


admin.site.register(PlanYear, PlanYearAdmin)


class PlanYearConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "year")


admin.site.register(PlanYearConfig, PlanYearConfigAdmin)
