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
    search_fields = ('name', 'authority_code', 'gss_code')

admin.site.register(Council, CouncilAdmin)

class PlanDocumentAdmin(admin.ModelAdmin):
    list_display = ('council',
                    'document_type',
                    'status',
                    'scope',
                    'file_type')
    list_filter = ('document_type', 'status', 'scope', 'file_type')
    search_fields = ('council__name',)

admin.site.register(PlanDocument, PlanDocumentAdmin)
