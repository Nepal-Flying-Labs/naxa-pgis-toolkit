from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

# from pgis_toolkit.users.api.views import UserViewSet

# if settings.DEBUG:
#     router = DefaultRouter()
# else:
#     router = SimpleRouter()

# router.register("users", UserViewSet)


app_name = "api"
# urlpatterns = router.urls
urlpatterns = [
    # path('', include(router.urls)),
    path("users/", include("pgis_toolkit.users.api.urls", namespace="users")),
    path("projects/", include("pgis_toolkit.projects.api.urls", namespace='projects')),
    path("maps/", include("pgis_toolkit.maps.api.urls", namespace='maps')),

]
