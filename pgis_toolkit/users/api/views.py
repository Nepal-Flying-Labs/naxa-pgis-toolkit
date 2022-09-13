import json
import operator
import uuid
from functools import reduce
from itertools import groupby

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.mail import send_mail
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.views.decorators.csrf import ensure_csrf_cookie
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from config.settings import base as settings
from pgis_toolkit.projects.models import DateTimeStamp, IsDeleted, Organization, Project
from pgis_toolkit.users.models import PreliminaryUser, UserRole
from pgis_toolkit.users.permissions import IsAuthorizedInviter
from pgis_toolkit.utils.pagination import CustomPageNumberPagination

from .serializers import (
    PreliminaryUserListSerializer,
    PreliminaryUserSerializer,
    UserDetailSerializer,
    UserGroupListSerializer,
    UserGroupPermissionsSerializer,
    UserListSerializer,
    UserRoleSerializer,
    UserSerializer,
)

User = get_user_model()

import environ

env = environ.Env()

# class UserViewSet(RetrieveModelMixin, ListModelMixin, UpdateModelMixin, GenericViewSet):
#     serializer_class = UserSerializer
#     queryset = User.objects.all()
#     lookup_field = "username"

#     def get_queryset(self, *args, **kwargs):
#         assert isinstance(self.request.user.id, int)
#         return self.queryset.filter(id=self.request.user.id)

#     @action(detail=False)
#     def me(self, request):
#         serializer = UserSerializer(request.user, context={"request": request})
#         return Response(status=status.HTTP_200_OK, data=serializer.data)



