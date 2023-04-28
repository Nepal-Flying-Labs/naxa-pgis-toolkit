from django.urls import include, path
from rest_framework.routers import DefaultRouter

# ReorderView,; project_layers,; get_error_data,
from pgis_toolkit.maps.api.views import (
    AdvanceFilterVectorTileQuerySet,
    AdvanceQueryAPIView,
    AnalysisViewset,
    DataMergeUpdateAPIView,
    DropdownChoiceViewset,
    ErrorFeaturesVectorTileQuerySet,
    FeatureCollectionMirrorViewset,
    FeatureCollectionViewset,
    FeatureGeoJSONAPIView,
    FeatureImageViewset,
    FeatureMirrorGeoJSONAPIView,
    LayerAttributeViewset,
    LayerFromOptimumPathAnalysis,
    LayerFromProximityAnalysis,
    LayerFromQueryAPIView,
    LayerGroupViewset,
    LayerVectorTileQuerySet,
    LayerViewSet,
    MirrorFeatureVectorTileQuerySet,
    NetworkRoutesCollection,
    OptimumRouteAnalysisAPIView,
    OptimumRouteAnalysisTileQuerySet,
    ProjectLayerTemplateAttributeViewset,
    ProjectLayerTemplateViewset,
    ProjectMapConfigAPIView,
    ProjectsLayerTemplateDropdownChoiceViewset,
    ProjectStyleViewset,
    ProximityAnalysisAPIView,
    ProximityAnalysisDataAPIView,
    ProximityAreasCollection,
    ProximityAreaTileQuerySet,
    QueryFeatureCollectionViewset,
    ServiceAreaAnalysisAPIView,
    StandardIconViewset,
    SubLayerViewset,
    ThemeViewset,
    analysis_result_detail,
    analysis_result_list,
    analysis_type_list,
    bulk_create_image_from_urls,
    bulk_del_null_geom,
    bulk_template_download,
    bulk_upload_image,
    cancel_layer_upload,
    category,
    check_duplicate_geometry,
    check_isolated_geometry,
    check_layer,
    check_multipart_geometry,
    check_null_geometry,
    check_overlapping_geometry,
    check_self_intersecting_geometry,
    cleaning_error_features,
    copy_features,
    delete_sequence,
    feature_popup,
    fix_duplicate_geometry,
    fix_isolated_geometry,
    fix_layer,
    fix_multipart_geometry,
    fix_null_geometry,
    fix_overlay_geometry,
    fix_self_intersecting_geometry,
    get_analysis_task_response,
    get_bulk_upload_image_response,
    get_data_merge_update_task_response,
    get_layer_upload_task_response,
    import_template,
    layer_download,
    project_theme_layers,
    reorder,
    sync_features,
    sync_mirror_to_mongo,
    sync_template,
    update_template_attributes,
)

router = DefaultRouter()
#==================
#       Map
#==================
router.register(r'theme', ThemeViewset, basename='theme')
router.register(r'project_style', ProjectStyleViewset, basename='project_style')
router.register(r'standard_icon', StandardIconViewset, basename='standard_icon')
router.register(r'layer', LayerViewSet, basename='layer')
router.register(r'sub_layer', SubLayerViewset, basename='sub_layer')
router.register(r'feature_collection', FeatureCollectionViewset, basename='feature_collection')
router.register(r'layer_group', LayerGroupViewset, basename='layer_group')
router.register(r'layer_attribute', LayerAttributeViewset, basename = 'layer attributes')
router.register(r'dropdown_choice', DropdownChoiceViewset, basename = 'dropdown_choice')
router.register(r'feature_image', FeatureImageViewset, basename = 'feature_image')

#==================
#     Template
#==================
router.register(r'project_layer_template', ProjectLayerTemplateViewset, basename='project_layer_template')
router.register(r'project_layer_template_attribute', ProjectLayerTemplateAttributeViewset, basename = 'project_layer_template_attribute')
router.register(r'project_layer_template_attribute_dropdown_choice', ProjectsLayerTemplateDropdownChoiceViewset, basename = 'project_template_attribute_dropdown_choice')

#==================
#   Advance Query
#==================
router.register(r'query_feature_collection', QueryFeatureCollectionViewset, basename='query_feature_collection')

#==================
#  Feature Mirror
#==================
router.register(r'feature_collection_mirror', FeatureCollectionMirrorViewset, basename='feature_collection_mirror')

#==================
#  NetworkRoutes
#==================
router.register(r'analysis', AnalysisViewset, basename='analysis')
router.register(r'network_route_collection', NetworkRoutesCollection, basename='network_route_collection')

#==================
#  ProximityAreas
#==================
router.register(r'proximity_area_collection', ProximityAreasCollection, basename='proximity_area_collection')
app_name = "projects"

