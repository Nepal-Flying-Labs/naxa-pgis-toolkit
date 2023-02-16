import json
import operator
import time
import uuid
from functools import reduce
from itertools import groupby

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.mail import send_mail
from django.db.models import F, Q
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
from rest_framework_simplejwt.views import TokenObtainPairView

from config.settings import base as settings
from pgis_toolkit.maps.models import ProjectMapConfig, Theme
from pgis_toolkit.projects.models import (
    DateTimeStamp,
    DefaultTheme,
    IsDeleted,
    Organization,
    Project,
)
from pgis_toolkit.users.models import PreliminaryUser, UserRole
from pgis_toolkit.users.permissions import (
    IsAuthorizedInviter,
    UpdatePreliminaryUserPermission,
)
from pgis_toolkit.utils.pagination import CustomPageNumberPagination

from .serializers import (
    CustomTokenObtainPairSerializer,
    PreliminaryUserListSerializer,
    PreliminaryUserSerializer,
    RequestingUserSerializer,
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
            org_proj_name = 'USAFIRI'
            if organization_name:
                org_proj_name=organization_name[0]+', USAFIRI'
                '''checking if organization exists'''
                if Organization.active.filter(name=organization_name[0]).exists():
                    return Response(data={'message': 'Your organization is already registered!'}, status=status.HTTP_400_BAD_REQUEST)
                '''creating organization object'''
                organization_instance = Organization.active.create(name=organization_name[0])
                request.data['organization'] = organization_instance.id
                request.data['group'] = int(env('ORGANIZATION_ADMIN'))
                request.data['project'] = None
            elif project_name:
                org_proj_name=project_name[0]+', USAFIRI'
                # project_name = request.data.pop('project_name', None)
                '''organization id is compulsory for sending project invitation'''
                if not project_name and not 'organization' in request.data:
                    return Response(data={'message': 'Params project_name and organization are required!'}, status=status.HTTP_400_BAD_REQUEST)
                if not organization or not Organization.active.filter(id=organization).exists():
                    return Response(data={'message': 'Valid Organization params is compulsory for a project related role!'}, status=status.HTTP_400_BAD_REQUEST)
                organization_inst = Organization.active.get(id=organization)
                if Project.active.filter(name=project_name[0],organization=organization_inst).exists():
                    return Response(data={'message': 'A project with the same name is already registered in your organization!'}, status=status.HTTP_400_BAD_REQUEST)
                project_instance = Project.active.create(name=project_name[0], organization=organization_inst)
                request.data['project'] = project_instance.id
                request.data['group'] = int(env('PROJECT_MANAGER'))
            else:
                '''checking for already existing organization and projects'''
                if not group or not Group.objects.filter(id=group).exists():
                    return Response(data={'message': 'params group is missing or group matching query does not exist!'}, status=status.HTTP_400_BAD_REQUEST)
                if int(group) == int(env('PGIS_WEB_APP_ADMINISTRATOR')):
                    request.data['organization'] = None
                    request.data['project'] = None
                elif int(group) == int(env('ORGANIZATION_ADMIN')):
                    request.data['project'] = None
                    if not organization or not Organization.active.filter(id=organization).exists():
                        return Response(data={'message': 'Organization params is invalid!'}, status=status.HTTP_400_BAD_REQUEST)
                    org_proj_name = Organization.active.get(id=int(organization)).name
                    org_proj_name = org_proj_name+', USAFIRI'
                elif int(group) == int(env('PROJECT_MANAGER')) or int(group) == int(env('DATA_COLLECTOR')):
                    if not project or not Project.active.filter(id=project).exists():
                        return Response(data={'message': 'Invalid project params or Project matching queryset does not exist!'}, status=status.HTTP_400_BAD_REQUEST)
                    project_inst = Project.active.get(id=project)
                    request.data['organization'] = project_inst.organization.id
                    org_proj_name=project_inst.name+', USAFIRI'
            '''create multiple or single preliminary user instances'''

            # created_object_list = []
            for email in email_list:
                if PreliminaryUser.active.filter(status='Pending', email=email, organization=request.data['organization'], project=request.data['project'], group=request.data['group']).exists():
                    role = Group.objects.get(id=request.data['group']).name
                    raise Exception(f'Invitation as {role} for the email: {email} already exists.')
                request.data['email'] = email
                request.data['email_verification_token'] = uuid.uuid4()
                serializer = PreliminaryUserSerializer(data=request.data)
                if serializer.is_valid():
                    created_object = serializer.save()
                    created_object_list.append(created_object)
                    '''email invitation'''
                    data = {
                    'role': created_object.group.name,
                    'proj_org': org_proj_name,
                    'link': f'{verify_url}{created_object.email_verification_token}',
                    'paragraph_1': f'You have been invited as {created_object.group.name} in USAFIRI platform. Please click on the link. {verify_url}{created_object.email_verification_token}',
                    # 'paragraph_1': f'You have been invited as {created_object.group.name} in USAFIRI platform. Please click on the link. {verify_url}{created_object.email_verification_token}',
                    }
                    template = 'email/email_invitation.html'
                    # template = 'email/email_request_demo.html'
                    html_message = render_to_string(template, data)
                    message = strip_tags(html_message)
                    # subject = 'Email Invitation, USAFIRI'
                    # name = data['proj_org']
                    subject = f"You're invited to join {org_proj_name}."
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
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
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
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

class PreliminaryUserUpdateAPIView(APIView):
    permission_classes = [UpdatePreliminaryUserPermission]
    '''resend, expire/delete user invitation'''
    def patch(self, request, pk, *args, **kwargs):
        try:
            errors=[]
            resend = request.data.get('resend', False)
            if not PreliminaryUser.objects.filter(pk=pk).exists():
                return Response(data={'message': 'Preliminary instance not found!'}, status=status.HTTP_400_BAD_REQUEST)
            instance = PreliminaryUser.objects.get(pk=pk)
            if resend:
                instance.status = 'Pending'
                instance.save()
                '''email invitation resend'''
                verify_url = settings.URL + '/verify-user/?token='
                if instance.organization:
                    email_org_name = instance.organization.name
                elif instance.project:
                    email_org_name = instance.project.name
                else:
                    email_org_name = 'USAFIRI'
                data = {
                'role': instance.group.name,
                'proj_org': email_org_name,
                'link': f'{verify_url}{instance.email_verification_token}',
                }
                template = 'email/email_invitation.html'
                html_message = render_to_string(template, data)
                message = strip_tags(html_message)
                name = data['proj_org']
                subject = f"You're invited! to join {name}, USAFIRI."
                from_email = settings.EMAIL_HOST_USER
                recipient_list = [instance.email]
                send_mail(subject, message, from_email, recipient_list,
                        html_message=html_message, fail_silently=False)
                return Response(data={'message': 'Resend email invitation successful.'}, status=200)
            else:
                '''expire/delete invitation'''
                serializer = PreliminaryUserSerializer(instance, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                else:
                    for er in serializer._errors:
                        errors.append(
                            {"errorName": er, "details": serializer._errors[er][0]})
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

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
                return Response(data={'message': 'Your token has expired!'}, status=status.HTTP_400_BAD_REQUEST)
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
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': f"Your role in project '{project_name}' as a {group_name} already exists. This invitation is disregarded as of now."})

                elif data_dict['organization']:
                    user_role=UserRole.active.filter(user=data_dict['user'],organization=data_dict['organization'],project=None)
                    if user_role.exists():
                        org_name=Organization.objects.get(id=data_dict['organization']).name
                        group_id=user_role.first().group.id
                        group_name=Group.objects.get(id=group_id).name
                        '''delete PreliminaryUserInstance once the job is done'''
                        preliminary_user_instance.delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': f"Your role in Organization '{org_name}' as a {group_name} already exists. This invitation is disregarded as of now."})

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
            return Response(data={'message': str(e)}, status=400)

'''NOT IN USE'''
'''User Invitation Table'''
class UserInvitationAPIView(APIView):
    permission_classes = [IsAuthenticated]
    # filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    # filterset_fields = ['status', 'project', 'organization', 'group']
    # search_fields = ['id', 'email']
    # ordering_fields = ['id', 'status', 'email', 'organization', 'project', 'group', 'uploaded_date']

    def get(self, request, *args, **kwargs):
        try:
            user_qs = PreliminaryUser.active.all()
            group_ids = UserRole.active.filter(active=True, user=request.user).values_list('group', flat=True)
            organization = request.query_params.get('organization', None)
            project = request.query_params.get('project', None)
            if project:
                '''only project level roles'''
                user_qs=user_qs.filter(project=project)
            elif organization:
                '''only organization and project level roles'''
                user_qs=user_qs.filter(organization=organization)
            elif request.user.is_superuser or int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
                user_qs=user_qs.filter(Q(group=int(env('PGIS_WEB_APP_ADMINISTRATOR')))|Q(group=int(env('ORGANIZATION_ADMIN'))))
            else:
                return Response (data={'message': 'organization or project params is missing!'}, status=400)

            'ordering'
            ordering = request.query_params.get('ordering', None)
            if ordering:
                user_qs = user_qs.order_by(ordering)
            else:
                user_qs = user_qs.order_by('-id')

            '''filtering'''
            filter_dict={}
            status=request.query_params.get('status', None)
            group=request.query_params.get('group', None)
            if status:
                filter_dict['status'] = status
            if group:
                filter_dict['group'] = group
            if filter_dict:
                user_qs=user_qs.filter(**filter_dict)

            '''search'''
            search_key = request.query_params.get('search', None)
            if search_key:
                filter_kwargs = {}
                search_fields = ['id', 'email']
                for field in search_fields:
                    filter_kwargs[field+'__icontains'] = search_key
                list_of_Q = [Q(**{key: val})
                                for key, val in filter_kwargs.items()]
                user_qs = user_qs.filter(
                    reduce(operator.or_, list_of_Q)) if search_fields else user_qs
            user_qs=user_qs.values('id', 'email','organization__name', 'project__name', 'group__name', 'status', 'uploaded_date')
            return Response(data=user_qs, status=200)
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)

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
                    'user': created_object.full_name,
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
        try:
            errors = []
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
                return Response(serializer.data, status=200)
            # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            for er in serializer._errors:
                errors.append({"errorName": er, "details": serializer._errors[er][0]})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Update not successful', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})


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
            ''''''
            # request_dict = request.query_params
            # request_keys = request_dict.keys()
            # '''removing the requesting user roles from userrole queryset'''
            # queryset = UserRole.active.exclude(user__id=request.user.id)
            # '''checking if the requesting user has a role assigned'''
            # if not UserRole.active.filter(Q(user__id=request.user.id) & Q(active=True)).exists():
            #     return Response(data={'message': 'No any user role of the requesting user found!'}, status=status.HTTP_400_BAD_REQUEST)
            # userrole_qs = UserRole.active.filter(Q(user__id=request.user.id) & Q(active=True))
            # user_role_list = userrole_qs.values_list('group__id', flat=True)
            # '''filtering queryset for web app administrator'''
            # if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in user_role_list:
            #     queryset = queryset.filter(group__id=int(env('ORGANIZATION_ADMIN')))
            # elif 'organization' in request_keys and request_dict['organization'] != "":
            #     organization = request_dict['organization']
            #     '''exclude all the pgis web administrator user roles'''
            #     queryset = queryset.exclude(group__id=int(env('PGIS_WEB_APP_ADMINISTRATOR')))
            #     if not userrole_qs.filter(organization__id=organization).exists():
            #         return Response(data={'message': 'No any role of the user found for the organization!'}, status=status.HTTP_400_BAD_REQUEST)
            #     userrole_qs = userrole_qs.filter(organization__id=organization)
            #     user_org_role_list = userrole_qs.values_list('group__id', flat=True)
            #     if int(env('ORGANIZATION_ADMIN')) in user_org_role_list:
            #         queryset = queryset.filter(organization__id=organization)
            #     elif 'project' in request_keys and request_dict['project'] != "":
            #         project = request_dict['project']
            #         '''exclude all the organization admin user roles'''
            #         queryset = queryset.exclude(group__id=int(env('ORGANIZATION_ADMIN')))
            #         if not userrole_qs.filter(project__id=project).exists():
            #             return Response(data={'message': 'No any role of the user found for the project in the organization!'}, status=status.HTTP_400_BAD_REQUEST)
            #         userrole_qs = userrole_qs.filter(project__id=project)
            #         user_org_proj_role_list = userrole_qs.values_list('group__id', flat=True)
            #         if int(env('PROJECT_MANAGER')) in user_org_proj_role_list:
            #             '''all users involved in the project excpet web administrator and organization admin'''
            #             queryset = queryset.filter(project_id=project)
            #         elif int(env('DATA_COLLECTOR')) in user_org_proj_role_list:
            #             '''exclude all the project manager user roles'''
            #             queryset = queryset.exclude(group__id=int(env('PROJECT_MANAGER')))
            #             '''user with roles data collector only'''
            #             queryset = queryset.filter(project__id=project)
            #         else:
            #             # queryset = queryset.none()
            #             return Response(data={'message': 'Your role does not allow you to view other user details!'}, status=status.HTTP_400_BAD_REQUEST)
            #     else:
            #         return Response(data={'message': 'Params project is missing!'}, status=status.HTTP_400_BAD_REQUEST)
            # else:
            #     return Response(data={'message': 'Params organization is missing!'}, status=status.HTTP_400_BAD_REQUEST)
            #     '''filter, search and order queryset'''
            # queryset = self.filter_queryset(queryset)
            # serializer = UserListSerializer(queryset, many=True, context={"request": request})
            ''''''
            '''checking if the requesting user has a role assigned'''
            role_qs=UserRole.active.filter(user__id=request.user.id, active=True)
            pre_user_qs = PreliminaryUser.active.all()
            if not role_qs.exists():
                return Response(data={'message': 'No any active role of the requesting user found!'}, status=status.HTTP_400_BAD_REQUEST)
            '''removing the requesting user roles from userrole queryset'''
            queryset = UserRole.active.exclude(user__id=request.user.id)
            group_ids = role_qs.values_list('group', flat=True)
            project=request.query_params.get('project', None)
            organization = request.query_params.get('organization', None)
            if project and Project.active.filter(id=project).exists():
                '''only project level roles'''
                queryset=queryset.filter(project=project)
                pre_user_qs=pre_user_qs.filter(project=project)
            elif organization and Organization.active.filter(id=organization).exists():
                '''organization and project level roles'''
                queryset=queryset.filter(organization=organization)
                pre_user_qs=pre_user_qs.filter(organization=organization)
            elif request.user.is_superuser or int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
                queryset=queryset.filter(Q(group=int(env('PGIS_WEB_APP_ADMINISTRATOR')))|Q(group=int(env('ORGANIZATION_ADMIN'))))
                pre_user_qs=pre_user_qs.filter(Q(group=int(env('PGIS_WEB_APP_ADMINISTRATOR')))|Q(group=int(env('ORGANIZATION_ADMIN'))))
            else:
                return Response (data={'message': 'organization or project params is missing!'}, status=400)
            '''filter, search and order queryset'''
            # queryset = self.filter_queryset(queryset)
            '''serialize'''
            serializer = UserListSerializer(queryset, many=True, context={"request": request})
            pre_user_serializer = PreliminaryUserListSerializer(pre_user_qs, many=True)

            data=serializer.data + pre_user_serializer.data
            return Response(data=data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def retrieve(self, request, pk, *args, **kwargs):
        try:
            user_instance = User.active.get(pk=pk)
            serializer = UserDetailSerializer(user_instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

'''Requesting user detail'''
''''''
class RequestUserDetailAPIView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, *args, **kwargs):
        try:
            user_instance = request.user
            if not user_instance:
                return Response(data={'message': 'Not logged in!'}, status=400)
            serializer = RequestingUserSerializer(user_instance)
            return Response(data=serializer.data, status=200)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

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
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": str(e)})

'''Email Invited User Status Table  >> NOT IN USE'''
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
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": str(error)})

'''users group list'''
@api_view(['GET'])
def user_group_list(request):
    try:
        # if not request.user.is_authenticated:
        #     return Response(status=status.HTTP_403_FORBIDDEN, data={"message": "You are not logged in."})
        # userrole_qs = UserRole.active.filter(user__id=request.user.id)
        # group_ids = userrole_qs.values_list('group__id', flat=True)
        # group_qs = Group.objects.all()
        # if request.user.is_superuser:
        #     group_qs = group_qs
        # elif int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
        #     group_qs = group_qs
        # elif 'organization' in request.query_params and request.query_params['organization'] != "":
        #     userrole_qs = userrole_qs.filter(organization__id=request.query_params['organization'])
        #     if not userrole_qs.exists():
        #         return Response(data={'message': 'No any user role found in the organization!'}, status=400)
        #     group_ids = userrole_qs.values_list('group__id', flat=True)
        #     if int(env('ORGANIZATION_ADMIN')) in group_ids:
        #         group_qs = group_qs.exclude(pk=int(env('PGIS_WEB_APP_ADMINISTRATOR')))
        # elif 'project' in request.query_params and request.query_params['project'] != "":
        #     project_id=request.query_params['project']
        #     userrole_qs = userrole_qs.filter(project__id=project_id)
        #     if not userrole_qs.exists():
        #         return Response(data={'message': 'No any user role found in the project!'}, status=400)
        #     group_id = userrole_qs[0].group.id
        #     if group_id == int(env('PROJECT_MANAGER')):
        #         group_qs = group_qs.filter(pk__in=[int(env('PROJECT_MANAGER')), int(env('DATA_COLLECTOR'))])
        #     elif group_id == int(env('DATA_COLLECTOR')):
        #         group_qs = group_qs.filter(pk=int(env('DATA_COLLECTOR')))
        # else:
        #     group_qs = None
        # serializer = UserGroupListSerializer(group_qs, many=True)
            '''checking if the requesting user has a role assigned'''
            role_qs=UserRole.active.filter(user__id=request.user.id, active=True)
            if not role_qs.exists():
                return Response(data={'message': 'No any active role of the requesting user found!'}, status=status.HTTP_400_BAD_REQUEST)
            group_ids = role_qs.values_list('group', flat=True)
            group_qs = Group.objects.all()

            project=request.query_params.get('project', None)
            organization = request.query_params.get('organization', None)
            if project and Project.active.filter(id=project).exists():
                '''only project level roles'''
                group_qs = group_qs.exclude(pk__in=[int(env('PGIS_WEB_APP_ADMINISTRATOR')), int(env('ORGANIZATION_ADMIN'))])
            elif organization and Organization.active.filter(id=organization).exists():
                '''organization and project level roles'''
                group_qs = group_qs.exclude(pk=int(env('PGIS_WEB_APP_ADMINISTRATOR')))
            elif request.user.is_superuser or int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
                group_qs = group_qs
            else:
                return Response (data={'message': 'organization or project params is missing!'}, status=400)
            data = group_qs.values('id', 'name').order_by('-id')
            return Response(data=data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

'''Send email to the user when forgot password button is clicked.'''
class ForgotPasswordEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            reset_url = settings.URL + '/reset-password/?token='
            username_or_email = request.data.get('username_or_email')
            if User.active.filter(Q(username=username_or_email) | Q(email=username_or_email)).exists():
                profile = User.active.filter(Q(username=username_or_email) | Q(email=username_or_email))
                if profile[0].email == username_or_email or profile[0].username == username_or_email:
                    user = profile[0]
                    user.email_verification_token = uuid.uuid4()
                    user.save()
                    '''email invitation'''
                    data = {
                    'username': user.username,
                    'link': f'{reset_url}{user.email_verification_token}',
                    }
                    template = 'email/reset_password.html'
                    html_message = render_to_string(template, data)
                    message = strip_tags(html_message)
                    subject = 'Reset Password, USAFIRI'
                    from_email = settings.EMAIL_HOST_USER
                    recipient_list = [user.email]
                    send_mail(subject, message, from_email, recipient_list,
                            html_message=html_message, fail_silently=False)
                    return Response(status=status.HTTP_200_OK, data={"message": "A reset password link is sent to your email. Please check it."})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": "Incorrect Email or no email found!"})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": str(e)})

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
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": str(e)})

'''change password'''
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
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
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"message": str(e)})

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