'''
for project invite, organzation is required in payload.
handles multiple email in the form: ["example@gmail.com", "example2@gmail.com"]
'''
class PreliminaryUserAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAuthorizedInviter]
    '''http://localhost:8000/api/users/preliminary_user_create/'''

    def post(self, request, *args, **kwargs):
        errors=[]
        project_instance, organization_instance = None, None
        try:
            verify_url = settings.URL + '/verify-user/?token='
            request.data._mutable = True
            email_list = request.data.get('email', None)
            if not email_list:
                return Response(data={'message': 'Params email is missing!'}, status=status.HTTP_400_BAD_REQUEST)
            email_list = json.loads(email_list)
            organization_name = request.data.pop('organization_name', None)
            project_name = request.data.pop('project_name', None)
            group = request.data.get('group', None)
            organization = request.data.get('organization', None)
            project = request.data.get('project', None)
            created_object_list = []
            if organization_name:
                '''checking if organization exists'''
                if Organization.active.filter(name=organization_name[0]).exists():
                    return Response(data={'message': 'Your organization is already registered!'}, status=status.HTTP_400_BAD_REQUEST)
                '''creating organization object'''
                organization_instance = Organization.active.create(name=organization_name[0])
                request.data['organization'] = organization_instance.id
                # '''checking if group exists already'''
                # if Group.objects.filter(name='Organization Admin').exists():
                #     request.data['group'] = Group.objects.get(name='Organization Admin').id
                # else:
                #     '''creating new group object'''
                #     group_instance = Group.objects.create(name='Organization Admin')
                #     request.data['group'] = group_instance.id
                request.data['group'] = int(env('ORGANIZATION_ADMIN'))
            elif project_name:
                # project_name = request.data.pop('project_name', None)
                '''organization id is compulsory for sending project invitation'''
                if not project_name and not 'organization' in request.data:
                    return Response(data={'message': 'Params project_name and organization are required!'}, status=status.HTTP_400_BAD_REQUEST)
                if not organization or not Organization.active.filter(id=organization).exists():
                    return Response(data={'message': 'Valid Organization params is compulsory for a project related role!'}, status=status.HTTP_400_BAD_REQUEST)
                organization_inst = Organization.active.get(id=organization)
                if Project.active.filter(Q(name=project_name[0]) & Q(organization=organization_inst)).exists():
                    return Response(data={'message': 'A project with the same name is already registered in your organization!'}, status=status.HTTP_400_BAD_REQUEST)
                project_instance = Project.active.create(name=project_name[0], organization=organization_inst)
                request.data['project'] = project_instance.id
                # '''checking if group exists already'''
                # if Group.objects.filter(name='Project Manager').exists():
                #     request.data['group'] = Group.objects.get(name='Project Manager').id
                # else:
                #     '''creating new group object'''
                #     group_instance = Group.objects.create(name='Project Manager')
                #     request.data['group'] = group_instance.id
                request.data['group'] = int(env('PROJECT_MANAGER'))
            else:
                '''checking for already existing organization and projects'''
                if not group or not Group.objects.filter(id=group).exists():
                    return Response(data={'message': 'params group is missing or group matching query does not exist!'}, status=status.HTTP_400_BAD_REQUEST)
                if int(group) == int(env('PGIS_WEB_APP_ADMINISTRATOR')):
                    request.data.pop('organization', None)
                    request.data.pop('project', None)
                elif int(group) == int(env('ORGANIZATION_ADMIN')):
                    request.data.pop('project', None)
                    if not organization or not Organization.active.filter(id=organization).exists():
                        return Response(data={'message': 'Organization params is invalid!'}, status=status.HTTP_400_BAD_REQUEST)
                elif int(group) == int(env('PROJECT_MANAGER')) or int(group) == int(env('DATA_COLLECTOR')):
                    if not project or not Project.active.filter(id=project).exists():
                        return Response(data={'message': 'Invalid project params or Project matching queryset does not exist!'}, status=status.HTTP_400_BAD_REQUEST)
                    project_inst = Project.active.get(id=project)
                    request.data['organization'] = project_inst.organization.id
            '''create multiple or single preliminary user instances'''
            # created_object_list = []
            for email in email_list:
                request.data['email'] = email
                request.data['email_verification_token'] = uuid.uuid4()
                serializer = PreliminaryUserSerializer(data=request.data)
                if serializer.is_valid():
                    created_object = serializer.save()
                    created_object_list.append(created_object)
                    '''email invitation'''
                    data = {
                    'paragraph_1': f'You have been invited as {created_object.group.name} in USAFIRI platform. Please click on the link to verfiy and continue further steps: {verify_url}{created_object.email_verification_token}',
                    }
                    template = 'email/email_request_demo.html'
                    html_message = render_to_string(template, data)
                    message = strip_tags(html_message)
                    subject = 'Email Verification, USAFIRI'
                    from_email = settings.EMAIL_HOST_USER
                    recipient_list = [created_object.email]
                    send_mail(subject, message, from_email, recipient_list,
                            html_message=html_message, fail_silently=False)
                else:
                    for er in serializer._errors:
                        errors.append(
                            {'errorName': er, 'details': serializer._errors[er][0]})
                    if organization_instance:
                        organization_instance.delete()
                    if project_instance:
                        project_instance.delete()
                    for obj in created_object_list:
                        obj.delete()
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
            if organization_instance:
                return Response(data={'message': 'Email Invitation Successful!', 'organization': organization_instance.id}, status=status.HTTP_200_OK)
            elif project_instance:
                return Response(data={'message': 'Email Invitation Successful!', 'project': project_instance.id}, status=status.HTTP_200_OK)
            else:
                return Response(data={'message': 'Email Invitation Successful!'}, status=status.HTTP_200_OK)
        except Exception as e:
            if organization_instance:
                organization_instance.delete()
            if project_instance:
                project_instance.delete()
            errors.append({'details': str(e)})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'Message': 'Dataset not created', 'Error': errors})

