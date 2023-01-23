from datetime import MAXYEAR

from django.contrib.gis.db import models as md
from django.contrib.gis.db.models import Extent
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _

from config.settings.base import MONGO_DB, env
from pgis_toolkit.projects.models import (
    DateTimeStamp,
    IsDeleted,
    Project,
    Template,
    TemplateAttribute,
)
from pgis_toolkit.utils.constants import (
    ANALYSIS_TYPE_CHOICES,
    DATA_TYPE_CHOICES,
    GEOMETRY_TYPE_CHOICES,
    LAYER_SOURCE_CHOICES,
    LAYER_STATUS_CHOICES,
    LAYER_TYPE_CHOICES,
    LAYER_UPLOAD_STATUS,
    NETWORK_MODE,
    UNIT_CHOICES,
)
from pgis_toolkit.utils.validators import (
    validate_icon_extension,
    validate_std_icon_extension,
)


# Create your models here.
class Theme(IsDeleted,DateTimeStamp):
    project=models.ForeignKey(Project, related_name='ThemeProject', on_delete=models.CASCADE,null=True)
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(default=0)
    description=models.TextField(blank=True,null=True)

    def __str__(self):
        return f'{self.id} {self.name}'
    class Meta:
        app_label = 'maps'

class LayerGroup(IsDeleted,DateTimeStamp):
    theme=models.ForeignKey(Theme,on_delete=models.SET_NULL,null=True)
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.id} {self.name}'
    class Meta:
        app_label = 'maps'
        unique_together = (("theme", "name"),)

