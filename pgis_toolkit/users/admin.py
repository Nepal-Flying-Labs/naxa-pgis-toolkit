from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

# from pgis_toolkit.users.forms import UserAdminChangeForm, UserAdminCreationForm

User = get_user_model()
from .models import UserRole, PreliminaryUser

# @admin.register(User)
# class UserAdmin(auth_admin.UserAdmin):

#     form = UserAdminChangeForm
#     add_form = UserAdminCreationForm
#     fieldsets = (
#         (None, {"fields": ("username", "password")}),
#         (_("Personal info"), {"fields": ("name", "email")}),
#         (
#             _("Permissions"),
#             {
#                 "fields": (
#                     "is_active",
#                     "is_staff",
#                     "is_superuser",
#                     "groups",
#                     "user_permissions",
#                 ),
#             },
#         ),
#         (_("Important dates"), {"fields": ("last_login", "date_joined")}),
#     )
#     list_display = ["username", "name", "is_superuser"]
#     search_fields = ["name"]

class UserAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {"fields": ("is_deleted",)}),
        (_("Credentials"), {"fields": ("username", "password", "email_verification_token")}),
        (_("Personal info"), {"fields": ("full_name", "email", "contact", "image")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ("is_deleted","id", "full_name", "email", "is_active")
    search_fields = ("full_name",)

class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'organization', 'group', 'project', 'active')
    search_fields = ('id', 'user')
    list_filter = ('organization', 'group', 'project', 'active')

class PreliminaryUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'organization', 'project', 'group')
    search_fields = ('id', 'email')
    list_filter = ('organization', 'project', 'group')


admin.site.register(User, UserAdmin)
admin.site.register(UserRole, UserRoleAdmin)
admin.site.register(PreliminaryUser, PreliminaryUserAdmin)