'''email verification, create user role for already registered users and send details of the preliminary user object in resposne'''
class PreliminaryUserVerificationAPIView(APIView):
    '''http://localhost:8000/api/users/preliminary_user_verify?token=cd72216e-a08d-456f-a72c-8f91ca9ca61c'''
    permission_classes = [AllowAny]
    def get(self, request, *args, **kwargs):
        errors=[]
        try:
            token = request.query_params.get('token', None)
            if not token:
                return Response(data={'message': 'Query Params token is required!'}, status=status.HTTP_400_BAD_REQUEST)
            if not PreliminaryUser.objects.filter(Q(email_verification_token=token) & Q(status='Pending')).exists():
                return Response(data={'message': 'PreliminaryUser matching queryset does not exists or your token has expired!'}, status=status.HTTP_400_BAD_REQUEST)
            preliminary_user_instance = PreliminaryUser.objects.get(Q(email_verification_token=token) & Q(status='Pending'))
            serializer = PreliminaryUserSerializer(preliminary_user_instance)
            data_dict = dict(serializer.data)
            '''checking whether the user is already registered'''
            if User.active.filter(email=preliminary_user_instance.email).exists():
                data_dict['user'] = User.active.get(email=preliminary_user_instance.email).id
                data_dict['user_created'] = True

                '''Restrict if any role of user within project or organization already exists'''
                if data_dict['project']:
                    user_role=UserRole.active.filter(user=data_dict['user'],project=data_dict['project'])
                    if user_role.exists():
                        project_name=Project.objects.get(id=data_dict['project']).name
                        group_id=user_role.first().group.id
                        group_name=Group.objects.get(id=group_id).name
                        '''delete PreliminaryUserInstance once the job is done'''
                        preliminary_user_instance.delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': f"Your role in project '{project_name}' as a {group_name} already exists"})

                elif data_dict['organization']:
                    user_role=UserRole.active.filter(user=data_dict['user'],organization=data_dict['organization'],project=None)
                    if user_role.exists():
                        org_name=Organization.objects.get(id=data_dict['organization']).name
                        group_id=user_role.first().group.id
                        group_name=Group.objects.get(id=group_id).name
                        '''delete PreliminaryUserInstance once the job is done'''
                        preliminary_user_instance.delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': f"Your role in Organization '{org_name}' as a {group_name} already exists"})

                '''creating new user role for already registered user'''
                user_role_serializer = UserRoleSerializer(data=data_dict)
                if user_role_serializer.is_valid():
                    user_role_serializer.save()
                    '''delete PreliminaryUserInstance once the job is done'''
                    preliminary_user_instance.delete()
                    return Response(data=data_dict, status=status.HTTP_200_OK)
                    # return Response(data={'message': 'Successully created new user role.', 'data': data_dict}, status=status.HTTP_200_OK)
                else:
                    for er in user_role_serializer._errors:
                        errors.append({"errorName": er, "details": serializer._errors[er][0]})
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
            else:
                data_dict['user_created'] = False
                return Response(data=data_dict, status=status.HTTP_200_OK)
        except Exception as e:
            return Response('Error: ' + str(e))

