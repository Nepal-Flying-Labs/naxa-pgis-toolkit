from django.urls import path
from rest_framework_simplejwt import views as jwt_views
from .views import PreliminaryUserAPIView, PreliminaryUserGETAPIView

app_name = "users"
urlpatterns = [
        # DRF SimpleJWT token
    path('token/login/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
    path('preliminary_user_create/', PreliminaryUserAPIView.as_view(), name='preliminary_user_create'),
    path('preliminary_user_retrieve/', PreliminaryUserGETAPIView.as_view(), name='preliminary_user_retrieve')

]
