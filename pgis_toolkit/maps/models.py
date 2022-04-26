from django.db import models
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from pgis_toolkit.projects.models import DateTimeStamp, IsDeleted, Project

LAYER_TYPE_CHOICES=(("Raster",_("Raster")),("Vector",_('Vector')),('WMS',_('WMS')))

# Create your models here.
class Theme(IsDeleted,DateTimeStamp):
    project=models.ForeignKey(Project,on_delete=models.CASCADE,blank=True,null=True)
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)

    def __str__(self):
        return str(self.name)

class ThemeAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'project')
    search_fields = ('id', 'name')
    list_filter = ('project',)

class Category(IsDeleted,DateTimeStamp):
    theme=models.ForeignKey(Theme,on_delete=models.CASCADE,blank=True,null=True)
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)

    def __str__(self):
        return str(self.name)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'theme')
    search_fields = ('id', 'name')
    list_filter = ('theme',)

class Layer(IsDeleted,DateTimeStamp):
    category=models.ForeignKey(Category,on_delete=models.CASCADE,blank=True,null=True)
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)
    default_load=models.BooleanField(default=False)
    layer_type=models.CharField(max_length=20,choices=LAYER_TYPE_CHOICES)
    is_osm_layer=models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)

class LayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'name', 'category', 'layer_type', 'is_osm_layer')
    search_fields = ('id', 'name')
    list_filter = ('category', 'layer_type', 'default_load', 'is_osm_layer')