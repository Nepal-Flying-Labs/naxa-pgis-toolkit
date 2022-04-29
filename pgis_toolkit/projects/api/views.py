from django_filters.rest_framework import DjangoFilterBackend
from projects.api.serializers import *
from projects.models import OrganizationCategory, Organization, Project, DefaultTheme, LayerTemplate, LayerTemplateAttribute
from rest_framework import filters, status, viewsets

class OrganizationCategoryViewset(viewsets.ModelViewSet):
    queryset = OrganizationCategory.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = OrganizationCategorySerializer
    serializer_classes = {
        'list': OrganizationCategoryListSerializer,
        'retrieve': OrganizationCategorySerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class OrganizationViewset(viewsets.ModelViewSet):
    queryset = Organization.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = OrganizationSerializer
    serializer_classes = {
        'list': OrganizationListSerializer,
        'retrieve': OrganizationSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class ProjectViewset(viewsets.ModelViewSet):
    queryset = Project.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = ProjectSerializer
    serializer_classes = {
        'list': ProjectListSerializer,
        'retrieve': ProjectSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class DefaultThemeViewset(viewsets.ModelViewSet):
    queryset = Organization.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = OrganizationSerializer
    serializer_classes = {
        'list': DefaultThemeListSerializer,
        'retrieve': DefaultThemeSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class LayerTemplateViewset(viewsets.ModelViewSet):
    queryset = LayerTemplate.objects.all()
    http_method_names = ['get','post','patch']
    default_serializer_class = LayerTemplateSerializer
    serializer_classes={
        'list':LayerTemplateListSerializer,
        'retrieve':LayerTemplateSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class LayerTemplateAttributeViewset(viewsets.ModelViewSet):
    queryset = LayerTemplateAttribute.objects.all()
    http_method_names = ['get','post','patch','delete']
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('layer_template', )
    default_serializer_class = LayerTemplateAttributeSerializer
    serializer_classes={
        'list':LayerTemplateAttributeListSerializer,
        # 'retrieve':LayerTemplateAttributeSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)
