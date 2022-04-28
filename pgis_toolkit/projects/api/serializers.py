from projects.models import LayerTemplate, LayerTemplateAttribute
from rest_framework import serializers


class LayerTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplate
        exclude=('uploaded_date','last_updated','is_deleted')

class LayerTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplate
        fields = '__all__'

class LayerTemplateAttributeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplateAttribute
        exclude=('uploaded_date','last_updated')

class LayerTemplateAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplateAttribute
        fields = '__all__'