data_clean_urls = [

    # Check Layers api
    path('copy_features/', copy_features, name='copy_features'),
    path('check_layer/', check_layer, name='check_layer'),
    path('check_null_geometry/', check_null_geometry, name='check_null_geometry'),
    path('check_multipart_geometry/', check_multipart_geometry, name='check_multipart_geometry'),
    path('check_duplicate_geometry/', check_duplicate_geometry, name='check_duplicate_geometry'),
    path('check_overlapping_geometry/', check_overlapping_geometry, name='check_overlapping_geometry'),
    path('check_self_intersecting_geometry/', check_self_intersecting_geometry, name='check_self_intersecting_geometry'),
    path('check_isolated_geometry/', check_isolated_geometry, name='check_isolated_geometry'),
    # path('get_error_data/', get_error_data, name="get_error_data"),
    # Fix Layers api
    path('fix_layer/', fix_layer, name='fix_layer'),
    path('fix_null_geometry/', fix_null_geometry, name='fix_null_geometry'),
    path('fix_multipart_geometry/', fix_multipart_geometry, name='fix_multipart_geometry'),
    path('fix_duplicate_geometry/', fix_duplicate_geometry, name='fix_duplicate_geometry'),
    path('fix_overlapping_geometry/', fix_overlay_geometry, name='fix_overlay_geometry'),
    path('fix_self_intersecting_geometry/', fix_self_intersecting_geometry, name='fix_self_intersecting_geometry'),
    path('fix_isolated_geometry/', fix_isolated_geometry, name='fix_isolated_geometry'),
    path('bulk_del_null_geom/', bulk_del_null_geom, name='bulk_del_null_geom'),
    #sync features to feature_collection table after data clean
    path('sync_features/', sync_features, name='sync_features'),
]

def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns = [
    path('', include(router.urls)),
    path('sentry-debug/', trigger_error),
    # path('project_layers/<int:id>/', project_layers, name='project_layers'),
    # path('layer/', LayerAPIView.as_view(), name='layer'),
    # path('layer/<int:pk>/', LayerAPIView.as_view(), name='layer_update'),

    #==================
    #       Map
    #==================
    path('project_theme_layers/', project_theme_layers, name='project_theme_layers'),
    path('get_layer_upload_task_response/', get_layer_upload_task_response),
    path('reorder/',reorder, name='reorder'),
    path('layer_vectortile/<int:z>/<int:x>/<int:y>/', LayerVectorTileQuerySet.as_view(), name='layer_vectortile'),
    path('layer_download/', layer_download, name='layer_download'),
    path('advance_filter_vectortile/<int:z>/<int:x>/<int:y>/', AdvanceFilterVectorTileQuerySet.as_view(), name="AdvanceFilterVectorTileQuerySet"),
    path('feature_geojson/<int:pk>/', FeatureGeoJSONAPIView.as_view(), name='feature'),
    path('feature_popup/', feature_popup, name='feature_popup'),
    path('map_config/', ProjectMapConfigAPIView.as_view(), name='map_config'),
    path('cleaning_error_features/', cleaning_error_features, name='cleaning_error_features'),
    path('error_features_vectortile/<int:z>/<int:x>/<int:y>/', ErrorFeaturesVectorTileQuerySet.as_view(), name='error_features_vectortile'),
    path('feature_mirror_geojson/', FeatureMirrorGeoJSONAPIView.as_view(), name='feature_mirror_geojson'),
    path('feature_mirror_vectortile/<int:z>/<int:x>/<int:y>/', MirrorFeatureVectorTileQuerySet.as_view(), name='feature_mirror_vectortile'),
    path('bulk_create_image_from_urls/', bulk_create_image_from_urls, name ='bulk_create_image_from_urls'),
    path('bulk_upload_image/', bulk_upload_image, name='bulk_upload_image'),
    path('get_bulk_upload_image_response/', get_bulk_upload_image_response),

    #==================
    #    Data Merge
    #==================
    path('data_merge_update/', DataMergeUpdateAPIView.as_view(), name='data_merge_update'),
    path('get_data_merge_update_task_response/', get_data_merge_update_task_response),

    #==================
    #     Analysis
    #==================
    path('sync_mirror_to_mongo/',sync_mirror_to_mongo, name='sync_mirror_to_mongo'),
    path('analysis_result_list/', analysis_result_list, name='analysis_layers'),
    path('analysis_result_detail/', analysis_result_detail, name='analysis_layers'),
    path('get_analysis_task_response/', get_analysis_task_response),
    path('optimum_route_analysis/', OptimumRouteAnalysisAPIView.as_view(), name='shortest_distance_analysis'),
    path('optimum_route_vectortile/<int:z>/<int:x>/<int:y>/', OptimumRouteAnalysisTileQuerySet.as_view(), name='NetworkRoutesTileQuerySet'),
    path('layer_from_optimum_path/', LayerFromOptimumPathAnalysis.as_view(), name='LayerFromOptimumPathAnalysis'),
    path('proximity_analysis/', ProximityAnalysisAPIView.as_view(), name='proximity_analysis'),
    # path('proximity_analysis_data/', ProximityAnalysisDataAPIView.as_view(), name='proximity_analysis_data'),
    path('proximity_area_vectortile/<int:z>/<int:x>/<int:y>/', ProximityAreaTileQuerySet.as_view(), name='NetworkRoutesTileQuerySet'),
    path('layer_from_buffer/',LayerFromProximityAnalysis.as_view(), name='layer_from_buffer'),
    path('analysis_type_list/',analysis_type_list,name="analysis_type_list"),
    #==================
    #   Advance Query
    #==================
    path('advance_query/', AdvanceQueryAPIView.as_view(), name='advance_query'),
    path('layer_from_query/', LayerFromQueryAPIView.as_view(), name='layer_from_query'),

    #==================
    #     Template
    #==================
    path('update_template_attributes/', update_template_attributes, name='update_template_attributes'),
    path('import_template/', import_template, name='import_template'),
    path('sync_template/', sync_template, name='sync_template'),
    path('bulk_template_download/', bulk_template_download, name='bulk_template_download'),

    #==================
    #   Miscellaneous
    #==================
    path('category/', category, name='category'),
    path('delete_sequence/', delete_sequence, name='delete_sequence'),
    path('cancel_layer_upload/', cancel_layer_upload, name='cancel_layer_upload')
] + data_clean_urls
