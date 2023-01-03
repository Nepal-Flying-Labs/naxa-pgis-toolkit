import operator
from functools import reduce

import environ
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from pgis_toolkit.projects.models import Organization, Project
from pgis_toolkit.users.models import UserRole

env = environ.Env()

'''This function filters out the project queryset and is used for ProjectViewset and ProjectLocationVectorTile'''
def get_project_queryset(request, user):
    try:
        if not request.GET.keys():
            return 'No request params is given!', 400
        request_keys = request.GET.keys()
        '''filter by organization'''
        if 'organization' not in request_keys or request.GET['organization'] == "":
            return 'Params organization is missing', 400
        organization_id = request.GET['organization']
        if not Organization.active.filter(id=organization_id).exists():
            return 'Organization matching queryset does not exist!', 400
        organization_project_qs = Project.active.select_related("organization").filter(organization__id=organization_id)
        '''superuser gets to see all project sites'''
        if user.is_superuser == True:
            organization_project_qs = organization_project_qs
        elif UserRole.active.filter(Q(user=user) & Q(active=True)).exists():
            userrole_qs = UserRole.active.filter(Q(user=user) & Q(active=True))
            user_role_list = userrole_qs.values_list('group__id', flat=True)
            if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in user_role_list:
                '''all projects visible if the user has web app administrator role'''
                organization_project_qs = organization_project_qs
            else:
                userrole_qs = userrole_qs.filter(organization__id=organization_id)
                '''now retrieve a list of group the user has been into inside the organization'''
                user_org_role_list = userrole_qs.values_list('group__id', flat=True)
                if int(env('ORGANIZATION_ADMIN')) in user_org_role_list:
                    '''all projects visible if the user has organization admin role amongst his roles'''
                    organization_project_qs = organization_project_qs
                else:
                    '''for user other than organization admin and pgis web administrator, projects are restricted only to the ones they work for.'''
                    user_org_proj_list = userrole_qs.values_list('project__id', flat=True)
                    organization_project_qs = organization_project_qs.filter(id__in=user_org_proj_list)
        else:
            return 'No any user role of the requesting user found!', 400
        '''search_key'''
        if 'search' in request_keys and request.GET['search'] != "":
            search_key = request.GET['search']
            search_fields = ['name', 'state__name', 'country__name']
            filter_kwargs = {}
            for field in search_fields:
                filter_kwargs[field+'__icontains'] = search_key
            list_of_Q = [Q(**{key: val})
                            for key, val in filter_kwargs.items()]
            organization_project_qs = organization_project_qs.filter(
                reduce(operator.or_, list_of_Q)) if search_fields else organization_project_qs
        '''filter by state'''
        if 'state' in request_keys and request.GET['state'] != "":
            state = request.GET['state']
            organization_project_qs = organization_project_qs.filter(state__id=state)
            '''filter by state'''
        elif 'country' in request_keys and request.GET['country'] != "":
            country = request.GET['country']
            organization_project_qs = organization_project_qs.filter(country__id=country)
        return organization_project_qs, 200
    except Exception as e:
        error = 'Error occured in get_project_queryset method. Details: '+ str(e)
        print(error)
        return str(e), 400
