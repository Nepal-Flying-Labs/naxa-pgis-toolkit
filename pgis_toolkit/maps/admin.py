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

# Register your models here.
admin.site.register(Theme, ThemeAdmin)
admin.site.register(LayerGroup, LayerGroupAdmin)
admin.site.register(Layer, LayerAdmin)
admin.site.register(SubLayer)
admin.site.register(Vectorlayer)
admin.site.register(RasterLayer)
admin.site.register(WMSLayer)
admin.site.register(LayerAttribute)
