from django.urls import include, path
from rest_framework.routers import DefaultRouter

from pgis_toolkit.maps.api.views import (  # ReorderView,
    AdvanceFilterVectorTileQuerySet,
    FeatureCollectionViewset,
    LayerAPIView,
    LayerGroupViewset,
    LayerVectorTileQuerySet,
    ProjectLayerTemplateAttributeViewset,
    ProjectLayerTemplateViewset,
    StandardIconViewset,
    SubLayerViewset,
    ThemeViewset,
    get_layer_upload_task_response,
    import_template,
    layer_download,
    project_layers,
    project_theme_layers,
    reorder,
)

router = DefaultRouter()
router.register(r'theme', ThemeViewset, basename='theme')
router.register(r'standard_icon', StandardIconViewset, basename='standard_icon')
router.register(r'sub_layer', SubLayerViewset, basename='sub_layer')
router.register(r'feature_collection', FeatureCollectionViewset, basename='feature_collection')
router.register(r'layer_group', LayerGroupViewset, basename='layer_group')
router.register(r'project_layer_template', ProjectLayerTemplateViewset, basename='project_layer_template')
router.register(r'project_layer_template_attribute', ProjectLayerTemplateAttributeViewset, basename = 'project_layer_template_attribute')
app_name = "projects"
urlpatterns = [
    path('', include(router.urls)),
    path('project_layers/<int:id>/', project_layers, name='project_layers'),
    path('project_theme_layers/', project_theme_layers, name='project_theme_layers'),
    path('layer/', LayerAPIView.as_view(), name='layer'),
    path('layer/<int:pk>/', LayerAPIView.as_view(), name='layer_update'),
    path('get_layer_upload_task_response/', get_layer_upload_task_response),
    path('reorder/',reorder, name='reorder'),
    path('layer_vectortile/<int:z>/<int:x>/<int:y>/', LayerVectorTileQuerySet.as_view(), name='layer_vectortile'),
    path('layer_download/', layer_download, name='layer_download'),
    path('advance_filter_vectortile/<int:z>/<int:x>/<int:y>/', AdvanceFilterVectorTileQuerySet.as_view(), name="AdvanceFilterVectorTileQuerySet"),
    path('import_template/', import_template, name='import_template'),
]
