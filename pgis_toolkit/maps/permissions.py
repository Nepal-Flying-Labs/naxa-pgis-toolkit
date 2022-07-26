import environ
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from pgis_toolkit.maps.models import (
    FeatureCollection,
    Layer,
    LayerAttribute,
    LayerGroup,
    ProjectStyle,
    SubLayer,
    Theme,
)
from pgis_toolkit.projects.models import Organization, Project
from pgis_toolkit.users.models import UserRole

# from users.models import User
User = get_user_model()
env = environ.Env()

def get_user_group(user_id,organization_id,project_id):
    user_role_qs=UserRole.active.select_related('organization','group','user','project').filter(user=user_id)
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

class LayerPermission(BasePermission):
    """
    Permission check for layer model
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id=request.user.id
            if request.user.is_superuser:
                return True
            if action in ['retrieve','partial_update']:
                layer_id=request.resolver_match.kwargs.get('pk')
                project_id=Layer.objects.get(id=layer_id).theme.project.id
                organization_id=Project.active.get(id=project_id).organization.id

            if action=="create":
                theme_id=request.data.get("theme",None)
                project_id=Theme.active.get(id=theme_id).project.id
                organization_id=Project.active.get(id=project_id).organization.id

            group_id=get_user_group(user_id,organization_id,project_id)

            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="create" and "add_layer" in permission_list:
                    return True
                elif action=="partial_update" and "change_layer" in permission_list:
                    return True
                elif action=="retrieve" and "view_layer" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in LayerPermission Check. Error Details: ", str(e))
            return False

class SubLayerPermission(BasePermission):
    """
    Permission check for sublayer model
    """
    def has_permission(self, request, view):
        try:
            action = view.action
            user_id=request.user.id
            if request.user.is_superuser:
                return True
            if action =="list":
                layer_id=request.query_params.get("layer")
                project_id=Layer.objects.get(id=layer_id).theme.project.id
                organization_id=Project.active.get(id=project_id).organization.id
            elif action in ['retrieve','partial_update']:
                sub_layer_id=request.resolver_match.kwargs.get('pk')
                project_id= SubLayer.objects.get(id=sub_layer_id).layer.theme.project.id
                organization_id=Project.active.get(id=project_id).organization.id

            group_id=get_user_group(user_id,organization_id,project_id)

            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="list" and "view_sublayer" in permission_list:
                    return True
                elif action=="partial_update" and "change_sublayer" in permission_list:
                    return True
                elif action=="retrieve" and "view_sublayer" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in SubLayerPermission Check. Error Details: ", str(e))
            return False

class FeatureCollectionPermission(BasePermission):
    """
    Permission check for sublayer model
    """
    def has_permission(self, request, view):
        try:
            action = view.action
            user_id=request.user.id
            if request.user.is_superuser:
                return True
            if action =="list":
                layer_id=request.query_params.get("layer")
                project_id=Layer.objects.get(id=layer_id).theme.project.id
                organization_id=Project.active.get(id=project_id).organization.id

            elif action=="create":
                layer_id=request.data.get("layer",None)
                project_id=Layer.objects.get(id=layer_id).theme.project.id
                organization_id=Project.active.get(id=project_id).organization.id

            elif action in ['retrieve','partial_update']:
                feature_id=request.resolver_match.kwargs.get('pk')
                project_id= FeatureCollection.objects.get(id=feature_id).layer.theme.project.id
                organization_id=Project.active.get(id=project_id).organization.id

            group_id=get_user_group(user_id,organization_id,project_id)

            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="list" and "view_featurecollection" in permission_list:
                    return True
                elif action=="create" and "add_featurecollection" in permission_list:
                    return True
                elif action=="partial_update" and "change_featurecollection" in permission_list:
                    return True
                elif action=="retrieve" and "view_featurecollection" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in FeatureCollectionPermission Check. Error Details: ", str(e))
            return False

class ThemePermission(BasePermission):
    """
    Permission check for sublayer model
    """
    def has_permission(self, request, view):
        try:
            action = view.action
            user_id=request.user.id
            if request.user.is_superuser:
                return True
            if action =="list":
                project_id=request.query_params.get("project")
                organization_id=Project.active.get(id=project_id).organization.id

            elif action=="create":
                project_id=request.data.get("project",None)
                organization_id=Project.active.get(id=project_id).organization.id

            elif action in ['retrieve','partial_update']:
                theme_id=request.resolver_match.kwargs.get('pk')

                project_id= Theme.objects.get(id=theme_id).project.id
                organization_id=Project.active.get(id=project_id).organization.id

            group_id=get_user_group(user_id,organization_id,project_id)

            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="list" and "view_theme" in permission_list:
                    return True
                elif action=="create" and "add_theme" in permission_list:
                    return True
                elif action=="partial_update" and "change_theme" in permission_list:
                    return True
                elif action=="retrieve" and "view_theme" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in ThemePermission Check. Error Details: ", str(e))
            return False


class LayerGroupPermission(BasePermission):
    """
    Permission check for layer model
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id=request.user.id
            if request.user.is_superuser:
                return True

            if action =="list":
                theme_id=request.query_params.get("theme")
                project_id=Theme.objects.get(id=theme_id).project.id
                organization_id=Project.active.get(id=project_id).organization.id

            if action in ['retrieve','partial_update']:
                layer_group_id=request.resolver_match.kwargs.get('pk')
                project_id=LayerGroup.objects.get(id=layer_group_id).theme.project.id
                organization_id=Project.active.get(id=project_id).organization.id

            if action=="create":
                theme_id=request.data.get("theme",None)
                project_id=Theme.active.get(id=theme_id).project.id
                organization_id=Project.active.get(id=project_id).organization.id

            group_id=get_user_group(user_id,organization_id,project_id)

            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="list" and "view_layergroup" in permission_list:
                    return True
                elif action=="create" and "add_layergroup" in permission_list:
                    return True
                elif action=="partial_update" and "change_layergroup" in permission_list:
                    return True
                elif action=="retrieve" and "view_layergroup" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in LayerGroupPermission Check. Error Details: ", str(e))
            return False

