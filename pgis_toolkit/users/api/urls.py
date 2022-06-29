from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt import views as jwt_views

from .views import (
    EmailConfirmationAPIView,
    PreliminaryUserAPIView,
    PreliminaryUserListView,
    PreliminaryUserVerificationAPIView,
    UserViewSet,
)

router = DefaultRouter()
router.register(r'user', UserViewSet, basename='user')


app_name = "users"
urlpatterns = [
    path('', include(router.urls)),
        # DRF SimpleJWT token
    path('token/login/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
    path('preliminary_user_create/', PreliminaryUserAPIView.as_view(), name='preliminary_user_create'),
    path('preliminary_user_verify/', PreliminaryUserVerificationAPIView.as_view(), name='preliminary_user_verify'),
    path('email_verify/', EmailConfirmationAPIView.as_view(), name='email_verify'),
    path('preliminary_user/', PreliminaryUserListView.as_view(), name='preliminary_user'),
]
