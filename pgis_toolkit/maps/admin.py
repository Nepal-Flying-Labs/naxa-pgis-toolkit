from django.contrib import admin

from .models import *


class ThemeAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted','order', 'name', 'project')
    search_fields = ('id', 'name')
    list_filter = ('project',)

class LayerGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'theme')
    search_fields = ('id', 'name')
    list_filter = ('theme',)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('id', 'name')

def change_layer_upload_status_to_successful(modeladmin, request, queryset):
    queryset.update(upload_status='successful')
change_layer_upload_status_to_successful.short_description = 'Change Upload Status to Successful'

class LayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'order','name','group', 'layer_type', 'is_osm_layer')
    search_fields = ('id', 'name')
    list_filter = ('layer_type', 'default_load', 'is_osm_layer')
    actions = [change_layer_upload_status_to_successful]

class LayerFileAdmin(admin.ModelAdmin):
    list_display=('id','file','layer')

class LayerAttributeAdmin(admin.ModelAdmin):
    list_display = ('id','layer', 'name', 'alias','data_type', 'length','precision','unit')
    search_fields = ('id','layer__id','name','alias','data_type',)
    list_filter = ('data_type',)
    readonly_fields=['name','layer']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class SubLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted','layer', 'name', 'order','bbox')
    search_fields = ('id', 'name','layer__id')
    list_filter = ('is_deleted', 'layer')
    readonly_fields=['name',]

class VectorLayerAdmin(admin.ModelAdmin):
    list_display = ('id','layer','geom_type','geoserver_workspace','geoserver_layer_name')
    search_fields = ('id', 'layer__name')
    list_filter = ('geom_type', )

    def has_add_permission(self, request):
        return False

class RasterLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer','geoserver_workspace','geoserver_layer_name')
    search_fields = ('id','geoserver_workspace','geoserver_layer_name')
    list_filter = ('geoserver_workspace', )

    def has_add_permission(self, request):
        return False

class WMSLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer','url')

    def has_add_permission(self, request):
        return False

class FeatureCollectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer','sub_layer')
    list_filter = ('layer', )
    search_fields=('layer__id',)

class FeatureCollectionMirrorAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer','sub_layer')
    list_filter = ('layer', )
    search_fields=('layer__id',)

class ProjectLayerTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'geometry_type', 'project')
    search_fields = ('id', 'name')
    list_filter = ('geometry_type','project')

class ProjectLayerTemplateAttributeAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer_template', 'name', 'data_type','length','precision','alias', 'unit')
    search_fields = ('id', 'name', 'alias')
    list_filter = ('layer_template', 'data_type')

class StandardIconAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'icon', 'is_deleted','uploaded_date','last_updated')

class ProjectStyleAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'project', 'is_deleted','uploaded_date','last_updated')
    list_filter = ('project',)

class LayerStyleAdmin(admin.ModelAdmin):
    list_display = ('id','layer', 'project_style', 'is_deleted','uploaded_date','last_updated')
    list_filter = ('project_style__project',)

class SubLayerStyleAdmin(admin.ModelAdmin):
    list_display = ('id','sub_layer', 'project_style', 'is_deleted','uploaded_date','last_updated')
    list_filter = ('project_style__project',)

class AnalysisAdmin(admin.ModelAdmin):
    list_display = ('id','is_deleted', 'name', 'type', 'geom_type', 'display', 'project', 'uploaded_date')
    list_filter = ('type', 'display', 'project')

class NetworkRoutesAdmin(admin.ModelAdmin):
    list_display = ('id','is_deleted', 'analysis_id', 'route_no', 'length', 'travel_time', 'uploaded_date')
    list_filter = ('route_no', 'analysis_id')

class CeleryTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_id')

class QueryLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'theme', 'group', 'geom_type', 'display_on_map', 'source', 'uploaded_date')

class QueryFeatureCollectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer')

# Register your models here.
admin.site.register(Theme, ThemeAdmin)
admin.site.register(LayerGroup, LayerGroupAdmin)
admin.site.register(Layer, LayerAdmin)
admin.site.register(SubLayer,SubLayerAdmin)
admin.site.register(Vectorlayer,VectorLayerAdmin)
admin.site.register(RasterLayer,RasterLayerAdmin)
admin.site.register(WMSLayer,WMSLayerAdmin)
admin.site.register(LayerAttribute,LayerAttributeAdmin)
admin.site.register(LayerFile,LayerFileAdmin)
admin.site.register(FeatureCollection,FeatureCollectionAdmin)
admin.site.register(FeatureCollectionMirror,FeatureCollectionAdmin)
admin.site.register(ProjectsLayerTemplate,ProjectLayerTemplateAdmin)
admin.site.register(ProjectsLayerTemplateAttribute,ProjectLayerTemplateAttributeAdmin)
admin.site.register(StandardIcon,StandardIconAdmin)
admin.site.register(ProjectStyle,ProjectStyleAdmin)
admin.site.register(LayerStyle,LayerStyleAdmin)
admin.site.register(SubLayerStyle,SubLayerStyleAdmin)
admin.site.register(NetworkRoutes, NetworkRoutesAdmin)
admin.site.register(Analysis, AnalysisAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(CeleryTask, CeleryTaskAdmin)
admin.site.register(QueryLayer, QueryLayerAdmin)
admin.site.register(QueryFeatureCollection, QueryFeatureCollectionAdmin)
