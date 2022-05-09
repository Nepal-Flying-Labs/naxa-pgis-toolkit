from django.urls import include, path
from rest_framework.routers import DefaultRouter

from pgis_toolkit.maps.api.views import project_layers

router = DefaultRouter()

app_name = "projects"
urlpatterns = [
    path('', include(router.urls)),
    path('project_layers/<int:id>/', project_layers, name='project_layers')
]
