from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from pgis_toolkit.projects.models import Document, Image, Project
from pgis_toolkit.users.models import UserRole

# from users.models import User
User = get_user_model()

import environ

env = environ.Env()

def get_user_group(user_id,organization_id,project_id):
    user_role_qs=UserRole.active.select_related('organization','group','user','project').filter(user=user_id, active=True)
    admin_level_role=user_role_qs.filter(organization=None,project=None).values('group')
    org_level_role=user_role_qs.filter(organization=organization_id,project=None).values('group')
    project_level_role=user_role_qs.filter(organization=organization_id,project=project_id).values('group') if project_id else user_role_qs.filter(organization=organization_id).exclude(project=None).values('group')
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


class OrganizationPermission(BasePermission):
    """
    Permission Check for OrganizationViewset.
    create action is not implemented in Organization viewset.
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id = request.user.id
            if request.user.is_superuser:
                return True
                '''organizations in which users are involved are filtered and provided in list.'''
            if action == "list":
                return True
            elif action in ["retrieve" , "partial_update"]:
                organization_id = request.resolver_match.kwargs.get('pk')
                project_id = None
            group_id=get_user_group(user_id, organization_id, project_id)
            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="partial_update" and "change_organization" in permission_list:
                    return True
                elif action=="retrieve" and "view_organization" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in OrganizationPermission Check. Error Details: ", str(e))
            return False

class ProjectPermission(BasePermission):
    """
    Permission Check for ProjectViewset.
    create action is not implemented in Project viewset.
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id = request.user.id
            if request.user.is_superuser:
                return True
                '''projects in which users are involved are filtered and provided in list.'''
            if action == "list":
                organization_id = request.query_params.get('organization', None)
                project_id=None
            elif action in ["retrieve" , "partial_update"]:
                project_id = request.resolver_match.kwargs.get('pk')
                organization_id = Project.active.get(id=project_id).organization.id

            group_id=get_user_group(user_id, organization_id, project_id)
            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="partial_update" and "change_project" in permission_list:
                    return True
                elif (action=="retrieve" or action=="list") and "view_project" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in ProjectPermission Check. Error Details: ", str(e))
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
            if action=="list":
                project_id = request.query_params.get('project')
                organization_id = Project.active.get(id=project_id).organization.id
            elif action=="create":
                project_id = request.data.get('project')
                organization_id = Project.active.get(id=project_id).organization.id
            elif action in ["retrieve", "partial_update"]:
                document_id = request.resolver_match.kwargs.get('pk')
                project_id = Document.objects.get(id=document_id).project.id
                organization_id = Project.active.get(id=project_id).organization.id
            group_id=get_user_group(user_id, organization_id, project_id)
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
            project_id = request.query_params.get('project')
            organization_id = Project.active.get(id=project_id).organization.id
            group_id=get_user_group(user_id, organization_id, project_id)
            if group_id:
                permission_list=get_permission_list(group_id)
                if "download_document" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in DocumentPermission Check. Error Details: ", str(e))
            return False

class ImagePermission(BasePermission):
    """
    Permission whether a user can perform CRUD operations of Image
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            if action=="list":
                project_id = request.query_params.get('project')
                organization_id = Project.active.get(id=project_id).organization.id
            elif action=="create":
                project_id = request.data.get('project')
                organization_id = Project.active.get(id=project_id).organization.id
            elif action in ["retrieve", "partial_update"]:
                image_id = request.resolver_match.kwargs.get('pk')
                project_id = Image.objects.get(id=image_id).project.id
                organization_id = Project.active.get(id=project_id).organization.id
            group_id=get_user_group(user_id, organization_id, project_id)
            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="create" and "add_image" in permission_list:
                    return True
                elif action=="partial_update" and "change_image" in permission_list:
                    return True
                elif action=="retrieve" and "view_image" in permission_list:
                    return True
                elif action=="list" and "view_image" in permission_list:
                    return True
                elif action=='destory' and 'delete_image' in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in ImagePermission Check. Error Details: ", str(e))
            return False

class ImageDownloadPermission(BasePermission):
    """
    Permission whether a user can download a image or not.
    """

    def has_permission(self, request, view):
        try:
            user_id = request.user.id
            if request.user.is_superuser:
                return True
            project_id = request.query_params.get('project')
            organization_id = Project.active.get(id=project_id).organization.id
            group_id=get_user_group(user_id, organization_id, project_id)
            if group_id:
                permission_list=get_permission_list(group_id)
                if "download_image" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in ImageDownloadPermission Check. Error Details: ", str(e))
            return False
