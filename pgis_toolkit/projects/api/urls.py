from django.urls import include, path
from rest_framework.routers import DefaultRouter

from pgis_toolkit.projects.api.views import (
    DefaultThemeViewset,
    DocumentViewset,
    LayerTemplateAttributeViewset,
    LayerTemplateUploadAPIView,
    LayerTemplateViewset,
    OrganizationCategoryViewset,
    OrganizationViewset,
    ProjectLocationVectorTileQuerySet,
    ProjectViewset,
    RequestDemoViewset,
    document_download,
    get_country_choices,
    get_project_detail,
    get_state_choices,
    layer_template_download,
)

router = DefaultRouter()
router.register(r'organization_category', OrganizationCategoryViewset, basename='organization_category')
router.register(r'organization', OrganizationViewset, basename='organization')
router.register(r'project', ProjectViewset, basename='project')
router.register(r'default_theme', DefaultThemeViewset, basename='default_theme')
router.register(r'layer_template', LayerTemplateViewset, basename='later_template')
router.register(r'layer_template_attribute', LayerTemplateAttributeViewset, basename='layer_template_attribute')
router.register(r'document', DocumentViewset, basename='document')
router.register(r'request_demo', RequestDemoViewset, basename='request_demo')

app_name = "projects"
urlpatterns = [
    path('', include(router.urls)),
    path('layer_template_download/', layer_template_download,
         name='layer_template_download'),
    path('layer_template_upload/', LayerTemplateUploadAPIView.as_view(), name='layer_template_upload'),
    path('project_location_vectortile/<int:z>/<int:x>/<int:y>/', ProjectLocationVectorTileQuerySet.as_view(), name='project_location_vectortile'),
    path('document_download/', document_download, name='document_download'),
    path('project_detail/', get_project_detail, name='project_detail'),
    path('country/', get_country_choices, name='country_choices'),
    path('state/', get_state_choices, name='state_choices'),


]
