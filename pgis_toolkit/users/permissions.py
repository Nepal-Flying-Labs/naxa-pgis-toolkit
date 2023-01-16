from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from pgis_toolkit.projects.models import Project
from pgis_toolkit.users.models import PreliminaryUser, UserRole

# from users.models import User
User = get_user_model()

import environ

env = environ.Env()

def get_user_group(user_id,organization_id,project_id):
    user_role_qs=UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
    admin_level_role=user_role_qs.filter(organization=None,project=None).values('group')
    org_level_role=user_role_qs.filter(organization=organization_id,project=None).values('group')
    project_level_role=user_role_qs.filter(organization=organization_id,project=project_id).values('group')
    group_id=None
    if project_level_role:
        group_id=project_level_role[0]['group']
    elif org_level_role:
        group_id=org_level_role[0]['group']
    elif admin_level_role:
        group_id=admin_level_role[0]['group']
    return group_id

def get_permission_list(group_id):
    permission_qs = Group.objects.get(id=group_id).permissions.all().values('codename')
    permission_list = [data['codename'] for data in permission_qs]
    return permission_list

def check_invitation_hierarchy(user_group, inviting_group):
    hier= {int(env('PGIS_WEB_APP_ADMINISTRATOR')): 1, int(env('ORGANIZATION_ADMIN')): 2, int(env('PROJECT_MANAGER')): 3, int(env('DATA_COLLECTOR')): 4}
    return True if hier[user_group] <= hier[inviting_group] else False

class IsAuthorizedInviter(BasePermission):
    """
    Permission Check for Email Invitation and create Organization and Project.
    """

    def has_permission(self, request, view):
        try:
            request_keys = request.data.keys()
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            organization_id, project_id, organization_name, project_name = None, None, None, None
            if 'organization' in request_keys and request.data['organization'] != "":
                organization_id = request.data['organization']
            if 'project' in request_keys and request.data['project'] != "":
                project_id = request.data['project']
            if 'organization_name' in request_keys and request.data['organization_name'] != "":
                organization_name = request.data['organization_name']
            if 'project_name' in request_keys and request.data['project_name'] != "":
                project_name = request.data['project_name']
            group_id=get_user_group(user_id, organization_id, project_id)
            print(group_id, "is group id")
            permission_list=get_permission_list(group_id)
            if project_name:
                '''user who can add a project can invite other users in that particular project in any role.'''
                if "add_project" in permission_list:
                    return True
            elif organization_name:
                '''user who can add a organization can invite other users in that particular organization in any role.'''
                if "add_organization" in permission_list:
                    return True
                    '''invitation for already existing organizations and projects are handeled via hierarchy check'''
            elif 'group' in request_keys and request.data['group'] != "":
                return check_invitation_hierarchy(group_id, int(request.data['group']))
            return False
        except Exception as e:
            print("Error occured in IsAuthorizedInviter Permission Check Error. Details:", str(e))
            return False

class UpdatePreliminaryUserPermission(BasePermission):
    """
    Permission Check for expire/ delete and resend email invitation.
    """

    def has_permission(self, request, view):
        try:
            request_keys = request.data.keys()
            pk=request.resolver_match.kwargs.get('pk')
            resend = request.data.get('resend', False)
            print(resend, "is ressend")
            print(pk, "is pk")
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            pre_user_inst = PreliminaryUser.objects.get(id=pk)
            print(user_id, pre_user_inst.organization, pre_user_inst.project, "is user, organization, project ids")
            group_id=get_user_group(user_id, pre_user_inst.organization, pre_user_inst.project)
            print(group_id, "is group_id")
            permission_list=get_permission_list(group_id)
            if 'change_preliminaryuser' in permission_list:
                print('user has the change preliminary user permission')
                if resend:
                    print(check_invitation_hierarchy(group_id, pre_user_inst.group.id), "is check invitation hierarchy")
                    return check_invitation_hierarchy(group_id, pre_user_inst.group.id)
                else:
                    return True
            return False
        except Exception as e:
            print("Error occured in UpdatePreliminaryUserPermission Permission Check Error. Details:", str(e))
            return False

# class IsTaskAuthorized(BasePermission):
#     """
#     Permission Check for Organization and Project tasks.
#     """

