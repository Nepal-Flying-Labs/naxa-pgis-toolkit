from rest_framework import serializers

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

class RasterLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = RasterLayer
        fields = '__all__'
        
class VectorLayerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vectorlayer
        exclude=('geom_type','bbox','geoserver_workspace','geoserver_layer_name')

class ThemeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        # fields = '__all__'
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

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
        fields = ('id',"name")

class SubLayerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubLayer
        fields = ('id','order','icon','icon_size','style')

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