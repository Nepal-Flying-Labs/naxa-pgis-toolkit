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

    def validate(self, data):
        # Raise a Validation error if template name is not unique
        if self.partial:
            if LayerTemplate.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
                raise serializers.ValidationError('Layer template name must be unique')
        elif LayerTemplate.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Layer template name must be unique')
        return data

class LayerTemplateAttributeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplateAttribute
        exclude=('uploaded_date','last_updated')

class LayerTemplateAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplateAttribute
        fields = '__all__'

    def validate(self,data):
        """
        Make sure proper fields are added
        """
        # Raise a Validation error if field name within layer is not unique
        if self.partial:
            if LayerTemplateAttribute.objects.exclude(id=self.instance.id).filter(layer_template=data['layer_template'],name=data['name']).exists():
                raise serializers.ValidationError('Layer template name must be unique')
        elif LayerTemplateAttribute.objects.filter(layer_template=data['layer_template'],name=data['name']).exists():
            raise serializers.ValidationError('Layer template name must be unique')

        if (data['data_type']=="str" or data['data_type']=="int") and not data['length']:
            # Raise a Validation error if length is empty when data_type equal to text or integer.
            raise serializers.ValidationError('length is missing')
        elif data['data_type']=="float" and not (data['length '] or data['precision']):
            # Raise a Validation error if length or precision is empty when data_type equal is decimal/float.
            raise serializers.ValidationError('length and precision should not be null')
        return data