'''Viewset to CRUD operations of user model'''
class UserViewSet(viewsets.ModelViewSet):
    queryset = UserRole.active.all()
    serializer_class = UserSerializer
    http_method_names = ['get', 'post', 'patch']
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['organization', 'project', 'group']
    search_fields = ['id', 'user__full_name', 'user__email', 'organization__name', 'project__name', 'group__name']
    ordering_fields = ['id', 'user__full_name', 'user__email', 'organization__name', 'project__name', 'group__name']

    def get_permissions(self):
        if self.action == 'list' or self.action == 'retrieve' or self.action == 'update' or self.action == 'partial_update':
            permission_classes = [IsAuthenticated]
        elif self.action == 'create':
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        errors = []
        created_object = None
        user_role_obj = None
        try:
            verify_url = settings.URL + '/api/users/email_verify/?token='
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                created_object = serializer.save()
                email = serializer.validated_data.get('email')
                token = request.data.get('email_verification_token')
                '''Activating account of users from email invitaion'''
                if PreliminaryUser.objects.filter(Q(email=email) & Q(email_verification_token=token) & Q(status='Pending')).exists():
                    preliminary_user_instance = PreliminaryUser.objects.get(Q(email=email) & Q(email_verification_token=token))
                    if preliminary_user_instance.email_verification_token:
                        email_verified = True
                        created_object.email_verification_token = preliminary_user_instance.email_verification_token
                        created_object.is_active = True
                        created_object.save()
                else:
                    email_verified = False
                    if not request.data.get('organization') or not request.data.get('project'):
                        raise Exception('No organization or project params!')
                    uuid_code = uuid.uuid4()
                    created_object = serializer.save(
                        email_verification_token=uuid_code)
                    created_object.set_password(request.data['password'])
                    created_object.save()
                    '''send email for verification'''
                    data = {
                    'paragraph_1': f'Click in the link to verify and activate your account: {verify_url}{uuid_code}',
                    }
                    template = 'email/email_request_demo.html'
                    html_message = render_to_string(template, data)
                    message = strip_tags(html_message)
                    subject = 'User Verification, USAFIRI'
                    from_email = settings.EMAIL_HOST_USER
                    recipient_list = [created_object.email]
                    send_mail(subject, message, from_email, recipient_list,
                            html_message=html_message, fail_silently=False)

                '''create user role'''
                request.data._mutable=True
                request.data['user'] = created_object.id
                if not 'project' in request.data.keys():
                    request.data['project'] = None
                user_role_serializer = UserRoleSerializer(data=request.data)
                if user_role_serializer.is_valid():
                    user_role_obj = user_role_serializer.save()
                else:
                    for er in user_role_serializer._errors:
                        errors.append({"errorName": er, "details": serializer._errors[er][0]})
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
                if email_verified == True:
                    '''activating the user role after verification'''
                    user_role_obj.active = True
                    user_role_obj.save()
                    '''deleting PreliminaryUser instance since the user is now registered!'''
                    preliminary_user_instance.delete()
                    return Response(data={'message': 'User Successfully Registered. Please proceed to login.'}, status=status.HTTP_200_OK)
                else:
                    return Response(data={'message': 'User Successfully Registered. To activate your account, verfiy by the link sent to your email.'}, status=status.HTTP_200_OK)
            else:
                for er in serializer._errors:
                    errors.append(
                        {"errorName": er, "details": serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            if created_object:
                User.active.get(id=created_object.id).delete()
            if user_role_obj:
                UserRole.objects.get(id=user_role_obj.id).delete()
            errors.append({"error": str(e)})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "User Not Registered", "Error": errors})

    def partial_update(self, request, pk=None):
        user = User.active.get(pk=pk)
        if isinstance(request.data.get('image'), str):
            request.data._mutable = True
            request.data.pop('image', None)
            user.image = None
            user.image_thumbnail = None
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            serializer = UserSerializer(user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_403_FORBIDDEN)

    # def list(self, request, *args, **kwargs):
    #     '''
    #     Web App Administrator: User with this role can't have any other role since this role is similar to super admin.
    #     For other roles, User can have multiple roles with different organizations but must have single role within each organization.
    #     http://localhost:8000/api/users/user/?organization=&project=&page=1&limit=10
    #     '''
    #     try:
    #         paginator = CustomPageNumberPagination()
    #         if not request.user.is_authenticated:
    #             return Response(status=status.HTTP_403_FORBIDDEN, data={"message": "You are not logged in."})
    #         request_dict = request.query_params
    #         request_keys = request_dict.keys()
    #         '''removing the request user from user queryset'''
    #         queryset = self.queryset.exclude(id=request.user.id)
    #         '''checking if the requesting user has a role assigned'''
    #         if not UserRole.active.filter(user__id=request.user.id).exists():
    #             return Response(data={'message': 'No any user role of the requesting user found!'}, status=status.HTTP_400_BAD_REQUEST)
    #         user_role_instance = UserRole.active.filter(user__id=request.user.id).first()
    #         organization = None
    #         '''filtering queryset for web app administrator'''
    #         if user_role_instance.group.id == int(env('PGIS_WEB_APP_ADMINISTRATOR')):
    #             queryset = queryset
    #         elif 'organization' in request_keys and request_dict['organization'] != "":
    #             organization = request_dict['organization']
    #             '''making organization compulsory and checking if any role of the request exists for the given organization'''
    #             if UserRole.active.filter(Q(user__id=request.user.id) & Q(organization__id=organization)).exists():
    #                 user_role_instance = UserRole.active.get(Q(user__id=request.user.id) & Q(organization__id=organization))
    #             else:
    #                 return Response(data={'message': 'No any user role of the requesting user found for the organization!'}, status=status.HTTP_400_BAD_REQUEST)
    #             '''filtering queryset according to the role of the user in the organization'''
    #             if user_role_instance.group.id == int(env('ORGANIZATION_ADMIN')):
    #                 org_user_ids = UserRole.active.filter(organization__id=organization).values_list('user__id', flat=True)
    #                 queryset = queryset.filter(id__in=org_user_ids)
    #                 '''filtering queryset according to users in a project'''
    #             elif 'project' in request_keys and request_dict['project'] != "":
    #                 project = request_dict['project']
    #                 if user_role_instance.group.id == int(env('PROJECT_MANAGER')):
    #                     project_user_ids = UserRole.active.filter(project__id=project).values_list('user__id', flat=True)
    #                     queryset = queryset.filter(id__in=project_user_ids)
    #                     '''filtering queryset in a project of the same role i.e. data collector'''
    #                 elif user_role_instance.group.id == int(env('DATA_COLLECTOR')):
    #                     group_user_ids = UserRole.active.filter(Q(project__id=project) & Q(group__id=user_role_instance.group.id)).values_list('user__id', flat=True)
    #                     queryset = queryset.filter(id__in=group_user_ids)
    #                 else:
    #                     '''return empty queryset when no any role is validated '''
    #                     queryset = None
    #             else:
    #                 return Response(data={'message': 'Params project is required!'}, status=status.HTTP_400_BAD_REQUEST)
    #         else:
    #             return Response(data={'message': 'Params organization is required!'}, status=status.HTTP_400_BAD_REQUEST)

    #         '''Search'''
    #         if 'search_key' in request_keys and request_dict['search_key'] != '':
    #             searched_queryset = None
    #             search_fields = ['full_name', 'contact', 'email']
    #             filter_kwargs = {}
    #             for field in search_fields:
    #                 filter_kwargs[field+'__icontains'] = request_dict['search_key']
    #             list_of_Q = [Q(**{key: val}) for key, val in filter_kwargs.items()]
    #             queryset = queryset.filter(reduce(operator.or_, list_of_Q)) if search_fields else queryset

    #         '''Sorting'''
    #         if 'order_by' in request_keys and request_dict['order_by'] != '':
    #             queryset = queryset.order_by(request_dict['order_by'] )

    #         '''Group by'''
    #         if 'group_by' in request_keys and request_dict['group_by'] != '':
    #             group_by = request_dict['group_by']
    #             if group_by == "project":
    #                 user_ids = list(queryset.values_list('id', flat=True))
    #                 user_role_qs = UserRole.active.filter(user__id__in=user_ids)
    #                 project_list = list(user_role_qs.values_list('project', flat=True).distinct())
    #                 data_dict = {}
    #                 for project in project_list:
    #                     project_name = Project.active.get(id=project).name
    #                     data_dict[project_name] = user_role_qs.filter(project__id=project).values('user__image_thumbnail', 'user__full_name', 'project__name', 'group__name')
    #                 return Response(data_dict, status=status.HTTP_200_OK)
    #         '''Paginate Queryset'''
    #         paginated_queryset = paginator.paginate_queryset(queryset, request)
    #         serializer = UserListSerializer(
    #             paginated_queryset, many=True, context={"request": request})
    #         return paginator.get_paginated_response(data=serializer.data)
    #     except Exception as e:
    #         return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def list(self, request, *args, **kwargs):
        '''
        User can have multiple roles with different organizations but must have single role within each organization.
        1. Web App Administrator can see all user roles
        2. Organization Admin can see all user roles except 1
        3. Project Manager can see all user roles except 1 and 2
        4. Data Collector can see only themselves.
        http://localhost:8000/api/users/user/?organization=&project=&group=&ordering=&search=
        '''
        try:
            # if not request.user.is_authenticated:
            #     return Response(status=status.HTTP_403_FORBIDDEN, data={"message": "You are not logged in."})
            request_dict = request.query_params
            request_keys = request_dict.keys()
            '''removing the requesting user roles from userrole queryset'''
            queryset = UserRole.active.exclude(user__id=request.user.id)
            '''checking if the requesting user has a role assigned'''
            if not UserRole.active.filter(Q(user__id=request.user.id) & Q(active=True)).exists():
                return Response(data={'message': 'No any user role of the requesting user found!'}, status=status.HTTP_400_BAD_REQUEST)
            userrole_qs = UserRole.active.filter(Q(user__id=request.user.id) & Q(active=True))
            user_role_list = userrole_qs.values_list('group__id', flat=True)
            '''filtering queryset for web app administrator'''
            if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in user_role_list:
                queryset = queryset.filter(group__id=int(env('ORGANIZATION_ADMIN')))
            elif 'organization' in request_keys and request_dict['organization'] != "":
                organization = request_dict['organization']
                '''exclude all the pgis web administrator user roles'''
                queryset = queryset.exclude(group__id=int(env('PGIS_WEB_APP_ADMINISTRATOR')))
                if not userrole_qs.filter(organization__id=organization).exists():
                    return Response(data={'message': 'No any role of the user found for the organization!'}, status=status.HTTP_400_BAD_REQUEST)
                userrole_qs = userrole_qs.filter(organization__id=organization)
                user_org_role_list = userrole_qs.values_list('group__id', flat=True)
                if int(env('ORGANIZATION_ADMIN')) in user_org_role_list:
                    queryset = queryset.filter(organization__id=organization)
                elif 'project' in request_keys and request_dict['project'] != "":
                    project = request_dict['project']
                    '''exclude all the organization admin user roles'''
                    queryset = queryset.exclude(group__id=int(env('ORGANIZATION_ADMIN')))
                    if not userrole_qs.filter(project__id=project).exists():
                        return Response(data={'message': 'No any role of the user found for the project in the organization!'}, status=status.HTTP_400_BAD_REQUEST)
                    userrole_qs = userrole_qs.filter(project__id=project)
                    user_org_proj_role_list = userrole_qs.values_list('group__id', flat=True)
                    if int(env('PROJECT_MANAGER')) in user_org_proj_role_list:
                        '''all users involved in the project excpet web administrator and organization admin'''
                        queryset = queryset.filter(project_id=project)
                    elif int(env('DATA_COLLECTOR')) in user_org_proj_role_list:
                        '''exclude all the project manager user roles'''
                        queryset = queryset.exclude(group__id=int(env('PROJECT_MANAGER')))
                        '''user with roles data collector only'''
                        queryset = queryset.filter(project__id=project)
                    else:
                        # queryset = queryset.none()
                        return Response(data={'message': 'Your role does not allow you to view other user details!'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response(data={'message': 'Params project is missing!'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response(data={'message': 'Params organization is missing!'}, status=status.HTTP_400_BAD_REQUEST)
                '''filter, search and order queryset'''
            queryset = self.filter_queryset(queryset)
            serializer = UserListSerializer(queryset, many=True, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def retrieve(self, request, pk, *args, **kwargs):
        user_instance = User.active.get(pk=pk)
        serializer = UserDetailSerializer(user_instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

'''Verify self registered user using token sent to their mail and activate their account.'''
class EmailConfirmationAPIView(APIView):
    permission_classes = [AllowAny]
    '''http://localhost:8000/api/users/email_verify/?token=5f53cbfd-de7b-45d9-b90a-5c364be8b0a9'''
    def post(self, request, *args, **kwargs):
        try:
            token = request.query_params.get('token', None)
            if not token or not User.active.filter(email_verification_token=token).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "token query_params is missing or token matching user query does not exist!"})
            user_instance = User.active.get(email_verification_token=token)
            user_instance.is_active = True
            user_instance.save()
            return Response(status=status.HTTP_200_OK, data={"message": "Account verified and activated! You can now log in to the system."})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "Error!", "Details": str(e)})

'''Email Invited User Status Table'''
class PreliminaryUserListView(generics.ListAPIView):
    queryset = PreliminaryUser.active.all()
    serializer_class = PreliminaryUserListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['organization', 'project', 'group', 'status']
    search_fields = ['id', 'email', 'organization__name', 'project__name', 'group__name']
    ordering_fields = ['id', 'email', 'organization__name', 'project__name', 'group__name', 'last_updated']

class UserPermissionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    '''user permissions'''
    # def list(self, request, *args, **kwargs):
    #     try:
    #         if not request.user.is_authenticated:
    #             return Response(status=status.HTTP_403_FORBIDDEN, data={"message": "You are not logged in."})
    #         group_ids = UserRole.active.filter(user__id=request.user.id).values_list('group__id', flat=True)
    #         queryset = Group.objects.filter(pk__in=group_ids)
    #         serializer = UserGroupPermissionsSerializer(
    #             queryset, many=True)
    #         raw_data = serializer.data
    #         permissions_list = []
    #         for data in raw_data:
    #             permissions_list += data['permissions']
    #         def addition(n):
    #             return n.lower().replace(" ", "_")
    #         result = map(addition, permissions_list)
    #         return Response(status=status.HTTP_200_OK, data={"permissions": result})
    #     except Exception as error:
    #         return Response(status=status.HTTP_400_BAD_REQUEST, data={"Error Message": str(error)})

    '''user group permissions'''
    '''http://localhost:8000/api/users/permissions/?organization=&project=2'''
    def list(self, request, *args, **kwargs):
        try:
            # def modify(perm):
            #     return perm.lower().replace(" ", "_")
            if not request.user.is_authenticated:
                return Response(status=status.HTTP_403_FORBIDDEN, data={"message": "You are not logged in."})
            userrole_qs = UserRole.active.filter(user__id=request.user.id)
            group_ids = userrole_qs.values_list('group__id', flat=True)
            queryset = None
            if request.user.is_superuser:
                perm_qs=Permission.objects.all().values('codename')
                permissions_list=[]
                for q in perm_qs:
                    permissions_list.append(q['codename'])
                # result = map(modify, permissions_list)
                return Response(status=status.HTTP_200_OK, data={"permissions": permissions_list})

            elif int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
                queryset = Group.objects.get(pk=int(env('PGIS_WEB_APP_ADMINISTRATOR')))

            elif 'organization' in request.query_params and request.query_params['organization'] != "":
                userrole_qs = userrole_qs.filter(organization__id=request.query_params['organization'])
                group_ids = userrole_qs.values_list('group__id', flat=True)
                if int(env('ORGANIZATION_ADMIN')) in group_ids:
                    queryset = Group.objects.get(pk=int(env('ORGANIZATION_ADMIN')))

            elif 'project' in request.query_params and request.query_params['project'] != "":
                project_id=request.query_params['project']
                organization_id=Project.active.get(id=project_id).organization.id

                userrole_qs = userrole_qs.filter(organization__id=organization_id)
                group_ids = userrole_qs.values_list('group__id', flat=True)
                if int(env('ORGANIZATION_ADMIN')) in group_ids:
                    queryset = Group.objects.get(pk=int(env('ORGANIZATION_ADMIN')))
                else:
                    userrole_qs = userrole_qs.filter(project__id=project_id)
                    '''a user has a single role in a particular project'''
                    queryset = Group.objects.get(pk=userrole_qs[0].group.id) if userrole_qs.exists() else None
            if queryset == None:
                return Response(data={'permissions':[]}, status=200)
                # return Response(data={'message': 'organization or project params or user role not found!'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = UserGroupPermissionsSerializer(
                queryset, many=False)
            permissions_list = serializer.data['permissions']
            # result = map(modify, permissions_list)
            return Response(status=status.HTTP_200_OK, data={"permissions": permissions_list})
        except Exception as error:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"Error Message": str(error)})

