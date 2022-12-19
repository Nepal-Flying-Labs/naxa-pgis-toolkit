from django.urls import include, path
from rest_framework.routers import DefaultRouter

from pgis_toolkit.maps.api.views import (  # ReorderView,; project_layers,
    AdvanceFilterVectorTileQuerySet,
    AdvanceQueryAPIView,
    DataMergeUpdateAPIView,
    FeatureCollectionViewset,
    FeatureGeoJSONAPIView,
    LayerAttributeViewset,
    LayerFromQueryAPIView,
    LayerGroupViewset,
    LayerVectorTileQuerySet,
    LayerViewSet,
    ProjectLayerTemplateAttributeViewset,
    ProjectLayerTemplateViewset,
    ProjectMapConfigAPIView,
    ProjectStyleViewset,
    QueryFeatureCollectionViewset,
    ShortestPathAPIView,
    ShortestRoutesTileQuerySet,
    StandardIconViewset,
    SubLayerViewset,
    ThemeViewset,
    analysis_layers,
    category,
    delete_sequence,
    feature_popup,
    get_analysis_task_response,
    get_data_merge_update_task_response,
    get_layer_upload_task_response,
    import_template,
    layer_download,
    project_theme_layers,
    reorder,
    check_layer,
    dry_fix_layer,
    fix_layer,
)

router = DefaultRouter()
router.register(r'theme', ThemeViewset, basename='theme')
router.register(r'project_style', ProjectStyleViewset, basename='project_style')
router.register(r'standard_icon', StandardIconViewset, basename='standard_icon')
router.register(r'layer', LayerViewSet, basename='layer')
router.register(r'sub_layer', SubLayerViewset, basename='sub_layer')
router.register(r'feature_collection', FeatureCollectionViewset, basename='feature_collection')
router.register(r'layer_group', LayerGroupViewset, basename='layer_group')
router.register(r'project_layer_template', ProjectLayerTemplateViewset, basename='project_layer_template')
router.register(r'project_layer_template_attribute', ProjectLayerTemplateAttributeViewset, basename = 'project_layer_template_attribute')
router.register(r'layer_attribute', LayerAttributeViewset, basename = 'layer attributes')
router.register(r'query_feature_collection', QueryFeatureCollectionViewset, basename='query_feature_collection')

app_name = "projects"

urlpatterns = [
    path('', include(router.urls)),
    # path('project_layers/<int:id>/', project_layers, name='project_layers'),
    path('project_theme_layers/', project_theme_layers, name='project_theme_layers'),
    # path('layer/', LayerAPIView.as_view(), name='layer'),
    # path('layer/<int:pk>/', LayerAPIView.as_view(), name='layer_update'),
    path('get_layer_upload_task_response/', get_layer_upload_task_response),
    path('reorder/',reorder, name='reorder'),
    path('layer_vectortile/<int:z>/<int:x>/<int:y>/', LayerVectorTileQuerySet.as_view(), name='layer_vectortile'),
    path('layer_download/', layer_download, name='layer_download'),
    path('advance_filter_vectortile/<int:z>/<int:x>/<int:y>/', AdvanceFilterVectorTileQuerySet.as_view(), name="AdvanceFilterVectorTileQuerySet"),
    path('import_template/', import_template, name='import_template'),
    path('feature/<int:pk>/', FeatureGeoJSONAPIView.as_view(), name='feature'),
    path('data_merge_update/', DataMergeUpdateAPIView.as_view(), name='data_merge_update'),
    path('get_data_merge_update_task_response/', get_data_merge_update_task_response),
    path('shortest_distance_analysis/', ShortestPathAPIView.as_view(), name='shortest_distance_analysis'),
    path('get_analysis_task_response/', get_analysis_task_response),
    path('shortest_routes_vectortile/<int:z>/<int:x>/<int:y>/', ShortestRoutesTileQuerySet.as_view(), name='NetworkRoutesTileQuerySet'),
    path('feature_popup/', feature_popup, name='feature_popup'),
    path('analysis_layers/', analysis_layers, name='analysis_layers'),
    path('map_config/', ProjectMapConfigAPIView.as_view(), name='map_config'),
    path('check_layer/', check_layer, name='check_layer'),
    path('dry_fix_layer', dry_fix_layer, name="dry_fix_layer"),
    path('fix_layer', fix_layer, name='fix_layer'),
    path('advance_query/', AdvanceQueryAPIView.as_view(), name='advance_query'),
    path('layer_from_query/', LayerFromQueryAPIView.as_view(), name='layer_from_query'),
    path('category/', category, name='category'),
    path('delete_sequence/', delete_sequence, name='delete_sequence'),
]
