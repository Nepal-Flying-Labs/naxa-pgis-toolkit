from django.urls import include, path
from rest_framework.routers import DefaultRouter

from pgis_toolkit.projects.api.views import (OrganizationCategoryViewset, OrganizationViewset, ProjectViewset, DefaultThemeViewset, 
    LayerTemplateAttributeViewset,
    LayerTemplateViewset,
)

router = DefaultRouter()
router.register(r'organization_category', OrganizationCategoryViewset, basename='organization_category')
router.register(r'organization', OrganizationViewset, basename='organization')
router.register(r'project', ProjectViewset, basename='project')
router.register(r'default_theme', DefaultThemeViewset, basename='default_theme')
router.register(r'layer_template', LayerTemplateViewset, basename='later_template')
router.register(r'layer_template_attribute', LayerTemplateAttributeViewset, basename='layer_template_attribute')

app_name = "projects"
urlpatterns = [
    path('', include(router.urls)),
]
