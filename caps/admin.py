from django.contrib import admin

from caps.models import Council, PlanDocument


class CouncilAdmin(admin.ModelAdmin):
    list_display = ('name',
                    'slug',
                    'authority_code',
                    'authority_type',
                    'gss_code',
                    'country',
                    'website_url')
    list_filter = ('authority_type', 'country')
    search_fields = ('name', 'authority_code')

class PlanDocumentAdmin(admin.ModelAdmin):
    list_display = ('get_council_name',
                    'document_type',
                    'status',
                    'scope',
                    'file_type')
    list_filter = ('document_type', 'status', 'scope', 'file_type')
    search_fields = ('council__name',)

    def get_council_name(self, obj):
        return obj.council.name

    get_council_name.short_description = 'Council'
    get_council_name.admin_order_field = 'council__name'

admin.site.register(Council, CouncilAdmin)

admin.site.register(PlanDocument, PlanDocumentAdmin)
