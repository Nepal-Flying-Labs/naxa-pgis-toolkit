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
            url = request.build_absolute_uri().split('/')
            url = list(filter(None, url))
            pk = url[-1]
            userrole_qs = UserRole.active.filter(user__id=request.user.id, active=True)
            group_ids = userrole_qs.values_list('group__id', flat=True)
            if request.user.is_superuser:
                return True
            elif int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
                return True
            elif 'organization' in url and pk:
                userrole_qs = userrole_qs.filter(organization__id=pk)
                group_ids = userrole_qs.values_list('group__id', flat=True)
                if int(env('ORGANIZATION_ADMIN')) in group_ids:
                    return True
            elif 'project' in url and pk:
                userrole_qs = userrole_qs.filter(project__id=int(pk))
                if userrole_qs.exists():
                    '''a user has a single role in a particular project'''
                    group_instance = Group.objects.get(pk=userrole_qs[0].group.id)
                    if group_instance.id == int(env('PROJECT_MANAGER')):
                        return True
            return False
        except Exception as e:
            print("Error occured in IsTaskAuthorized Permission Check. Error Details: ", str(e))
            return False

class IsAuthorizedInviter(BasePermission):
    """
    Allows the user to send email invitation.
    """

    def has_permission(self, request, view):
        try:
            userrole_qs = UserRole.active.filter(user__id=request.user.id, active=True)
            group_ids = userrole_qs.values_list('group__id', flat=True)
            if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
                return True
            elif 'organization' in request.data.keys() and request.data['organization'] != "":
                userrole_qs = userrole_qs.filter(organization__id=request.data['organization'])
                group_ids = userrole_qs.values_list('group__id', flat=True)
                if int(env('ORGANIZATION_ADMIN')) in group_ids:
                    return True
            elif 'project' in request.data.keys() and request.data['project'] != "":
                userrole_qs = userrole_qs.filter(project__id=request.data['project'])
                '''a user has a single role in a particular project'''
                group_instance = Group.objects.get(pk=userrole_qs[0].group.id)
                if group_instance.id == int(env('PROJECT_MANAGER')):
                    return True
            return False
        except Exception as e:
            print("Error occured in IsAuthorizedInviter Permission Check Error. Details:", str(e))
            return False