'''Landing page'''
@api_view(['GET'])
def landing_page(request, *args, **kwargs):
    try:
        userrole_qs = UserRole.active.filter(user__id=request.user.id, active=True)
        organization_ids = userrole_qs.exclude(organization=None).values_list('organization__id', flat=True).distinct()
        project_ids = userrole_qs.exclude(project=None).values_list('project__id', flat=True).distinct()
        group_ids = userrole_qs.values_list('group__id', flat=True).distinct()
        page, organization, project = '', None, None
        if request.user.is_superuser:
            page = '/organizations' #'organization_list'
        elif int(env('PGIS_WEB_APP_ADMINISTRATOR')) in group_ids:
            page = '/organizations' #'organization_list'
        elif not organization_ids.exists(): return Response(data={'message': 'No any active user role found for the user inside the organization!'}, status=400)
        elif organization_ids.count() > 1:
            page = '/organizations' #'organization_list'
        elif organization_ids.exists() and not project_ids.exists():
            organization = organization_ids.first()
            # page =  f'/organizations/{organization}/home' #'organization_home' #implement this once home page is made.
            page = f'/organizations/{organization}/projects' #'project_list' # delete this once home page is made.
        elif not project_ids.exists(): return Response(data={'message': 'No any active user role found for the user inside the project!'}, status=400)
        elif project_ids.count() > 1:
            organization = organization_ids.first()
            page = f'/organizations/{organization}/projects' #'project_list'
        else:
            '''inside_project'''
            organization = organization_ids.first()
            project = project_ids.first()
            page = f'/organizations/{organization}/projects/{project}/map' #'map_layers'
            if int(env('PROJECT_MANAGER')) in group_ids:
                project_status = Project.active.get(id=project).status
                if project_status == 'draft':
                    page = f'/organizations/{organization}/project-setup/{project}' # 'project_edit'
                else:
                    '''change this if required'''
                    page = f'/organizations/{organization}/projects/{project}/map' #'map_layers'
        if page == '': return Response(data={'message': 'No any active user role found for the user!'}, status=400)
        result = {'page': page, 'organization': organization, 'project': project}
        return Response(data=result, status=200)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Takes a set of user credentials and returns an access and refresh JSON web
    token pair to prove the authentication of those credentials.
    """
    serializer_class = CustomTokenObtainPairSerializer
