from django.urls import path, include
from rest_framework_simplejwt import views as jwt_views
from rest_framework.routers import DefaultRouter
from .views import PreliminaryUserAPIView, PreliminaryUserGETAPIView, UserViewSet

router = DefaultRouter()
router.register(r'user', UserViewSet, basename='user')


app_name = "users"
urlpatterns = [
    path('', include(router.urls)),
        # DRF SimpleJWT token
    path('token/login/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
    path('preliminary_user_create/', PreliminaryUserAPIView.as_view(), name='preliminary_user_create'),
    path('preliminary_user_retrieve/', PreliminaryUserGETAPIView.as_view(), name='preliminary_user_retrieve')

]
