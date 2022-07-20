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
    Allows access only to users who are pgis administrator, organization admin and project manager in their organization/project. Used for
    """

    def has_permission(self, request, view):
        try:
            url = request.build_absolute_uri().split('/')
            url = list(filter(None, url))
            pk = url[-1]
            action = view.action
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            if action == "list":
                return True
            user_role_qs = UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
            admin_level_role=user_role_qs.filter(organization=None,project=None).values('group')
            org_level_role=user_role_qs.filter(organization=pk,project=None).values('group') if 'organization' in url and pk else None
            project_level_role=user_role_qs.filter(project=pk).values('group') if 'project' in url and pk else None
            group_id=None
            if project_level_role:
                group_id=project_level_role[0]['group']
            elif org_level_role:
                group_id=org_level_role[0]['group']
            elif admin_level_role:
                group_id=admin_level_role[0]['group']

            if group_id:
                permission_qs= Group.objects.get(id=group_id).permissions.all().values('codename')
                permission_list=[data['codename'] for data in permission_qs]
                if project_level_role:
                    if action=="create" and "add_project" in permission_list:
                        return True
                    elif action=="partial_update" and "change_project" in permission_list:
                        return True
                    elif action=="retrieve" and "view_project" in permission_list:
                        return True
                elif org_level_role:
                    if action=="create" and "add_organization" in permission_list:
                        return True
                    elif action=="partial_update" and "change_organization" in permission_list:
                        return True
                    elif action=="retrieve" and "view_organization" in permission_list:
                        return True
            return False
            # group_ids = userrole_qs.values_list('group__id', flat=True)
            # if request.user.is_superuser:
            #     return True
            # elif int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
            #     return True
            # elif 'organization' in url and pk:
            #     userrole_qs = userrole_qs.filter(organization__id=pk)
            #     group_ids = userrole_qs.values_list('group__id', flat=True)
            #     if int(env('ORGANIZATION_ADMIN')) in group_ids:
            #         return True
            # elif 'project' in url and pk:
            #     userrole_qs = userrole_qs.filter(project__id=int(pk))
            #     if userrole_qs.exists():
            #         '''a user has a single role in a particular project'''
            #         group_instance = Group.objects.get(pk=userrole_qs[0].group.id)
            #         if group_instance.id == int(env('PROJECT_MANAGER')):
            #             return True
        except Exception as e:
            print("Error occured in IsTaskAuthorized Permission Check. Error Details: ", str(e))
            return False

def check_invitation_hierarchy(user_group, inviting_group):
    hier= {int(env('PGIS_WEB_APP_ADMINISTRATOR')): 1, int(env('ORGANIZATION_ADMIN')): 2, int(env('PROJECT_MANAGER')): 3, int(env('DATA_COLLECTOR')): 4}
    return True if hier[user_group] <= hier[inviting_group] else False

class IsAuthorizedInviter(BasePermission):
    """
    Allows the user to send email invitation.
    """

    def has_permission(self, request, view):
        try:
            request_keys = request.data.keys()
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            user_role_qs = UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
            admin_level_role=user_role_qs.filter(organization=None,project=None).values('group')
            org_level_role=user_role_qs.filter(organization=request.data['organization'],project=None).values('group') if 'organization' in request_keys and request.data['organization'] != "" else None
            project_level_role=user_role_qs.filter(project=request.data['project']).values('group') if 'project' in request_keys and request.data['project'] != "" else None
            group_id=None
            if project_level_role:
                group_id=project_level_role[0]['group']
            elif org_level_role:
                group_id=org_level_role[0]['group']
            elif admin_level_role:
                group_id=admin_level_role[0]['group']
            if group_id:
                if 'group' in request_keys and request.data['group'] != "":
                    if check_invitation_hierarchy(group_id, int(request.data['group'])) == False:
                        return False
                permission_qs= Group.objects.get(id=group_id).permissions.all().values('codename')
                permission_list=[data['codename'] for data in permission_qs]
                if project_level_role:
                    '''project manager who has add project permission has also inviting permission'''
                    if "add_project" in permission_list:
                        return True
                elif org_level_role:
                    '''organization admin will create project and also has inviting permission'''
                    if "add_project" in permission_list:
                        return True
                elif admin_level_role:
                    if "add_project" in permission_list and "add_organization" in permission_list:
                        return True
            return False
            # userrole_qs = UserRole.active.filter(user__id=request.user.id, active=True)
            # group_ids = userrole_qs.values_list('group__id', flat=True)
            # if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
            #     return True
            # elif 'organization' in request.data.keys() and request.data['organization'] != "":
            #     userrole_qs = userrole_qs.filter(organization__id=request.data['organization'])
            #     group_ids = userrole_qs.values_list('group__id', flat=True)
            #     if int(env('ORGANIZATION_ADMIN')) in group_ids:
            #         return True
            # elif 'project' in request.data.keys() and request.data['project'] != "":
            #     userrole_qs = userrole_qs.filter(project__id=request.data['project'])
            #     '''a user has a single role in a particular project'''
            #     group_instance = Group.objects.get(pk=userrole_qs[0].group.id)
            #     if group_instance.id == int(env('PROJECT_MANAGER')):
            #         return True
            # return False
        except Exception as e:
            print("Error occured in IsAuthorizedInviter Permission Check Error. Details:", str(e))
            return False
