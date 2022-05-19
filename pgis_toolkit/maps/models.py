from django.contrib.gis.db import models as md
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _

from pgis_toolkit.projects.models import DateTimeStamp, IsDeleted, Project
from pgis_toolkit.utils.constants import (
    DATA_TYPE_CHOICES,
    GEOMETRY_TYPE_CHOICES,
    LAYER_TYPE_CHOICES,
    UNIT_CHOICES,
)


# Create your models here.
class Theme(IsDeleted,DateTimeStamp):
    project=models.ForeignKey(Project, related_name='ThemeProject', on_delete=models.CASCADE,blank=True,null=True)
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)

    def __str__(self):
        return str(self.name)
    class Meta:
        app_label = 'maps'

class LayerGroup(IsDeleted,DateTimeStamp):
    theme=models.ForeignKey(Theme,on_delete=models.SET_NULL,null=True)
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)

    def __str__(self):
        return str(self.name)
    class Meta:
        app_label = 'maps'
        unique_together = (("theme", "name"),)


class Layer(IsDeleted,DateTimeStamp):
    theme=models.ForeignKey(Theme,on_delete=models.SET_NULL,null=True,related_name="layer_theme")
    group=models.ForeignKey(LayerGroup,on_delete=models.SET_NULL,null=True,blank=True,related_name='layer_group')
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)
    default_load=models.BooleanField(default=False)
    layer_type=models.CharField(max_length=20,choices=LAYER_TYPE_CHOICES)
    is_osm_layer=models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)
    class Meta:
        app_label = 'maps'

class LayerFile(DateTimeStamp):
    file = models.FileField(upload_to='shapefiles/%Y/%m/%d')
    layer=models.OneToOneField(Layer,on_delete=models.SET_NULL,null=True,blank=True,related_name='layer_file')

    def __str__(self):
        return str(self.id)
    class Meta:
        app_label = 'maps'

class SubLayer(IsDeleted,DateTimeStamp):
    layer=models.ForeignKey(Layer,on_delete=models.CASCADE,related_name='sub_layer')
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)
    icon = models.FileField(upload_to="icons",  blank=True, null=True)
    icon_size = models.JSONField(blank=True, null=True)
    style = models.JSONField(default=dict, blank=True, null=True)

    def __str__(self):
        return str(self.name)
    class Meta:
        app_label = 'maps'
        # ordering = ('order',)

class Vectorlayer(DateTimeStamp):
    layer=models.OneToOneField(Layer,on_delete=models.CASCADE,related_name="vector_layer")
    geom_type=models.CharField(max_length=20,choices=GEOMETRY_TYPE_CHOICES,blank=True,null=True) #geometry type of the layer
    bbox=ArrayField(models.FloatField(max_length=20, blank=True),
                               default=list,
                               size=4,
                               blank=True, null=True
                               )# bounding box in format minx,miny,maxx,maxy
    popup_fields=ArrayField(models.CharField(max_length=100, blank=True),
                               default=list,
                               size=100,
                               blank=True, null=True
                               ) # attributes list to display in feature popup
    popup_name_field=models.CharField(max_length=100,blank=True,null=True) # field name to display as title/name in popup

    sub_layers_mapping_field=models.CharField(max_length=100,blank=True,null=True) #field name on which basis sublayer is generated

    style = models.JSONField(default=dict, blank=True, null=True) #layer styling
    icon = models.FileField(upload_to="icons", blank=True, null=True) #icon for point datatype
    icon_size = models.JSONField(blank=True, null=True)

    show_label = models.BooleanField(default=False)
    label_field = models.CharField(max_length=100, blank=True, null=True) #field name on which basis feature is label
    label_style = models.JSONField(blank=True, null=True) #styling for feature label

    geoserver_workspace = models.CharField(
        max_length=500, blank=True, null=True)
    geoserver_layer_name = models.CharField(
        max_length=250, blank=True, null=True)

    def __str__(self):
        return f'{self.layer};id-{self.id}'
    class Meta:
        app_label = 'maps'

class RasterLayer(DateTimeStamp):
    layer=models.OneToOneField(Layer,on_delete=models.CASCADE,related_name="raster_layer")
    geoserver_workspace = models.CharField(
        max_length=100, blank=True, null=True)
    geoserver_layer_name = models.CharField(
        max_length=100, blank=True, null=True)
    sld=models.TextField(
        max_length=250, blank=True, null=True)

    class Meta:
        app_label = 'maps'




class WMSLayer(DateTimeStamp):
    layer=models.OneToOneField(Layer,on_delete=models.CASCADE,related_name="wms_layer")
    url=models.URLField()

    class Meta:
        app_label = 'maps'

class FeatureCollection(DateTimeStamp,IsDeleted):
    layer=models.ForeignKey(Layer,on_delete=models.CASCADE,related_name="layer_feature")
    attributes=models.JSONField(blank=True, null=True)
    geometry=md.GeometryField(srid=4326, blank=True, null=True)

    class Meta:
        app_label = 'maps'


class LayerAttribute(DateTimeStamp):
    layer=models.ForeignKey(Layer,on_delete=models.CASCADE)
    name=models.CharField(max_length=254)
    alias=models.CharField(max_length=254,blank=True,null=True)
    data_type=models.CharField(max_length=20,choices=DATA_TYPE_CHOICES,default='str')
    length=models.IntegerField(blank=True,null=True)
    precision=models.IntegerField(blank=True,null=True)
    unit=models.CharField(max_length=20,choices=UNIT_CHOICES,blank=True,null=True)
    class Meta:
        app_label = 'maps'
        unique_together = (("layer", "name"),)

    def clean(self):
        """
        Make sure proper fields are added
        """
        if (self.data_type=="str" or self.data_type=="int") and not self.length:
            # Raise a Validation error if length is empty when data_type equal to text or integer.
            raise ValidationError('length is missing')
        elif self.data_type=="float" and not (self.length or self.precision):
            # Raise a Validation error if length or precision is empty when data_type equal is decimal/float.
            raise ValidationError('length and precision should not be null')
