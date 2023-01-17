import json

from attr import fields
from rest_framework import serializers

from pgis_toolkit.maps.models import *
from pgis_toolkit.maps.utils.project_style import get_style_detail


class LayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Layer
        fields = '__all__'
class LayerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Layer
        fields = ('id', 'name', 'source', 'status', 'display')

    def to_representation(self, instance):
        representation = super(LayerListSerializer,self).to_representation(instance)
        if instance.layer_type=='Vector':
            vector_layer = Vectorlayer.objects.filter(layer=instance).values('geom_type')
            if vector_layer.exists():
                representation['geom_type'] = vector_layer[0]['geom_type']
            feature_count = FeatureCollection.active.filter(layer=instance).count()
            representation['features'] = feature_count
        return representation


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
    theme = serializers.SerializerMethodField()
    layer = serializers.SerializerMethodField()

    class Meta:
        model = SubLayer
        fields = ('id',"name",'order','theme','layer','bbox')

    def to_representation(self, instance):
        representation = super(SubLayerRetrieveSerializer,self).to_representation(instance)
        layer_id=self.context.get('layer_id')
        project_style=self.context.get('project_style')
        icon,style,std_icon=get_style_detail(layer_id,instance.id,project_style)
        representation['icon']=icon
        representation['std_icon']=std_icon
        # representation['icon_size']=icon_size
        representation['style']=style
        return representation

    def get_theme(self, instance):
        try:
            return instance.layer.theme.id
        except:
            return None

    def get_layer(self, instance):
            return instance.layer.id if instance.layer else None



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

class NetworkRoutesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkRoutes
        fields = '__all__'

class QueryFeatureCollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryFeatureCollection
        fields = '__all__'

class QueryFeatureCollectionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryFeatureCollection
        fields = ('id',)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation |= instance.attributes
        return representation

class CleaningErrorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CleaningErrors
        fields = '__all__'

class FeatureCollectionMirrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureCollectionMirror
        fields= '__all__'

class NetworkRoutesObstaclesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkRoutes
        fields= ('id', 'route_no', 'length', 'travel_time', 'is_optimum')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        optimum_route_instance = OptimumRoute.active.get(analysis_id=instance.analysis_id)
        representation['origin'] = f'({optimum_route_instance.origin_long}, {optimum_route_instance.origin_lat})'
        representation['destination'] = f'({optimum_route_instance.destination_long}, {optimum_route_instance.destination_lat})'
        '''obstacles'''
        obstacles_list= []
        obstacles = instance.obstacles
        if obstacles:
            # obstacles = json.loads(obstacles)
            obstacles_json = {}
            for key, value in obstacles.items():
                layer = Layer.active.get(id=key)
                obstacles_json['layer_id'] = layer.id
                obstacles_json['feature_mirror_ids'] = value
                obstacles_json['layer_name'] = layer.name
                obstacles_json['count'] = len(value)
                obstacles_list.append(obstacles_json)
                obstacles_json = {}
        representation['obstacles'] = obstacles_list
        return representation

class NetworkRoutesObstaclesMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkRoutes
        fields= ('id', 'route_no', 'is_optimum')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        '''obstacles'''
        obstacles_list= []
        obstacles = instance.obstacles
        if obstacles:
            # obstacles = json.loads(obstacles)
            obstacles_json = {}
            for key, value in obstacles.items():
                layer = Layer.active.get(id=key)
                obstacles_json['layer_id'] = layer.id
                obstacles_json['feature_mirror_ids'] = value
                obstacles_list.append(obstacles_json)
                obstacles_json = {}
        representation['obstacles'] = obstacles_list
        return representation

class AnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analysis
        fields = '__all__'
