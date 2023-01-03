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
    check_null_geometry,
    check_multipart_geometry,
    check_duplicate_geometry,
    check_overlapping_geometry,
    check_self_intersecting_geometry,
    check_isolated_geometry,
    fix_layer,
    fix_null_geometry,
    fix_multipart_geometry,
    fix_duplicate_geometry,
    fix_overlay_geometry,
    fix_self_intersecting_geometry,
    fix_isolated_geometry,
    buffer_distance,
    buffer_column,
    data_buffer,
    optimum_path_analysis,
    service_area_analysis,
    closest_path_analysis,
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

data_clean_urls = [
    # Check Layers api
    path('check_layer/', check_layer, name='check_layer'),
    path('check_null_geometry/', check_null_geometry, name='check_null_geometry'),
    path('check_multipart_geometry/', check_multipart_geometry, name='check_multipart_geometry'),
    path('check_duplicate_geometry/', check_duplicate_geometry, name='check_duplicate_geometry'),
    path('check_overlapping_geometry/', check_overlapping_geometry, name='check_overlapping_geometry'),
    path('check_self_intersecting_geometry/', check_self_intersecting_geometry, name='check_self_intersecting_geometry'),
    path('check_isolated_geometry/', check_isolated_geometry, name='check_isolated_geometry'),
    # Fix Layers api
    path('fix_layer/', fix_layer, name='fix_layer'),
    path('fix_null_geometry/', fix_null_geometry, name='fix_null_geometry'),
    path('fix_multipart_geometry/', fix_multipart_geometry, name='fix_multipart_geometry'),
    path('fix_duplicate_geometry/', fix_duplicate_geometry, name='fix_duplicate_geometry'),
    path('fix_overlay_geometry/', fix_overlay_geometry, name='fix_overlay_geometry'),
    path('fix_self_intersecting_geometry/', fix_self_intersecting_geometry, name='fix_self_intersecting_geometry'),
    path('fix_isolated_geometry/', fix_isolated_geometry, name='fix_isolated_geometry'),
]

data_analysis_urls = [
    path('buffer_by_distance/', buffer_distance, name="buffer_by_distance"),
    path('buffer_by_column/', buffer_column, name="buffer_by_column"),
    path('data_inside_buffer/', data_buffer, name="data_inside_buffer"),
    path('optimum_path_analysis/', optimum_path_analysis, name="optimum_path_analysis"),
    path('service_area_analysis/', service_area_analysis, name="service_area_analysis"),
    path('closest_path_analysis/', closest_path_analysis, name="closest_path_analysis")
]

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
    path('feature_geojson/<int:pk>/', FeatureGeoJSONAPIView.as_view(), name='feature'),
    path('data_merge_update/', DataMergeUpdateAPIView.as_view(), name='data_merge_update'),
    path('get_data_merge_update_task_response/', get_data_merge_update_task_response),
    path('shortest_distance_analysis/', ShortestPathAPIView.as_view(), name='shortest_distance_analysis'),
    path('get_analysis_task_response/', get_analysis_task_response),
    path('shortest_routes_vectortile/<int:z>/<int:x>/<int:y>/', ShortestRoutesTileQuerySet.as_view(), name='NetworkRoutesTileQuerySet'),
    path('feature_popup/', feature_popup, name='feature_popup'),
    path('analysis_layers/', analysis_layers, name='analysis_layers'),
    path('map_config/', ProjectMapConfigAPIView.as_view(), name='map_config'),
    path('advance_query/', AdvanceQueryAPIView.as_view(), name='advance_query'),
    path('layer_from_query/', LayerFromQueryAPIView.as_view(), name='layer_from_query'),
    path('category/', category, name='category'),
    path('delete_sequence/', delete_sequence, name='delete_sequence'),
] + data_clean_urls + data_analysis_urls
