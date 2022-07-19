import environ
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from pgis_toolkit.maps.models import FeatureCollection, Layer, SubLayer, Theme
from pgis_toolkit.projects.models import Organization, Project
from pgis_toolkit.users.models import UserRole

# from users.models import User
User = get_user_model()
env = environ.Env()

def get_user_group(user_id,organization_id,project_id):
    user_role_qs=UserRole.active.select_related('organization','group','user','project')
    admin_level_role=user_role_qs.filter(user=user_id,organization=None,project=None).values('group')
    org_level_role=user_role_qs.filter(user=user_id,organization=organization_id,project=None).values('group')
    project_level_role=user_role_qs.filter(user=user_id,organization=organization_id,project=project_id).values('group')
    group_id=None
    if project_level_role:
        group_id=project_level_role[0]['group']
    elif org_level_role:
        group_id=org_level_role[0]['group']
    elif admin_level_role:
        group_id=admin_level_role[0]['group']
    return group_id



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
                permission_qs= Group.objects.get(id=group_id).permissions.all().values('codename')
                permission_list=[data['codename'] for data in permission_qs]
                if action=="create" and "add_layer" in permission_list:
                    return True
                elif action=="partial_update" and "change_layer" in permission_list:
                    return True
                elif action=="retrieve" and "view_layer" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in IsTaskAuthorized Permission Check. Error Details: ", str(e))
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
                permission_qs= Group.objects.get(id=group_id).permissions.all().values('codename')
                permission_list=[data['codename'] for data in permission_qs]
                if action=="list" and "view_sublayer" in permission_list:
                    return True
                elif action=="partial_update" and "change_sublayer" in permission_list:
                    return True
                elif action=="retrieve" and "view_sublayer" in permission_list:
                    return True
            return False
        except Exception as e:
            print("Error occured in IsTaskAuthorized Permission Check. Error Details: ", str(e))
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
                permission_qs= Group.objects.get(id=group_id).permissions.all().values('codename')
                permission_list=[data['codename'] for data in permission_qs]
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
            print("Error occured in IsTaskAuthorized Permission Check. Error Details: ", str(e))
            return False
