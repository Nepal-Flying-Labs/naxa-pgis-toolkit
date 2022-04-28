from projects.models import LayerTemplate, LayerTemplateAttribute
from rest_framework import serializers


class LayerTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplate
        exclude=('created_date','updated_date','is_deleted')

class LayerTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplate
        fields = '__all__'

class LayerTemplateAttributeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplateAttribute
        exclude=('created_date','updated_date')

class LayerTemplateAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplateAttribute
        fields = '__all__'