#     def has_permission(self, request, view):
#         try:
#             url = request.build_absolute_uri().split('/')
#             url = list(filter(None, url))
#             pk = url[-1]
#             action = view.action
#             user_id = request.user.id
#             if request.user.is_superuser:
#                 return True
#             if action == "list":
#                 return True
#             user_role_qs = UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
#             admin_level_role=user_role_qs.filter(organization=None,project=None).values('group')
#             org_level_role=user_role_qs.filter(organization=pk,project=None).values('group') if 'organization' in url and pk else None
#             project_level_role=user_role_qs.filter(project=pk).values('group') if 'project' in url and pk else None
#             group_id=None
#             if project_level_role:
#                 group_id=project_level_role[0]['group']
#             elif org_level_role:
#                 group_id=org_level_role[0]['group']
#             elif admin_level_role:
#                 group_id=admin_level_role[0]['group']
#                 '''for organization admin who do not have any project role'''
#             if not group_id and 'project' in url and pk :
#                 organization = Project.active.get(id=pk).organization
#                 org_level_role=user_role_qs.filter(organization=organization,project=None).values('group')
#                 group_id=org_level_role[0]['group']
#             if group_id:
#                 permission_qs= Group.objects.get(id=group_id).permissions.all().values('codename')
#                 permission_list=[data['codename'] for data in permission_qs]
#                 if project_level_role:
#                     if action=="create" and "add_project" in permission_list:
#                         return True
#                     elif action=="partial_update" and "change_project" in permission_list:
#                         return True
#                     elif action=="retrieve" and "view_project" in permission_list:
#                         return True
#                 elif org_level_role:
#                     if action=="create" and "add_organization" in permission_list:
#                         return True
#                     elif action=="partial_update" and "change_organization" in permission_list:
#                         return True
#                     elif action=="retrieve" and "view_organization" in permission_list:
#                         return True
#                 elif admin_level_role:
#                     if action=="create" and "add_organization" and "add_project" in permission_list:
#                         return True
#                     elif action=="partial_update" and "change_organization" and "change_project" in permission_list:
#                         return True
#                     elif action=="retrieve" and "view_organization" and "view_project" in permission_list:
#                         return True
#             return False
#         except Exception as e:
#             print("Error occured in IsTaskAuthorized Permission Check. Error Details: ", str(e))
#             return False


# class IsAuthorizedInviter(BasePermission):
#     """
#     Permission Check for Email Invitation.
#     """

#     def has_permission(self, request, view):
#         try:
#             request_keys = request.data.keys()
#             user_id = request.user.id
#             if request.user.is_superuser:
#                 return True
#             user_role_qs = UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
#             admin_level_role=user_role_qs.filter(organization=None,project=None).values('group')
#             org_level_role=user_role_qs.filter(organization=request.data['organization'],project=None).values('group') if 'organization' in request_keys and request.data['organization'] != "" else None
#             project_level_role=user_role_qs.filter(project=request.data['project']).values('group') if 'project' in request_keys and request.data['project'] != "" else None
#             group_id=None
#             if project_level_role:
#                 group_id=project_level_role[0]['group']
#             elif org_level_role:
#                 group_id=org_level_role[0]['group']
#             elif admin_level_role:
#                 group_id=admin_level_role[0]['group']
#                 '''for organization admin who do not have any project role'''
#             if not group_id and 'project' in request_keys and request.data['project'] != "" :
#                 organization = Project.active.get(id=request.data['project']).organization
#                 org_level_role=user_role_qs.filter(organization=organization,project=None).values('group')
#                 group_id=org_level_role[0]['group']
#             if group_id:
#                 if 'group' in request_keys and request.data['group'] != "":
#                     if check_invitation_hierarchy(group_id, int(request.data['group'])) == False:
#                         return False
#                 permission_qs= Group.objects.get(id=group_id).permissions.all().values('codename')
#                 permission_list=[data['codename'] for data in permission_qs]
#                 if project_level_role:
#                     '''project manager who has add project permission has also inviting permission'''
#                     if "add_project" in permission_list:
#                         return True
#                 elif org_level_role:
#                     '''organization admin will create project and also has inviting permission'''
#                     if "add_project" in permission_list:
#                         return True
#                 elif admin_level_role:
#                     if "add_project" in permission_list and "add_organization" in permission_list:
#                         return True
#             return False
#         except Exception as e:
#             print("Error occured in IsAuthorizedInviter Permission Check Error. Details:", str(e))
#             return False