'''users group list'''
@api_view(['GET'])
def user_group_list(request):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_403_FORBIDDEN, data={"message": "You are not logged in."})
    group_qs = Group.objects.all()
    serializer = UserGroupListSerializer(group_qs, many=True)
    return Response(data=serializer.data, status=status.HTTP_200_OK)

'''Send email to the user when forgot password button is clicked.'''
class ForgotPasswordEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            reset_url = settings.URL + '/api/users/reset_password/?token='
            username_or_email = request.data.get('username_or_email')
            if User.active.filter(Q(username=username_or_email) | Q(email=username_or_email)).exists():
                profile = User.active.filter(Q(username=username_or_email) | Q(email=username_or_email))
                if profile[0].email == username_or_email or profile[0].username == username_or_email:
                    user = profile[0]
                    user.email_verification_token = uuid.uuid4()
                    user.save()
                    '''email invitation'''
                    data = {
                    'paragraph_1': f'Click in the link to reset your password: {reset_url}{user.email_verification_token}',
                    }
                    template = 'email/email_request_demo.html'
                    html_message = render_to_string(template, data)
                    message = strip_tags(html_message)
                    subject = 'Password Reset Verification, USAFIRI'
                    from_email = settings.EMAIL_HOST_USER
                    recipient_list = [user.email]
                    send_mail(subject, message, from_email, recipient_list,
                            html_message=html_message, fail_silently=False)
                    return Response(status=status.HTTP_200_OK, data={"message": "A reset password link is sent to your email. Please check it."})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "Incorrect Email or no email found!"})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "Error!", "Details": str(e)})