class ProjectStylePermission(BasePermission):
    """
    Permission check for ProjectStyle
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id=request.user.id
            if request.user.is_superuser:
                return True

            if action =="list":
                project_id=request.query_params.get("project")
                organization_id=Project.active.get(id=project_id).organization.id

            if action in ['retrieve','partial_update']:
                project_style_id=request.resolver_match.kwargs.get('pk')
                print(project_style_id, "is project style")
                project_id=ProjectStyle.active.get(id=project_style_id).project.id
                organization_id=Project.active.get(id=project_id).organization.id

            if action=="create":
                project_id=request.data.get("project",None)
                organization_id=Project.active.get(id=project_id).organization.id

            group_id=get_user_group(user_id,organization_id,project_id)

            if group_id:
                permission_list=get_permission_list(group_id)
                if action=="list" and "view_projectstyle" in permission_list:
                    return True
                elif action=="create" and "add_projectstyle" in permission_list:
                    return True
                elif action=="partial_update" and "change_projectstyle" in permission_list:
                    return True
                elif action=="retrieve" and "view_projectstyle" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in ProjectStylePermission Check. Error Details: ", str(e))
            return False

class LayerAttributePermission(BasePermission):
    """
    Permission check for ProjectStyle
    """

    def has_permission(self, request, view):
        try:
            action = view.action
            user_id=request.user.id
            if request.user.is_superuser:
                return True

            if action =="list":
                layer_id=request.query_params.get('layer', None)
                project_id=Layer.active.get(id=layer_id).theme.project.id
                organization_id=Project.active.get(id=project_id).organization.id

            if action == 'retrieve':
                layer_attribute_id=request.resolver_match.kwargs.get('pk')
                project_id=LayerAttribute.active.get(id=layer_attribute_id).project.id
                organization_id=Project.active.get(id=project_id).organization.id

            group_id=get_user_group(user_id,organization_id,project_id)

            if group_id:
                permission_list=get_permission_list(group_id)
                if (action=="list" or action=="retrieve") and "view_projectstyle" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in LayerAttributePermission Check. Error Details: ", str(e))
            return False
