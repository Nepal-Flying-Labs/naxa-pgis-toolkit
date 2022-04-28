from django.urls import include, path
from rest_framework.routers import DefaultRouter

from pgis_toolkit.projects.api.views import (
    LayerTemplateAttributeViewset,
    LayerTemplateUploadAPIView,
    LayerTemplateViewset,
    layer_template_download,
)

router = DefaultRouter()

router.register(r'layer_template', LayerTemplateViewset, basename='later_template')
router.register(r'layer_template_attribute', LayerTemplateAttributeViewset, basename='layer_template_attribute')

app_name = "projects"
urlpatterns = [
    path('', include(router.urls)),
    path('layer_template_download/', layer_template_download,
         name='layer_template_download'),
]
