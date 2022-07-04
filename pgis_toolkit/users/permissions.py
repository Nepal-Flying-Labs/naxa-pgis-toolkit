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

class IsTaskAuthorized(BasePermission):
    """
    Allows access only to users who are pgis administrator, organization admin and project manager in their organization/project.
    """

    def has_permission(self, request, view):
        try:
            userrole_qs = UserRole.active.filter(user__id=request.user.id, active=True)
            group_ids = userrole_qs.values_list('group__id', flat=True)
            if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
                return True
            elif 'organization' in request.query_params and request.query_params['organization'] != "":
                userrole_qs = userrole_qs.filter(organization__id=request.query_params['organization'])
                group_ids = userrole_qs.values_list('group__id', flat=True)
                if int(env('ORGANIZATION_ADMIN')) in group_ids:
                    return True
            elif 'project' in request.query_params and request.query_params['project'] != "":
                userrole_qs = userrole_qs.filter(project__id=request.query_params['project'])
                '''a user has a single role in a particular project'''
                group_instance = Group.objects.get(pk=userrole_qs[0].group.id)
                if group_instance.id == int(env('PROJECT_MANAGER')):
                    return True
            return False
        except Exception as e:
            print("Error occured in IsTaskAuthorized Permission Check Error. Details:", str(e))
            return False
