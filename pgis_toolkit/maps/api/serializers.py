from attr import fields
from rest_framework import serializers

from pgis_toolkit.maps.functions import get_style_detail
from pgis_toolkit.maps.models import *


class LayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Layer
        fields = '__all__'

class LayerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Layer
        exclude=('layer_type',)

class WMSLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WMSLayer
        fields = '__all__'

class VectorLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vectorlayer
        fields = '__all__'

class VectorLayerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vectorlayer
        exclude=('geom_type','bbox','geoserver_workspace','geoserver_layer_name')

class RasterLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = RasterLayer
        fields = '__all__'

class ThemeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        exclude = ('uploaded_date', 'last_updated', 'is_deleted','project','order')

class ThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        fields = '__all__'

class SubLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubLayer
        fields = '__all__'

class SubLayerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubLayer
        fields = ('id',"name",'order')


class SubLayerRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubLayer
        fields = ('id',"name",'order')

    def to_representation(self, instance):
        representation = super(SubLayerRetrieveSerializer,self).to_representation(instance)
        layer_id=self.context.get('layer_id')
        project_style=self.context.get('project_style')
        icon,icon_size,style,std_icon=get_style_detail(layer_id,instance.id,project_style)
        representation['icon']=icon
        representation['std_icon']=std_icon
        representation['icon_size']=icon_size
        representation['style']=style
        return representation


class SubLayerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubLayer
        fields = ('id','order','icon','icon_size','style','std_icon')

class FeatureCollectionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureCollection
        fields = ('id',)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation |= instance.attributes
        return representation

class FeatureCollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureCollection
        fields= '__all__'

class LayerGroupListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerGroup
        exclude = ('uploaded_date', 'last_updated', 'is_deleted','theme','order')

class LayerGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerGroup
        fields = '__all__'

class ProjectLayerTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectsLayerTemplate
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

class ProjectLayerTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectsLayerTemplate
        fields = '__all__'

class ProjectsLayerTemplateAttributeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectsLayerTemplateAttribute
        exclude = ('uploaded_date', 'last_updated')

class ProjectsLayerTemplateAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectsLayerTemplateAttribute
        fields = '__all__'

class ProjectStyleListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectStyle
        fields = ['id','name']

class ProjectStyleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectStyle
        fields = '__all__'

class StandardIconListSerializer(serializers.ModelSerializer):
    class Meta:
        model = StandardIcon
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')
class LayerAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerAttribute
        exclude = ('uploaded_date', 'last_updated')

class LayerAttributeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerAttribute
        fields=['id','name','alias']
