from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from pgis_toolkit.projects.models import Document, Project
from pgis_toolkit.users.models import UserRole

# from users.models import User
User = get_user_model()

import environ

env = environ.Env()

def get_permission_list(group_id):
    permission_qs = Group.objects.get(id=group_id).permissions.all().values('codename')
    permission_list = [data['codename'] for data in permission_qs]
    return permission_list

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
                permission_list=get_permission_list(group_id)
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

class DocumentPermission(BasePermission):
    """
    Permission whether a user can perform CRUD operations of Document
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            project_id = request.query_params.get('project')
            project_inst = Project.active.get(id=project_id)
            user_role_qs = UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
            admin_level_role=user_role_qs.filter(organization=None,project=None).values('group')
            org_level_role=user_role_qs.filter(organization=project_inst.organization, project=None).values('group')
            project_level_role=user_role_qs.filter(project=project_id).values('group')
            group_id=None
            if project_level_role:
                group_id=project_level_role[0]['group']
            elif org_level_role:
                group_id=org_level_role[0]['group']
            elif admin_level_role:
                group_id=admin_level_role[0]['group']
            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="create" and "add_document" in permission_list:
                    return True
                elif action=="partial_update" and "change_document" in permission_list:
                    return True
                elif action=="retrieve" and "view_document" in permission_list:
                    return True
                elif action=="list" and "view_document" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in DocumentPermission Check. Error Details: ", str(e))
            return False

class DocumentDownloadPermission(BasePermission):
    """
    Permission whether a user can download a document or not.
    """

    def has_permission(self, request, view):
        try:
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            document_id = request.query_params.get('document')
            document_inst = Document.objects.get(id=document_id)
            project_inst = Project.active.get(id=document_inst.project.id)
            user_role_qs = UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
            admin_level_role=user_role_qs.filter(organization=None,project=None).values('group')
            org_level_role=user_role_qs.filter(organization=project_inst.organization, project=None).values('group')
            project_level_role=user_role_qs.filter(project=project_inst).values('group')
            group_id=None
            if project_level_role:
                group_id=project_level_role[0]['group']
            elif org_level_role:
                group_id=org_level_role[0]['group']
            elif admin_level_role:
                group_id=admin_level_role[0]['group']
            if group_id:
                permission_list=get_permission_list(group_id)
                if "download_document" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in DocumentPermission Check. Error Details: ", str(e))
            return False
