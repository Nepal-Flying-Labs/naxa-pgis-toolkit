import uuid
import json
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import action, permission_classes
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework import status, viewsets
from rest_framework.response import Response
from django.contrib.auth.models import Group
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from config.settings import base as settings
from django.db.models import Q

from pgis_toolkit.projects.models import DateTimeStamp, IsDeleted, Organization, Project
from pgis_toolkit.users.models import PreliminaryUser

from .serializers import UserSerializer, PreliminaryUserSerializer, UserRoleSerializer

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
    permission_classes = [IsAuthenticated]
    '''http://localhost:8000/api/users/preliminary_user_create/'''

    def post(self, request, *args, **kwargs):
        errors=[]
        try:
            verify_url = settings.URL + '/api/users/preliminary_user_verify/?token='
            request.data._mutable = True
            email_list = request.data.get('email', None)
            if not email_list:
                return Response(data={'message': 'Params email is missing!'}, status=status.HTTP_400_BAD_REQUEST)
            email_list = json.loads(email_list)
            organization_name = request.data.pop('organization_name', None)
            group = request.data.get('group', None)
            if not group or not Group.objects.filter(id=group).exists():
                return Response(data={'message': 'params group is missing or group matching query does not exist!'}, status=status.HTTP_400_BAD_REQUEST)
            project_name = None
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
            else:
                project_name = request.data.pop('project_name', None)
                '''organization id is compulsory for sending project invitation'''
                if not project_name and not 'organization' in request.data:
                    return Response(data={'message': 'Params project_name and organization are required!'}, status=status.HTTP_400_BAD_REQUEST)
                organization = request.data.get('organization')
                organization_instance = Organization.active.get(id=organization)
                if Project.active.filter(Q(name=project_name[0]) & Q(organization=organization_instance)).exists():
                    return Response(data={'message': 'A project with the same name is already registered in your organization!'}, status=status.HTTP_400_BAD_REQUEST)
                project_instance = Project.active.create(name=project_name[0], organization=organization_instance)
                request.data['project'] = project_instance.id
                # '''checking if group exists already'''
                # if Group.objects.filter(name='Project Manager').exists():
                #     request.data['group'] = Group.objects.get(name='Project Manager').id
                # else:
                #     '''creating new group object'''
                #     group_instance = Group.objects.create(name='Project Manager')
                #     request.data['group'] = group_instance.id
                request.data['group'] = int(env('PROJECT_MANAGER'))       
            '''create multiple or single preliminary user instances'''
            created_object_list = []
            for email in email_list:
                request.data['email'] = email
                request.data['email_verification_token'] = uuid.uuid4()
                serializer = PreliminaryUserSerializer(data=request.data)
                if serializer.is_valid():
                    created_object = serializer.save()
                    created_object_list.append(created_object)
                    '''email invitation'''
                    data = {
                    'paragraph_1': f'You have been invited as {created_object.group} in USAFIRI mapping platform. Please click on the link to verfiy and continue further steps: {verify_url}{created_object.email_verification_token}',
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
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
            return Response(data={'message': 'Email Invitation Successful!'}, status=status.HTTP_200_OK)
        except Exception as e:
            if organization_name:
                organization_instance.delete()
            if project_name:
                project_instance.delete()
            group_instance.delete()
            for obj in created_object_list:
                obj.delete()
            errors.append({'details': str(e)})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'Message': 'Dataset not created', 'Error': errors})

'''email verification, create user role for already registered users and send details of the preliminary user object in resposne'''
class PreliminaryUserVerificationAPIView(APIView):
    '''http://localhost:8000/api/users/preliminary_user_verify?token=cd72216e-a08d-456f-a72c-8f91ca9ca61c'''
    permission_classes = [AllowAny]
    def get(self, request, *args, **kwargs):
        try:
            token = request.query_params.get('token', None)
            if not token:
                return Response(data={'message': 'Query Params token is required!'}, status=status.HTTP_400_BAD_REQUEST)
            if not PreliminaryUser.objects.filter(email_verification_token=token).exists():
                return Response(data={'message': 'PreliminaryUser matching queryset does not exists!'}, status=status.HTTP_400_BAD_REQUEST)
            preliminary_user_instance = PreliminaryUser.objects.get(email_verification_token=token)
            serializer = PreliminaryUserSerializer(preliminary_user_instance)
            data_dict = dict(serializer.data)
            '''checking whether the user is already registered'''
            if User.active.filter(email=preliminary_user_instance.email).exists():
                data_dict['user'] = User.active.get(email=preliminary_user_instance.email).id
                data_dict['user_created'] = True 
                '''creating new user role for already registered user'''
                user_role_serializer = UserRoleSerializer(data=data_dict)
                if user_role_serializer.is_valid():
                    user_role_serializer.save()
                    '''delete PreliminaryUserInstance once the job is done'''
                    preliminary_user_instance.delete()
                    return Response(data={'message': 'Successully created new user role.', 'data': data_dict}, status=status.HTTP_200_OK)
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
    queryset = User.active.all()
    serializer_class = UserSerializer
    http_method_names = ['get', 'post', 'patch']

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
            verify_url = settings.URL + '/api/users/user_verify/?token='     
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                created_object = serializer.save()
                email = serializer.validated_data.get('email')
                '''Activating account of users from email invitaion'''
                if PreliminaryUser.objects.filter(email=email).exists():
                    preliminary_user_instance = PreliminaryUser.objects.get(email=email)
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
                request.data['user'] = created_object.id
                user_role_serializer = UserRoleSerializer(data=request.data)
                if user_role_serializer.is_valid():
                    user_role_obj = user_role_serializer.save()
                else:
                    for er in user_role_serializer._errors:
                        errors.append({"errorName": er, "details": serializer._errors[er][0]})
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
                if email_verified == True:
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