'''Reset password from the reset link sent to email'''
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            email_verification_token = self.request.query_params.get('token')
            password1 = request.data.get("new_password1")
            password2 = request.data.get("new_password2")
            if password1 == password2:
                if User.active.filter(email_verification_token=email_verification_token).exists():
                    profile = User.active.filter(
                        email_verification_token=email_verification_token)
                    user = profile[0]
                    user.set_password(password1)
                    # user.email_verification_token = ''  # change
                    user.save()
                    return Response(status=status.HTTP_200_OK, data={"message": "Password reset successful. Please Login!"})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "Invalid token!"})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "New Passwords did not match!"})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "Error!", "Details": str(e)})

'''change password'''
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        old_password = request.data["old_password"]
        new_password1 = request.data["new_password1"]
        new_password2 = request.data["new_password2"]
        '''validating old password'''
        user = User.active.get(id=request.user.id)
        check_old_password = user.check_password(old_password)
        if check_old_password:
            if new_password1 == new_password2:
                user.set_password(new_password1)
                # user.is_password_changed = True
                user.save()
                return Response({'message': 'Password Change Succesful!'})
            else:
                return Response({"message": "New passwords don't match!"})
        else:
            return Response({"message": "Your old password is wrong!"})


'''activate/deactivate/delete user role'''
class UserRoleUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        try:
            errors=[]
            if not UserRole.active.filter(pk=pk).exists():
                return Response(data={'message': 'User Role not found!'}, status=status.HTTP_400_BAD_REQUEST)
            user_role = UserRole.active.get(pk=pk)
            serializer = UserRoleSerializer(user_role, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                for er in serializer._errors:
                    errors.append(
                        {"errorName": er, "details": serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

@ ensure_csrf_cookie
def set_csrf_token(request):
    """
    This will be `/api/set-csrf-cookie/` on `urls.py`
    """
    return JsonResponse({"details": "CSRF cookie set"})
