from django.contrib import admin

from .models import *


class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'category', 'name', 'link')
    search_fields = ('id', 'name', 'email', 'link')
    list_filter = ('category',)

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'organization', 'name')
    search_fields = ('id', 'name')
    list_filter = ('organization', 'start_date', 'end_date')

class LayerTemplateAttributeAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer_template', 'name', 'alias', 'unit')
    search_fields = ('id', 'name', 'alias')
    list_filter = ('layer_template', 'data_type')

# Register your models here.
admin.site.register(OrganizationCategory)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(DefaultTheme)
admin.site.register(LayerTemplate)
admin.site.register(LayerTemplateAttribute, LayerTemplateAttributeAdmin)
