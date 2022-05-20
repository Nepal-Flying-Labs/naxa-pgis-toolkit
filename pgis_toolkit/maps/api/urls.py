from django.urls import include, path
from rest_framework.routers import DefaultRouter

from pgis_toolkit.maps.api.views import (
    LayerAPIView,
    get_layer_upload_task_response,
    project_layers, ThemeViewset
)

router = DefaultRouter()
router.register(r'theme', ThemeViewset, basename='theme')

app_name = "projects"
urlpatterns = [
    path('', include(router.urls)),
    path('project_layers/<int:id>/', project_layers, name='project_layers'),
    path('layer/', LayerAPIView.as_view(), name='layer'),
    path('layer/<int:pk>/', LayerAPIView.as_view(), name='layer_update'),
    path('get_layer_upload_task_response/', get_layer_upload_task_response),
]
