from django.contrib import admin
from scoring.models import PlanSection

from caps.models import Council, DataPoint, DataType, PlanDocument


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
