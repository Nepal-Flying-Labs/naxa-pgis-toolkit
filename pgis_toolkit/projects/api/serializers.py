from projects.models import OrganizationCategory, Organization, Project, DefaultTheme, LayerTemplate, LayerTemplateAttribute
from rest_framework import serializers

class OrganizationCategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationCategory
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

class OrganizationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationCategory
        fields = '__all__'

    def validate(self, data):
        if self.partial and OrganizationCategory.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
            raise serializers.ValidationError('Organization Category name must be unique')
        elif OrganizationCategory.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Organization Category name must be unique')
        return data

class OrganizationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'

    def validate(self, data):
        if self.partial and Organization.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
            raise serializers.ValidationError('Organization name must be unique')
        elif Organization.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Organization name must be unique')
        return data

class ProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'

    def validate(self, data):
        if self.partial and Project.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
            raise serializers.ValidationError('Project name must be unique')
        elif Project.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Project name must be unique')
        return data

class DefaultThemeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultTheme
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

class DefaultThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultTheme
        fields = '__all__'

    def validate(self, data):
        if self.partial and DefaultTheme.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
            raise serializers.ValidationError('Default Theme name must be unique')
        elif DefaultTheme.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Default Theme name must be unique')
        return data
        
class LayerTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplate
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

class LayerTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplate
        fields = '__all__'

    def validate(self, data):
        if self.partial and LayerTemplate.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
            raise serializers.ValidationError('Layer template name must be unique')
        elif LayerTemplate.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Layer template name must be unique')
        return data

class LayerTemplateAttributeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplateAttribute
        fields = '__all__'

class LayerTemplateAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerTemplateAttribute
        fields = '__all__'
