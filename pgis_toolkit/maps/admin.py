from django.contrib import admin

from .models import *


class ThemeAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'project')
    search_fields = ('id', 'name')
    list_filter = ('project',)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'theme')
    search_fields = ('id', 'name')
    list_filter = ('theme',)

class LayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'category', 'layer_type', 'is_osm_layer')
    search_fields = ('id', 'name')
    list_filter = ('category', 'layer_type', 'default_load', 'is_osm_layer')

# Register your models here.
admin.site.register(Theme, ThemeAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Layer, LayerAdmin)
