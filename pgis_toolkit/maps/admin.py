from django.contrib import admin

from .models import *


class ThemeAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'project')
    search_fields = ('id', 'name')
    list_filter = ('project',)

class LayerGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'theme')
    search_fields = ('id', 'name')
    list_filter = ('theme',)

class LayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'layer_type', 'is_osm_layer')
    search_fields = ('id', 'name')
    list_filter = ('layer_type', 'default_load', 'is_osm_layer')

class LayerFileAdmin(admin.ModelAdmin):
    list_display=('id','file','layer')

class LayerAttributeAdmin(admin.ModelAdmin):
    list_display = ('id','layer', 'name', 'alias','data_type', 'length','precision','unit')
    search_fields = ('id','layer__id','name','alias','data_type',)
    list_filter = ('data_type',)

class SubLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted','layer', 'name', 'order')
    search_fields = ('id', 'name','layer__id')
    list_filter = ('is_deleted', 'layer')

class VectorLayerAdmin(admin.ModelAdmin):
    list_display = ('id','layer','geom_type','geoserver_workspace','geoserver_layer_name')
    search_fields = ('id', 'layer')
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
