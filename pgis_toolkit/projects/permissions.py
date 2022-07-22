from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from pgis_toolkit.users.models import UserRole

# from users.models import User
User = get_user_model()

import environ

env = environ.Env()

class OrganizationCategoryPermission(BasePermission):
    """
    Permission whether a user can perform CRUD operations of Organization Category
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            user_role_qs = UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
            org_level_role=user_role_qs.filter(project=None).values('group')
            group_id=org_level_role[0]['group'] if org_level_role else None
            if group_id:
                permission_qs= Group.objects.get(id=group_id).permissions.all().values('codename')
                permission_list=[data['codename'] for data in permission_qs]
                if action=="create" and "add_organizationcategory" in permission_list:
                    return True
                elif action=="partial_update" and "change_organizationcategory" in permission_list:
                    return True
                elif action=="retrieve" and "view_organizationcategory" in permission_list:
                    return True
                elif action=="list" and "view_organizationcategory" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in OrganizationCategoryPermission Check. Error Details: ", str(e))
            return False
