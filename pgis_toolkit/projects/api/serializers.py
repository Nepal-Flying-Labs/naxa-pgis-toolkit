from rest_framework import serializers

from pgis_toolkit.projects.models import (
    ContactPerson,
    DefaultTheme,
    Document,
    Image,
    LayerTemplate,
    LayerTemplateAttribute,
    Organization,
    OrganizationCategory,
    Project,
    RequestDemo,
)
from pgis_toolkit.users.models import UserRole


class OrganizationCategoryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationCategory
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

class OrganizationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationCategory
        fields = '__all__'

    def validate(self, data):
        if self.partial:
            if 'name' in data.keys() and OrganizationCategory.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
                raise serializers.ValidationError('Organization Category name must be unique')
            return data
        elif OrganizationCategory.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Organization Category name must be unique')
        return data

class OrganizationListSerializer(serializers.ModelSerializer):
    projects = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        exclude = ('address', 'contact', 'link', 'category', 'uploaded_date', 'last_updated', 'is_deleted')

    def get_projects(self, instance):
        return Project.active.select_related('organization').filter(organization__id=instance.id).count()

class OrganizationRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        exclude = ('uploaded_date', 'last_updated', 'is_deleted')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        project_qs = Project.active.select_related('organization').filter(organization__id=instance.id)
        representation['projects'] = project_qs.count()
        representation['ongoing'] = project_qs.filter(status__in=['draft', 'ongoing']).count()
        representation['completed'] = project_qs.filter(status='completed').count()
        contact_person_qs = ContactPerson.active.filter(organization=instance).values('id', 'name', 'email')
        representation['contact_person'] = contact_person_qs if contact_person_qs else []
        representation['users_count'] = UserRole.active.filter(organization=instance).count()
        return representation

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'

    def validate(self, data):
        if self.partial:
            if 'name' in data.keys() and Organization.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
                raise serializers.ValidationError('Organization name must be unique')
            return data
        elif Organization.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Organization name must be unique')
        return data

class ProjectListSerializer(serializers.ModelSerializer):
    # organization = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ('id', 'name', 'state', 'country', 'status', 'start_date', 'end_date', 'thematic_areas' , 'cover_image')
        # fields = ('id', 'name', 'description', 'start_date', 'end_date', 'geometry_type', 'bbox', 'organization', 'state', 'country')
        # exclude = ('uploaded_date', 'last_updated', 'is_deleted')

    # def get_organization(self, instance):
    #     return instance.organization.name

    def get_state(self, instance):
        return instance.state.all().values_list('name', flat=True)

    def get_country(self, instance):
        return instance.country.all().values_list('name', flat=True)

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'

    def validate(self, data):
        if self.partial:
            if 'name' in data.keys() and Project.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
                raise serializers.ValidationError('Project name must be unique')
            return data
        elif Project.active.filter(name=data['name']).exists():
            raise serializers.ValidationError('Project name must be unique')
        return data

class DefaultThemeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultTheme
        fields = '__all__'

class DefaultThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultTheme
        fields = '__all__'

    def validate(self, data):
        if self.partial:
            if 'name' in data.keys() and DefaultTheme.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
                raise serializers.ValidationError('Default Theme name must be unique')
            return data
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
        # Raise a Validation error if template name is not unique
        if self.partial:
            if 'name' in data.keys() and LayerTemplate.active.exclude(id=self.instance.id).filter(name=data['name']).exists():
                raise serializers.ValidationError('Layer template name must be unique')
            return data
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
        keys = data.keys()
        if self.partial:
            if 'layer_template' in keys and 'name' in keys and LayerTemplateAttribute.objects.exclude(id=self.instance.id).filter(layer_template=data['layer_template'],name=data['name']).exists():
                raise serializers.ValidationError('Attribute name must be unique for a layer template.')
            elif 'layer_template' in keys and LayerTemplateAttribute.objects.exclude(id=self.instance.id).filter(layer_template=data['layer_template'],name=self.instance.name).exists():
                raise serializers.ValidationError('Attribute name must be unique for a layer template.')
            elif 'name' in keys and LayerTemplateAttribute.objects.exclude(id=self.instance.id).filter(layer_template=self.instance.layer_template,name=data['name']).exists():
                raise serializers.ValidationError('Attribute name must be unique for a layer template.')
            return data
        elif LayerTemplateAttribute.objects.filter(layer_template=data['layer_template'],name=data['name']).exists():
            raise serializers.ValidationError('Attribute name must be unique for a layer template.')

        if (data['data_type']=="str" or data['data_type']=="int") and not data['length']:
            # Raise a Validation error if length is empty when data_type equal to text or integer.
            raise serializers.ValidationError('length is missing')
        elif data['data_type']=="float" and not (data['length '] or data['precision']):
            # Raise a Validation error if length or precision is empty when data_type equal is decimal/float.
            raise serializers.ValidationError('length and precision should not be null')
        return data

class DocumentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        exclude=('uploaded_date','last_updated', 'project')

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = '__all__'

class RequestDemoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestDemo
        fields = '__all__'

class ContactPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactPerson
        fields = '__all__'