class Category(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return f'{self.id} {self.name}'
    class Meta:
        app_label = 'maps'

class Layer(IsDeleted,DateTimeStamp):
    theme=models.ForeignKey(Theme,on_delete=models.SET_NULL,null=True,related_name="layer_theme")
    group=models.ForeignKey(LayerGroup,on_delete=models.SET_NULL,null=True,blank=True,related_name='layer_group')
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(default=0)
    default_load=models.BooleanField(default=False)
    layer_type=models.CharField(max_length=20,choices=LAYER_TYPE_CHOICES)
    is_osm_layer=models.BooleanField(default=False)
    display_on_map=models.BooleanField(default=True) #add to map
    status = models.CharField(max_length=20, default='unchecked', choices=LAYER_STATUS_CHOICES)
    source = models.CharField(max_length=20, choices=LAYER_SOURCE_CHOICES, blank=True, null=True)
    # category = models.ForeignKey(Category, on_delete=models.SET_NULL, related_name='LayerCategory', blank=True, null=True)
    upload_status = models.CharField(max_length=20, default='uploading', choices=LAYER_UPLOAD_STATUS)
    is_clean = models.BooleanField(default=False) #data cleaned or not

    def __str__(self):
        return f'{self.id} {self.name}'
    class Meta:
        app_label = 'maps'
        permissions = (
            ('download_layer', 'Can download layer'),
        )

    @property
    def vector_layer(self):
        if self.id:
            return Vectorlayer.objects.select_related('layer').get(layer=self.id)
        return Vectorlayer.objects.none()

    @property
    def raster_layer(self):
        if self.id:
            return RasterLayer.objects.select_related('layer').get(layer=self.id)
        return RasterLayer.objects.none()

    @property
    def wms_layer(self):
        if self.id:
            return WMSLayer.objects.select_related('layer').get(layer=self.id)
        return WMSLayer.objects.none()

class LayerFile(DateTimeStamp):
    file = models.FileField(upload_to='geofiles/%Y/%m/%d')
    layer=models.OneToOneField(Layer,on_delete=models.SET_NULL,null=True,blank=True,related_name='layer_file')

    def __str__(self):
        return str(self.id)
    class Meta:
        app_label = 'maps'

class StandardIcon(DateTimeStamp,IsDeleted):
    name=models.CharField(max_length=50,blank=True,null=True)
    icon=models.FileField(upload_to="standard_icons/",validators=[validate_std_icon_extension])
    class Meta:
        app_label = 'maps'

    def __str__(self):
        return f'{self.id} {self.name}'

class Vectorlayer(DateTimeStamp):
    layer=models.OneToOneField(Layer,on_delete=models.CASCADE,related_name="vector_layer")
    geom_type=models.CharField(max_length=20,choices=GEOMETRY_TYPE_CHOICES,blank=True,null=True) #geometry type of the layer
    # bbox=ArrayField(models.FloatField(max_length=20, blank=True),
    #                            default=list,
    #                            size=4,
    #                            blank=True, null=True
    #                            )# bounding box in format minx,miny,maxx,maxy
    bbox = models.JSONField(default=list, blank=True, null=True) #layer styling
    mandatory_fields=ArrayField(models.CharField(max_length=100, blank=True),
                               default=list,
                               size=100,
                               blank=True, null=True
                               ) # attributes list to display required fields in feature create
    popup_fields=ArrayField(models.CharField(max_length=100, blank=True),
                               default=list,
                               size=100,
                               blank=True, null=True
                               ) # attributes list to display in feature popup
    popup_name_field=models.CharField(max_length=100,blank=True,null=True) # field name to display as title/name in popup

    sub_layers_mapping_field=models.CharField(max_length=100,blank=True,null=True) #field name on which basis sublayer is generated

    style = models.JSONField(default=dict, blank=True, null=True) #layer styling
    icon = models.FileField(upload_to="icons", blank=True, null=True,validators=[validate_icon_extension]) #icon for point datatype
    icon_size = models.JSONField(default=dict,blank=True, null=True)
    # icon_url=models.URLField(blank=True,null=True)
    std_icon=models.ForeignKey(StandardIcon,on_delete=models.SET_NULL,related_name="layer_std_icon",blank=True,null=True)

    show_label = models.BooleanField(default=False)
    label_field = models.CharField(max_length=100, blank=True, null=True) #field name on which basis feature is label
    label_style = models.JSONField(blank=True, null=True) #styling for feature label

    geoserver_workspace = models.CharField(
        max_length=500, blank=True, null=True)
    geoserver_layer_name = models.CharField(
        max_length=250, blank=True, null=True)

    def __str__(self):
        return f'{self.id} {self.layer}'
    class Meta:
        app_label = 'maps'

class RasterLayer(DateTimeStamp):
    layer=models.OneToOneField(Layer,on_delete=models.CASCADE,related_name="raster_layer")
    geoserver_workspace = models.CharField(
        max_length=100, blank=True, null=True)
    geoserver_layer_name = models.CharField(
        max_length=100, blank=True, null=True)
    sld=models.TextField(blank=True, null=True)

    class Meta:
        app_label = 'maps'




class WMSLayer(DateTimeStamp):
    layer=models.OneToOneField(Layer,on_delete=models.CASCADE,related_name="wms_layer")
    url=models.URLField(max_length=1000)

    class Meta:
        app_label = 'maps'


class SubLayer(IsDeleted,DateTimeStamp):
    layer=models.ForeignKey(Layer,on_delete=models.CASCADE,related_name='sub_layer')
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(default=0)
    icon = models.FileField(upload_to="icons",  blank=True, null=True)
    icon_size = models.JSONField(blank=True, null=True)
    style = models.JSONField(default=dict, blank=True, null=True)
    std_icon=models.ForeignKey(StandardIcon,on_delete=models.SET_NULL,related_name="sublayer_std_icon",blank=True,null=True)
    bbox = models.JSONField(default=list, blank=True, null=True)

    def __str__(self):
        return f'{self.id} {self.name}'

    def refresh(obj):
        """ Reload an object from the database """
        return obj.__class__._default_manager.get(pk=obj.pk)

    class Meta:
        app_label = 'maps'
        # ordering = ('order',)


class FeatureCollection(DateTimeStamp,IsDeleted):
    layer=models.ForeignKey(Layer,on_delete=models.CASCADE,related_name="layer_feature")
    sub_layer=models.ForeignKey(SubLayer,on_delete=models.SET_NULL,blank=True,null=True,related_name="sublayer_feature")
    attributes=models.JSONField(blank=True, null=True)
    geometry=md.GeometryField(srid=4326, blank=True, null=True)

    class Meta:
        app_label = 'maps'

    def refresh(obj):
        """ Reload an object from the database """
        return obj.__class__._default_manager.get(pk=obj.pk)

    def save(self, *args, **kwargs):
        '''Update box of vectorlayer'''
        try:
            if self.geometry:
                if self.geometry.geom_type=="Point":
                    coords=self.geometry.coords
                    feature_bbox =[coords[0],coords[1],coords[0],coords[1]]
                else:
                    # feature=FeatureCollection.active.filter(id=self.id).aggregate(Extent('geometry'))
                    # feature_bbox = list(feature['geometry__extent']) if feature['geometry__extent'] else None
                    feature_bbox=self.geometry.extent
                vector_layer_instance=Vectorlayer.objects.get(layer=self.layer)
                layer_bbox= vector_layer_instance.bbox

                sub_layer_instance=SubLayer.objects.get(id=self.sub_layer.id) if self.sub_layer else None
                sub_layer_bbox= sub_layer_instance.bbox if sub_layer_instance else None

                if layer_bbox and feature_bbox:
                    if feature_bbox[0]<layer_bbox[0]:
                        layer_bbox[0]=feature_bbox[0]

                    if feature_bbox[1]<layer_bbox[1]:
                        layer_bbox[1]=feature_bbox[1]

                    if feature_bbox[2]>layer_bbox[2]:
                        layer_bbox[2]=feature_bbox[2]

                    if feature_bbox[3]>layer_bbox[3]:
                        layer_bbox[3]=feature_bbox[3]

                    # else:
                    #     print("no case satisfies")
                    vector_layer_instance.bbox=layer_bbox
                elif feature_bbox:
                    vector_layer_instance.bbox=feature_bbox

                if sub_layer_bbox and feature_bbox:
                    if sub_layer_bbox[0] < layer_bbox[0]:
                        sub_layer_bbox[0]=feature_bbox[0]

                    if sub_layer_bbox[1] < layer_bbox[1]:
                        sub_layer_bbox[1]= feature_bbox[1]

                    if sub_layer_bbox[2] > layer_bbox[2]:
                        sub_layer_bbox[2]=feature_bbox[2]

                    if sub_layer_bbox[3]>layer_bbox[3]:
                        sub_layer_bbox[3]=feature_bbox[3]

                    # else:
                    #     print("sub no case satisfies")
                    sub_layer_instance.bbox=sub_layer_bbox
                elif sub_layer_instance and feature_bbox:
                    sub_layer_instance.bbox=feature_bbox
                '''save bbox'''
                vector_layer_instance.save()
                if sub_layer_instance:
                    sub_layer_instance.save()
            super(FeatureCollection, self).save(*args, **kwargs)
            feature = FeatureCollection.active.filter(id=self.id).values('id', 'layer', 'sub_layer', 'attributes')[0]
            if feature:
                feature_coll = MONGO_DB['featurecollections']
                feature_count = feature_coll.count_documents({'id':feature['id']})
                if feature_count == 0:
                    feature_coll.insert_one(feature)
                else:
                    feature_coll.update_one({'id': feature['id']}, {'$set': feature})
                # Print on the terminal
                # qs = feature_coll.find({'id':feature['id']})
                # for r in qs:
                #     print(r["id"], r["layer"], r["sub_layer"], r["attributes"])


        except Exception as e:
            print(f'error in def save of feature collection: {str(e)}')

class FeatureCollectionMirror(DateTimeStamp,IsDeleted):
    feature = models.ForeignKey(FeatureCollection, on_delete=models.CASCADE, blank=True, null=True, related_name="feature")
    layer=models.ForeignKey(Layer,on_delete=models.CASCADE,related_name="layer_feature_mirror")
    sub_layer=models.ForeignKey(SubLayer,on_delete=models.SET_NULL,blank=True,null=True,related_name="sublayer_feature_mirror")
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


class ProjectsLayerTemplate(Template,IsDeleted,DateTimeStamp):
    selected = models.BooleanField(default=False)
    project=models.ForeignKey(Project,on_delete=models.CASCADE)
    class Meta:
        app_label = 'maps'

    def __str__(self):
        return f'{self.id} {self.name}'


class ProjectsLayerTemplateAttribute(IsDeleted, DateTimeStamp,TemplateAttribute):
    selected = models.BooleanField(default=True)
    layer_template=models.ForeignKey(ProjectsLayerTemplate,on_delete=models.CASCADE)
    class Meta:
        app_label = 'maps'
        unique_together = (("layer_template", "name"),)

class ProjectStyle(DateTimeStamp,IsDeleted):
    project=models.ForeignKey(Project,on_delete=models.CASCADE)
    name=models.CharField(max_length=50)

    class Meta:
        app_label = 'maps'

    def __str__(self):
        return f'{self.id} {self.name}'

class LayerStyle(DateTimeStamp,IsDeleted):
    project_style=models.ForeignKey(ProjectStyle,on_delete=models.CASCADE,blank=True,null=True)
    layer=models.ForeignKey(Layer,on_delete=models.CASCADE)
    style = models.JSONField(default=dict, blank=True, null=True) #layer styling
    icon = models.FileField(upload_to="icons", blank=True, null=True,validators=[validate_std_icon_extension]) #icon for point datatype
    # icon_size = models.JSONField(default=dict,blank=True, null=True)
    std_icon=models.ForeignKey(StandardIcon,on_delete=models.SET_NULL,related_name="layer_style_std_icon",blank=True,null=True)

    class Meta:
        app_label = 'maps'

    @property
    def get_icon_url(self):
        return f'{env("BACKEND_URL")}{self.icon.url}' if self.icon else None
    @property
    def get_std_icon_url(self):
        return f'{env("BACKEND_URL")}{self.std_icon.icon.url}' if self.std_icon else None

class SubLayerStyle(DateTimeStamp,IsDeleted):
    project_style=models.ForeignKey(ProjectStyle,on_delete=models.CASCADE,blank=True,null=True)
    sub_layer=models.ForeignKey(SubLayer,on_delete=models.CASCADE)
    style = models.JSONField(default=dict, blank=True, null=True) #layer styling
    icon = models.FileField(upload_to="icons", blank=True, null=True,validators=[validate_std_icon_extension]) #icon for point datatype
    # icon_size = models.JSONField(default=dict,blank=True, null=True)
    std_icon=models.ForeignKey(StandardIcon,on_delete=models.SET_NULL,related_name="sublayer_style_std_icon",blank=True,null=True)

    class Meta:
        app_label = 'maps'

    @property
    def get_icon_url(self):
        return f'{env("BACKEND_URL")}{self.icon.url}' if self.icon else None
    @property
    def get_std_icon_url(self):
        return f'{env("BACKEND_URL")}{self.std_icon.icon.url}' if self.std_icon else None

class ProjectMapConfig(DateTimeStamp,IsDeleted):
    project = models.IntegerField(db_index=True)
    map_config = models.JSONField(default=dict, blank=True, null=True)
    user = models.IntegerField(db_index=True, blank=True, null=True)

    class Meta:
        app_label = 'maps'

'''similar to Layer'''
class Analysis(DateTimeStamp,IsDeleted):
    name = models.CharField(max_length=254)
    project = models.IntegerField(db_index=True)
    display = models.BooleanField(default=False)
    type = models.CharField(max_length=100, choices=ANALYSIS_TYPE_CHOICES)
    geom_type = models.CharField(max_length=20, choices=GEOMETRY_TYPE_CHOICES, blank=True, null=True)
    bbox = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        app_label = 'maps'

class OptimumRoute(DateTimeStamp,IsDeleted):
    analysis_id = models.IntegerField(db_index=True, blank=True, null=True)
    road_network = models.IntegerField(null=True, blank=True) #layer
    mode = models.CharField(max_length=100, choices=NETWORK_MODE)
    paths = models.IntegerField(null=True, blank=True)
    origin_long = models.FloatField(max_length=20, null=True, blank=True)
    origin_lat = models.FloatField(max_length=20, null=True, blank=True)
    destination_long = models.FloatField(max_length=20, null=True, blank=True)
    destination_lat = models.FloatField(max_length=20, null=True, blank=True)
    route_origin = models.JSONField(default=list, blank=True, null=True)
    route_destination = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        app_label = 'maps'

'''Shortest Paths'''
class NetworkRoutes(DateTimeStamp,IsDeleted):
    analysis_id = models.IntegerField(db_index=True, blank=True, null=True)
    route_no = models.IntegerField(blank=True, null=True)
    geometry=md.GeometryField(srid=4326)
    length = models.FloatField(max_length=10, verbose_name='Length in meters')
    travel_time = models.FloatField(max_length=10, verbose_name='Travel Time in seconds')
    is_optimum = models.BooleanField(default=False)
    obstacles = models.JSONField(default=dict, blank=True, null=True)
    style = models.JSONField(default=dict, blank=True, null=True) #route style
    bbox = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        app_label = 'maps'

    # def save(self, *args, **kwargs):
    #     '''Update bbox of Analysis'''
    #     try:
    #         if self.geometry:
    #             route=NetworkRoutes.active.filter(id=self.id).aggregate(Extent('geometry'))
    #             route_bbox = list(route['geometry__extent']) if route['geometry__extent'] else None

    #             analysis_instance=Analysis.active.get(id=self.analysis_id)
    #             analysis_bbox= analysis_instance.bbox

    #             if analysis_bbox and route_bbox:
    #                 if route_bbox[0]<analysis_bbox[0]:
    #                     analysis_bbox[0]=route_bbox[0]

    #                 if route_bbox[1]<analysis_bbox[1]:
    #                     analysis_bbox[1]=route_bbox[1]

    #                 if route_bbox[2]>analysis_bbox[2]:
    #                     analysis_bbox[2]=route_bbox[2]

    #                 if route_bbox[3]>analysis_bbox[3]:
    #                     analysis_bbox[3]=route_bbox[3]

    #             elif route_bbox:
    #                 analysis_instance.bbox=route_bbox
    #             analysis_instance.save()
    #     except Exception as e:
    #         print(f'error in def save of NetworkRoutes: {str(e)}')
    #     super(NetworkRoutes, self).save(*args, **kwargs)

class ServiceAreaAnalysis(DateTimeStamp, IsDeleted):
    analysis_id = models.IntegerField(db_index=True, blank=True, null=True)
    class Meta:
        app_label = 'maps'

class BufferAnalysis(DateTimeStamp, IsDeleted):
    analysis_id = models.IntegerField(db_index=True, blank=True, null=True)
    origins = models.JSONField(default=list, blank=True, null=True)
    radius = models.FloatField(max_length=10, blank=True, null=True, verbose_name='Length in meters')
    dissolve_output = models.BooleanField(default=False)
    total_area = models.FloatField(null=True, blank=True, verbose_name='Area in meter square')

    class Meta:
        app_label = 'maps'

class BufferAreas(DateTimeStamp, IsDeleted):
    analysis_id = models.IntegerField(db_index=True, blank=True, null=True)
    geometry=md.GeometryField(srid=4326)
    area = models.FloatField(null=True, blank=True, verbose_name='Area in meter square')
    bbox = models.JSONField(default=list, blank=True, null=True)
    pois = models.JSONField(default=dict, blank=True, null=True)
    class Meta:
        app_label = 'maps'

'''Celery Task'''
class CeleryTask(models.Model):
    task_id = models.UUIDField()
    layer_id = models.IntegerField(db_index=True, blank=True, null=True)

    class Meta:
        app_label = 'maps'

class QueryLayer(IsDeleted, DateTimeStamp):
    theme=models.ForeignKey(Theme,on_delete=models.SET_NULL,null=True,related_name="querylayer_theme")
    group=models.ForeignKey(LayerGroup,on_delete=models.SET_NULL,null=True,blank=True,related_name='querylayer_group')
    name=models.CharField(max_length=254)
    display_on_map=models.BooleanField(default=True) #add to map
    source = models.CharField(max_length=20, choices=LAYER_SOURCE_CHOICES, blank=True, null=True)
    icon = models.FileField(upload_to="icons", blank=True, null=True,validators=[validate_icon_extension]) #icon for point datatype
    bbox = models.JSONField(default=list, blank=True, null=True) #layer styling
    geom_type=models.CharField(max_length=20,choices=GEOMETRY_TYPE_CHOICES,blank=True,null=True) #geometry type of the layer
    std_icon=models.ForeignKey(StandardIcon,on_delete=models.SET_NULL,related_name="querylayer_std_icon",blank=True,null=True)
    style = models.JSONField(default=dict, blank=True, null=True) #layer styling

    class Meta:
        app_label = 'maps'

class QueryFeatureCollection(DateTimeStamp,IsDeleted):
    layer=models.ForeignKey(QueryLayer,on_delete=models.CASCADE,related_name="querylayer_feature")
    attributes=models.JSONField(blank=True, null=True)
    geometry=md.GeometryField(srid=4326, blank=True, null=True)

    class Meta:
        app_label = 'maps'

    # def save(self, *args, **kwargs):
    #     '''Update bbox of QueryFeatureCollection'''
    #     try:
    #         if self.geometry:
    #             if self.geometry.geom_type=="Point":
    #                 coords=self.geometry.coords
    #                 feature_bbox =[coords[0],coords[1],coords[0],coords[1]]
    #             else:
    #                 feature_bbox = self.geometry.extent

    #             layer_instance=QueryLayer.active.get(id=self.layer.id)
    #             layer_bbox= layer_instance.bbox

    #             if layer_bbox and feature_bbox:
    #                 if feature_bbox[0]<layer_bbox[0]:
    #                     layer_bbox[0]=feature_bbox[0]

    #                 if feature_bbox[1]<layer_bbox[1]:
    #                     layer_bbox[1]=feature_bbox[1]

    #                 if feature_bbox[2]>layer_bbox[2]:
    #                     layer_bbox[2]=feature_bbox[2]

    #                 if feature_bbox[3]>layer_bbox[3]:
    #                     layer_bbox[3]=feature_bbox[3]

    #             elif feature_bbox:
    #                 layer_instance.bbox=list(feature_bbox)
    #             layer_instance.save()
    #     except Exception as e:
    #         print(f'error in def save of QueryFeatureCollection: {str(e)}')
    #     super(QueryFeatureCollection, self).save(*args, **kwargs)


class CleaningErrors(DateTimeStamp):
    """
    layer_id > Layer

    remaining fields stores ids > FeatureCollectionMirror object ids
    """
    layer_id = models.IntegerField(db_index=True, unique=True, blank=True, null=True)
    null =ArrayField(models.IntegerField(blank=True, null=True), default=list, size=2000, blank=True, null=True)
    multipart =ArrayField(models.IntegerField(blank=True, null=True), default=list, size=2000, blank=True, null=True)
    duplicate=ArrayField(models.IntegerField(blank=True, null=True), default=list, size=2000, blank=True, null=True)
    overlap=ArrayField(models.IntegerField(blank=True, null=True), default=list, size=2000, blank=True, null=True)
    self_instersect =ArrayField(models.IntegerField(blank=True, null=True), default=list, size=2000, blank=True, null=True)
    snapping =ArrayField(models.IntegerField(blank=True, null=True), default=list, size=2000, blank=True, null=True)

    class Meta:
        app_label = 'maps'
