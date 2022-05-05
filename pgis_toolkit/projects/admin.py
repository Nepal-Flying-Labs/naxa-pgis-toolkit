from django.contrib import admin

from .models import *


class OrganizationCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('id', 'name')

class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'category', 'name', 'link')
    search_fields = ('id', 'name', 'email', 'link')
    list_filter = ('category',)

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'organization', 'name')
    search_fields = ('id', 'name')
    list_filter = ('organization', 'start_date', 'end_date')

class ProjectLocationFeatureCollectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'project', 'attributes')
    search_fields = ('id', )
    list_filter = ('project',)

class DefaultThemeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'order')
    search_fields = ('id', 'name')

class LayerTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'geometry_type')
    search_fields = ('id', 'name')
    list_filter = ('geometry_type',)

class LayerTemplateAttributeAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer_template', 'name', 'data_type','length','precision','alias', 'unit')
    search_fields = ('id', 'name', 'alias')
    list_filter = ('layer_template', 'data_type')

class CountryAdmin (admin.ModelAdmin):
    list_display = ('id', 'name', 'code')
    search_fields = ('id', 'name', 'code')

class StateAdmin (admin.ModelAdmin):
    list_display = ('id', 'name', 'code')
    search_fields = ('id', 'name', 'code')
# Register your models here.
admin.site.register(OrganizationCategory, OrganizationCategoryAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(DefaultTheme)
admin.site.register(LayerTemplate)
admin.site.register(LayerTemplateAttribute, LayerTemplateAttributeAdmin)
admin.site.register(Country, CountryAdmin)
admin.site.register(State, StateAdmin)
admin.site.register(ProjectLocationFeatureCollection, ProjectLocationFeatureCollectionAdmin)
