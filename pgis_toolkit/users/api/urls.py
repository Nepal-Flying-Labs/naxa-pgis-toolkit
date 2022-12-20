from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt import views as jwt_views

from .views import (
    ChangePasswordView,
    EmailConfirmationAPIView,
    ForgotPasswordEmailView,
    PreliminaryUserAPIView,
    PreliminaryUserListView,
    PreliminaryUserVerificationAPIView,
    RequestUserDetailAPIView,
    ResetPasswordView,
    UserInvitationAPIView,
    UserPermissionViewSet,
    UserRoleUpdateView,
    UserViewSet,
    landing_page,
    set_csrf_token,
    user_group_list,
)

router = DefaultRouter()
router.register(r'user', UserViewSet, basename='user')
router.register(r'permissions', UserPermissionViewSet, basename="permissions")

app_name = "users"
urlpatterns = [
    path('', include(router.urls)),
        # DRF SimpleJWT token
    path('token/login/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
    path('myprofile/', RequestUserDetailAPIView.as_view(), name='requesting_user_profile'),
    path('preliminary_user_create/', PreliminaryUserAPIView.as_view(), name='preliminary_user_create'),
    path('preliminary_user_verify/', PreliminaryUserVerificationAPIView.as_view(), name='preliminary_user_verify'),
    path('email_verify/', EmailConfirmationAPIView.as_view(), name='email_verify'),
    path('preliminary_user/', PreliminaryUserListView.as_view(), name='preliminary_user'),
    path('user_group/', user_group_list, name='user_group'),
    path('forgot_password_email/', ForgotPasswordEmailView.as_view(), name='password_reset_email'),
    path('reset_password/', ResetPasswordView.as_view(), name='password_reset'),
    path('change_password/', ChangePasswordView.as_view(), name='password_change'),
    path('userrole_update/<int:pk>/', UserRoleUpdateView.as_view(), name='update_userrole'),
    # path('deactivate/', DeactivateUserRoleView.as_view(), name='deactivate_userrole'),
    path('set_csrf/', set_csrf_token, name='Set-CSRF'),
    path('landing_page/', landing_page, name='landing_page'),
    path('user_invitation/', UserInvitationAPIView.as_view(), name='user_invitation'),
]
