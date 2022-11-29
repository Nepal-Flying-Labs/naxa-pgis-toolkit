import json
import operator
import os
import shutil
import tempfile
import zipfile
from functools import reduce

import environ
import fiona
import geopandas as gpd
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.views.generic import DetailView, ListView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken

from pgis_toolkit.maps.models import Theme
from pgis_toolkit.projects.api.serializers import *
from pgis_toolkit.projects.models import (
    Country,
    DefaultTheme,
    Document,
    Image,
    LayerTemplate,
    LayerTemplateAttribute,
    Organization,
    OrganizationCategory,
    Project,
    ProjectLocationFeatureCollection,
    RequestDemo,
    State,
)
from pgis_toolkit.projects.permissions import (
    DocumentDownloadPermission,
    DocumentPermission,
    OrganizationCategoryPermission,
    OrganizationPermission,
    ProjectPermission,
)
from pgis_toolkit.projects.utils.get_project_queryset import get_project_queryset
from pgis_toolkit.projects.utils.handleProjectLocation import (
    handleProjectGeoJSON,
    handleProjectShapeFile,
)
from pgis_toolkit.users.models import UserRole
from pgis_toolkit.utils.pagination import CustomPageNumberPagination
from pgis_toolkit.utils.vectortile import BaseVectorTileView, ProjectLocationMVTView

env = environ.Env()
User = get_user_model()
class OrganizationCategoryViewset(viewsets.ModelViewSet):
    queryset = OrganizationCategory.active.all()
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [OrganizationCategoryPermission]
    default_serializer_class = OrganizationCategorySerializer
    serializer_classes = {
        'list': OrganizationCategoryListSerializer,
        'retrieve': OrganizationCategorySerializer
    }
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class OrganizationViewset(viewsets.ModelViewSet):
    '''create is handeled in PreliminaryUserAPIView inside users app'''
    queryset = Organization.active.all()
    http_method_names = ['get', 'patch']
    default_serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, OrganizationPermission]
    serializer_classes = {
        'list': OrganizationListSerializer,
        'retrieve': OrganizationRetrieveSerializer,
    }
    pagination_class = CustomPageNumberPagination
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def list(self, request, *args, **kwargs):
        try:
            paginator = CustomPageNumberPagination()
            if request.user.is_superuser:
                queryset = self.queryset
            elif UserRole.active.filter(Q(user__id=request.user.id) & Q(active=True)).exists():
                userrole_qs = UserRole.active.filter(Q(user__id=request.user.id) & Q(active=True))
                queryset = self.queryset
                user_role_list = userrole_qs.values_list('group__id', flat=True)
                '''filter organization list according to the role of the user.'''
                if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in user_role_list:
                    '''web app administrator can view all organization'''
                    queryset = queryset
                else:
                    '''other user can view only the organizations they are involved in'''
                    user_org_list = userrole_qs.values_list('organization__id', flat=True)
                    queryset = queryset.filter(id__in=user_org_list)
            else:
                return Response(data={'message': 'No any user role of the requesting user found!'}, status=status.HTTP_400_BAD_REQUEST)
            search_key = request.query_params.get('search', None)
            order_by = request.query_params.get('ordering', None)
            queryset = queryset.filter(name__icontains=search_key) if search_key and search_key != "" else queryset
            if order_by and order_by != "":
                if order_by == 'projects':
                    queryset = queryset.annotate(count=Count('ProjectOrganization')).order_by('count')
                elif order_by == '-projects':
                    queryset = queryset.annotate(count=Count('ProjectOrganization')).order_by('-count')
                else:
                    queryset = queryset.order_by(order_by)
            else:
                queryset = queryset
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = self.get_serializer(paginated_queryset, many=True, context={})
            return paginator.get_paginated_response(data=serializer.data)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data=str(e))

'''delets a project object'''
def delete_project(project_id):
    Project.active.filter(id=project_id).delete()

# '''create theme objects from default theme objects for each new project object created'''
# def create_theme(project_id):
#     project = Project.active.get(id=project_id)
#     default_themes = DefaultTheme.objects.all()
#     for theme in default_themes:
#         Theme.objects.create(project=project, name=theme.name, order=theme.order)

class ProjectViewset(viewsets.ModelViewSet):
    '''create is handeled in PreliminaryUserAPIView inside users app'''
    queryset = Project.active.all()
    http_method_names = ['get', 'patch']
    permission_classes = [IsAuthenticated,ProjectPermission]
    default_serializer_class = ProjectSerializer
    serializer_classes = {
        'list': ProjectListSerializer,
        'retrieve': ProjectSerializer
    }
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    # def create(self, request, *args, **kwargs):
    #     errors = []
    #     try:
    #         request.data._mutable = True
    #         request_dict = request.data
    #         request_keys = request_dict.keys()
    #         '''retrieveing country'''
    #         country = request_dict['country']
    #         request_dict.pop('country')
    #         '''retrieving state'''
    #         state = request_dict['state']
    #         request_dict.pop('state')

    #         serializer = ProjectSerializer(data=request_dict)
    #         if serializer.is_valid():
    #             created_object = serializer.save()
    #             ''''handle country and state'''
    #             created_object.country.set(json.loads(country))
    #             created_object.state.set(json.loads(state))
    #             created_object.save()
    #             '''check location file'''
    #             file_input = False
    #             if 'location_type' in request_keys and request_dict['location_type'] == 'File Upload':
    #                 file_input = True
    #                 file_type_list = ['Shapefile', 'GeoJSON']
    #                 if 'file' not in request_keys or request_dict['file'] == "" or 'file_type' not in request_keys or request_dict['file_type'] not in file_type_list:
    #                     return Response(data={'message': 'No file input or file_type!'}, status=status.HTTP_400_BAD_REQUEST)

    #             '''Location file as Shapfile'''
    #             if file_input == True:
    #                 file_type = request_dict['file_type']
    #                 file = str(request_dict['file'])
    #                 split_tup = os.path.splitext(file)
    #                 file_extension = split_tup[1]
    #                 if file_type == "Shapefile":
    #                     if file_extension == ".zip":
    #                         response = handleProjectShapeFile(
    #                             created_object.id)
    #                         if response == "successful":
    #                             # create_theme(created_object.id)
    #                             return Response({'message': response, 'data': serializer.data}, status=status.HTTP_201_CREATED)
    #                         else:
    #                             delete_project(created_object.id)
    #                             return Response({'message': response}, status=status.HTTP_400_BAD_REQUEST)
    #                     else:
    #                         delete_project(created_object.id)
    #                         return Response({'message': "Please provide commpressed .zip file"},
    #                                         status=status.HTTP_400_BAD_REQUEST)

    #                     '''Location file as GeoJSON'''
    #                 elif file_type == "GeoJSON":
    #                     if file_extension == ".geojson":
    #                         response = handleProjectGeoJSON(created_object.id)
    #                         if response == "successful":
    #                             # create_theme(created_object.id)
    #                             return Response({'message': response, 'data': serializer.data}, status=status.HTTP_201_CREATED)
    #                         else:
    #                             delete_project(created_object.id)
    #                             return Response({'message': response}, status=status.HTTP_400_BAD_REQUEST)
    #                     else:
    #                         delete_project(created_object.id)
    #                         return Response({'message': "Please provide valid .geojson file"},
    #                                         status=status.HTTP_400_BAD_REQUEST)
    #                 else:
    #                     return Response({'message': "Invalid file type"}, status=status.HTTP_400_BAD_REQUEST)

    #             else:
    #                 '''Location as wkt from Custom Draw on map'''
    #                 if 'location_wkt' not in request_keys or request_dict['location_wkt'] == "":
    #                     delete_project(created_object.id)
    #                     return Response(data={'message': 'No wkt of project location'}, status=status.HTTP_400_BAD_REQUEST)

    #                 wkt_list = json.loads(request.data['location_wkt'])
    #                 for geom in wkt_list:
    #                     ProjectLocationFeatureCollection.objects.create(project=created_object,
    #                                                                     geometry=GEOSGeometry(geom))
    #                 # create_theme(created_object.id)
    #                 return Response(status=200, data={'Message': 'Object Successfully Created', 'data': serializer.data,
    #                                                     'object_id': created_object.id})
    #         else:
    #             for er in serializer._errors:
    #                 errors.append(
    #                     {'errorName': er, 'details': serializer._errors[er]})
    #             return Response(status=status.HTTP_400_BAD_REQUEST,
    #                             data={'message': 'Error Occured', 'error': errors})

    #     except Exception as error:
    #         return Response({"message": str(error)}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        try:
            project = Project.active.get(pk=pk)
            request.data._mutable = True
            request_dict = request.data
            request_keys = request_dict.keys()
            country = None
            state = None
            '''retrieveing country'''
            if 'country' in request_keys:
                country = request_dict['country']
                request_dict.pop('country')
            '''retrieving state'''
            if 'state' in request_keys:
                state = request_dict['state']
                request_dict.pop('state')
            serializer = ProjectSerializer(
                project, data=request_dict, partial=True)
            if serializer.is_valid():
                created_object = serializer.save()
                ''''handle country and state'''
                if country != None:
                    created_object.country.set(json.loads(country))
                if state != None:
                    created_object.state.set(json.loads(state))
                created_object.save()
                project_id = project.id

                '''check location file'''
                file_input = False
                if 'location_type' in request_keys and request_dict['location_type'] == 'File Upload':
                    file_input = True
                    file_type_list = ['Shapefile', 'GeoJSON']
                    if 'file' not in request_keys or request_dict['file'] == "" or 'file_type' not in request_keys or request_dict['file_type'] not in file_type_list:
                        return Response(data={'message': 'No file input or file_type!'}, status=status.HTTP_400_BAD_REQUEST)
                    file_type = request_dict['file_type']
                    file = str(request_dict["file"])
                    split_tup = os.path.splitext(file)
                    file_extension = split_tup[1]

                '''Location file as Shapfile'''
                if file_input == True:
                    if file_type == "Shapefile":
                        if file_extension == ".zip":
                            ProjectLocationFeatureCollection.active.filter(project=project_id).update(
                                is_deleted=True)  # Archive existing features
                            response = handleProjectShapeFile(project_id)
                            if response == "successful":
                                '''change project status to ongoing'''
                                project.status='ongoing'
                                project.save()
                                return Response({'message': response, 'data': serializer.data}, status=status.HTTP_201_CREATED)
                            else:
                                return Response({'message': response}, status=status.HTTP_400_BAD_REQUEST)
                        else:
                            return Response({'message': "Please provide commpressed .zip file"},
                                            status=status.HTTP_400_BAD_REQUEST)

                        '''Location file as Shapfile'''
                    elif file_type == "GeoJSON":
                        if file_extension == ".geojson":
                            ProjectLocationFeatureCollection.active.filter(project=project_id).update(
                                is_deleted=True)  # Archive existing features
                            response = handleProjectGeoJSON(project_id)
                            if response == "successful":
                                '''change project status to ongoing'''
                                project.status='ongoing'
                                project.save()
                                return Response({'message': response, 'data': serializer.data}, status=status.HTTP_201_CREATED)
                            else:
                                return Response({'message': response}, status=status.HTTP_400_BAD_REQUEST)
                        else:
                            return Response({'message': "Please provide valid .geojson file"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({'message': "Invalid file type"}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    '''Location as wkt from Custom Draw on map'''
                    if 'location_wkt' in request_keys:
                        ProjectLocationFeatureCollection.active.filter(project=project_id).update(
                            is_deleted=True)  # Archive existing features
                        project.file.delete(save=True)
                        wkt_name = request_dict['location_wkt']
                        wkt_list = json.loads(request_dict['location_wkt'])
                        merged_geom = GEOSGeometry(wkt_list[0])
                        for wkt in wkt_list:
                            geom = GEOSGeometry(wkt)
                            ProjectLocationFeatureCollection.active.create(project=project,
                                                                            geometry=geom)
                            merged_geom = merged_geom.union(geom)
                        project.bbox = merged_geom.extent
                        '''change project status to ongoing'''
                        project.status='ongoing'
                        project.save()
                serializer = ProjectSerializer(
                    project, context={'request': request})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_403_FORBIDDEN)
        except Exception as error:
            return Response({"Error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

    def list(self, request, *args, **kwargs):
        '''http://localhost:8000/api/projects/project/?organization=1&state=&country=&polygon_wkt=POLYGON ((84 26, 86 26, 86 30, 84 30, 84 26))&search=ggg'''
        try:
            paginator = CustomPageNumberPagination()
            organization_id = request.query_params.get('organization', None)
            # queryset = self.queryset

            # '''filter by organization id'''
            # if organization_id and organization_id != "":
            #     if not Organization.active.filter(id=organization_id).exists():
            #         return Response(data={'message': 'Invalid organization id!'}, status=status.HTTP_400_BAD_REQUEST)
            #     queryset = queryset.select_related("organization").filter(organization__id=organization_id)
            # if request.user.is_superuser:
            #     queryset = queryset
            # elif UserRole.active.filter(Q(user__id=request.user.id) & Q(active=True)).exists():
            #     userrole_qs = UserRole.active.filter(Q(user__id=request.user.id) & Q(active=True))
            #     user_role_list = userrole_qs.values_list('group__id', flat=True)
            #     if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in user_role_list:
            #         '''all projects visible if the user has web app administrator role'''
            #         queryset = queryset
            #     else:
            #         userrole_qs = userrole_qs.filter(organization__id=organization_id)
            #         '''now retrieve a list of group the user has been into inside the organization'''
            #         user_org_role_list = userrole_qs.values_list('group__id', flat=True)
            #         if int(env('ORGANIZATION_ADMIN')) in user_org_role_list:
            #             '''all projects visible if the user has organization admin role amongst his roles'''
            #             queryset = queryset
            #         else:
            #             '''for user other than organization admin and pgis web administrator, projects are restricted only to the ones they work for.'''
            #             user_org_proj_list = userrole_qs.values_list('project__id', flat=True)
            #             queryset = queryset.filter(id__in=user_org_proj_list)
            # else:
            #     return Response(data={'message': 'No any user role of the requesting user found!'}, status=status.HTTP_400_BAD_REQUEST)
            # state = request.query_params.get('state', None)
            # country = request.query_params.get('country', None)
            # '''filter by state'''
            # if state and state != "":
            #     queryset = queryset.filter(state__id=state)
            #     '''filter by country or polygon wkt'''
            # elif country and country != "":
            #     queryset = queryset.filter(country__id=country)
            #     '''filter by polygon wkt'''
            # elif polygon_wkt and polygon_wkt != "":
            #     polygon = GEOSGeometry(polygon_wkt)
            #     organization_project_list = queryset.values_list('id', flat=True)
            #     project_location_qs = ProjectLocationFeatureCollection.active.select_related("project").filter(project__id__in=organization_project_list).values('id', 'project', 'geometry')
            #     project_ids = []
            #     for qs in project_location_qs:
            #         if qs['geometry'].within(polygon):
            #             project_ids.append(qs['project'])
            #     queryset = queryset.filter(id__in=project_ids)
            # '''search by a key'''
            # search_key = request.query_params.get('search', None)
            # if search_key and search_key != "":
            #     search_fields = ['name', 'state__name', 'country__name']
            #     filter_kwargs = {}
            #     for field in search_fields:
            #         filter_kwargs[field+'__icontains'] = search_key
            #     list_of_Q = [Q(**{key: val})
            #                     for key, val in filter_kwargs.items()]
            #     queryset = queryset.filter(
            #         reduce(operator.or_, list_of_Q)) if search_fields else queryset
            queryset = get_project_queryset(request, request.user)
            if not isinstance(queryset, QuerySet):
                if isinstance(queryset, HttpResponse):
                    return Response(queryset.content, status=queryset.status_code)
                else:
                    return Response(data=queryset, status=status.HTTP_400_BAD_REQUEST)
            '''filter by polygon_wkt'''
            polygon_wkt = request.query_params.get('polygon_wkt', None)
            if polygon_wkt and polygon_wkt != "":
                polygon = GEOSGeometry(polygon_wkt)
                organization_project_list = queryset.values_list('id', flat=True)
                project_location_qs = ProjectLocationFeatureCollection.active.select_related("project").filter(project__id__in=organization_project_list).values('id', 'project', 'geometry')
                project_ids = []
                for qs in project_location_qs:
                    if qs['geometry'].within(polygon):
                        project_ids.append(qs['project'])
                queryset = queryset.filter(id__in=project_ids)
            '''paginate queryset'''
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = self.get_serializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(data=serializer.data)
        except Exception as error:
            return Response({"Error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

'''Retrieve bbox and project name in Map page'''
@api_view(['GET'])
def get_project_detail(request, *args, **kwargs):
    project = request.query_params.get('project', None)
    if project:
        if Project.active.filter(id=project).exists():
            project_instance = Project.active.get(id=project)
            data = {'id': project, 'name': project_instance.name, 'bbox': project_instance.bbox}
            return Response(status=status.HTTP_200_OK, data={'message': 'success', 'data': data})
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': "Project Matching queryset not found!"})
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': "params project is missing"})


class DefaultThemeViewset(viewsets.ModelViewSet):
    queryset = Organization.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = OrganizationSerializer
    serializer_classes = {
        'list': DefaultThemeListSerializer,
        'retrieve': DefaultThemeSerializer
    }
    pagination_class = CustomPageNumberPagination
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class LayerTemplateViewset(viewsets.ModelViewSet):
    queryset = LayerTemplate.objects.all()
    http_method_names = ['get','post','patch']
    default_serializer_class = LayerTemplateSerializer
    serializer_classes={
        'list':LayerTemplateListSerializer,
        'retrieve':LayerTemplateSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class LayerTemplateAttributeViewset(viewsets.ModelViewSet):
    queryset = LayerTemplateAttribute.objects.all()
    http_method_names = ['get','post','patch','delete']
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('layer_template', )
    default_serializer_class = LayerTemplateAttributeSerializer
    serializer_classes={
        'list':LayerTemplateAttributeListSerializer,
        # 'retrieve':LayerTemplateAttributeSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

#function to clear files in a specific directory
def clear_dir(dir):
    for files in os.listdir(dir):
        path = os.path.join(dir, files)
        try:
            shutil.rmtree(path)
        except OSError:
            os.remove(path)


@api_view(['GET'])
@permission_classes([AllowAny])
def layer_template_download(request):
    #creating directory to save shapefile
    dir=settings.MEDIA_ROOT + '/template_download/shapefiles/'
    os.makedirs(dir, exist_ok=True)
    try:
        layer_template_id=request.query_params.get('layer_template_id',None)
        if not layer_template_id:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': "params layer_template_id is missing"})
        layer_template_instance=LayerTemplate.objects.get(id=layer_template_id)
        attributes=LayerTemplateAttribute.objects.filter(layer_template=layer_template_instance.id)
        properties={}
        for attribute in attributes:
            if attribute.data_type=="str":
                properties[attribute.name]='str'
            elif attribute.data_type=="int":
                properties[attribute.name]=f'int:{attribute.length}'
            elif attribute.data_type=="float":
                properties[attribute.name]=f'float:{attribute.length}.{attribute.precision}'
            elif attribute.data_type=="date":
                properties[attribute.name]='date'
        schema={
            'geometry':layer_template_instance.geometry_type,
            'properties':properties
        }
        shapefile_path = settings.MEDIA_ROOT + \
                            f'/template_download/shapefiles/{layer_template_instance.name}.shp'
        shapefile = fiona.open(shapefile_path, mode='w', driver='ESRI Shapefile',
          schema = schema, crs = "EPSG:4326")
        shapefile.close()

        # create a ZipFile
        zipfile_path = settings.MEDIA_ROOT + \
            f'/template_download/shapefiles/{layer_template_instance.name}'
        files = settings.MEDIA_ROOT + '/template_download/shapefiles'
        shutil.make_archive(zipfile_path, 'zip', files)

        # defining zip file path
        file_url = settings.MEDIA_ROOT + \
            f'/template_download/shapefiles/{layer_template_instance.name}.zip'

        # downloading zip file
        zip_file = open(file_url, 'rb')
        response = HttpResponse(
            zip_file, content_type='application/force-download')
        response[
            'Content-Disposition'] = 'attachment; filename="%s"' % f'{layer_template_instance.name}.zip'
        clear_dir(dir) #clearing directory
        return response
    except Exception as e:
        clear_dir(dir) #clearing directory
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': str(e)})

class LayerTemplateUploadAPIView(APIView):
    def post(self, request, format=None):
        errors=[]
        try:
            #creating directory to save uploaded file
            FILE_UPLOAD_DIR = settings.MEDIA_ROOT + '/template_upload/shapefiles/'
            os.makedirs(FILE_UPLOAD_DIR, exist_ok=True)

            if not 'file' in request.FILES and request.FILES.get('file') == "":
                return Response("error: file is missing", status=status.HTTP_400_BAD_REQUEST)

            file = request.data["file"]
            split_tup = os.path.splitext(str(file))
            file_name=split_tup[0]
            file_extension = split_tup[1]
            if not file_extension == ".zip":
                return Response("error: only .zip file is valid", status=status.HTTP_400_BAD_REQUEST)

            #saving uploded file in directory
            fd, zip_file_path = tempfile.mkstemp(prefix=file_name, dir=FILE_UPLOAD_DIR)
            with open(zip_file_path, 'wb') as dest:
                shutil.copyfileobj(file, dest)

            #unzipping uploaded zip file
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(FILE_UPLOAD_DIR)

            #finding file with .shp extension
            files=os.listdir(FILE_UPLOAD_DIR)
            shp_file_name=None
            for file_name in files:
                file_extension=os.path.splitext(str(file_name))[1]
                if file_extension==".shp":
                    shp_file_name=file_name
            if not shp_file_name:
                clear_dir(FILE_UPLOAD_DIR)
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': "File with extension .shp not found"})

            #reading shapefile
            c = fiona.open(FILE_UPLOAD_DIR+shp_file_name)
            schema=c.schema

            #creating layer template instance
            geometry=schema['geometry']
            request.data['geometry_type']=geometry
            serializer=LayerTemplateSerializer(data=request.data)
            if serializer.is_valid():
                template_instance=serializer.save()
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                    clear_dir(FILE_UPLOAD_DIR)
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': errors})

            #reading fields properites and saving it into the LayerTemplateAttribute table
            for data in schema['properties']:
                properties={'name':str(data)}
                data_type=schema['properties'][data].split(':')[0]
                properties['data_type']=data_type
                if data_type=='str' or data_type=='int':
                    properties['length']=schema['properties'][data].split(':')[1]
                elif data_type=="float":
                    properties['length']=schema['properties'][data].split(':')[1].split('.')[0]
                    properties['precision']=schema['properties'][data].split(':')[1].split('.')[1]
                properties['layer_template']=template_instance.id
                attribute_serializer=LayerTemplateAttributeSerializer(data=properties)
                if attribute_serializer.is_valid():
                    attribute_serializer.save()
                else:
                    for er in attribute_serializer._errors:
                        errors.append(
                            {'errorName': er, 'details': attribute_serializer._errors[er][0]})
                    template_instance.delete()
                    clear_dir(FILE_UPLOAD_DIR)
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': errors})
            clear_dir(FILE_UPLOAD_DIR)
            return Response(status=200, data={'message': "Data successfully uploaded"})
        except Exception as e:
            clear_dir(FILE_UPLOAD_DIR) #clearing directory
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': str(e)})


'''VextorTile Generation for ProjectLocationFeatureCollection'''

class ProjectLocationVectorTileQuerySet(ProjectLocationMVTView, DetailView):
    # "http://localhost:8000/api/projects/project_location_vectortile/{z}/{x}/{y}/?organization=1&state=&country=&polygon_wkt=POLYGON ((84 26, 86 26, 86 30, 84 30, 84 26))"
    vector_tile_layer_name = None
    vector_tile_fields = ('pk', 'project', 'attributes')

    def get(self, request, *args, **kwargs):
        '''Authentication'''
        # user_id = request.user.id
        auth = request.headers['Authorization']
        token = auth.split()[1]
        try:
            '''if JWT authentication'''
            user_id = AccessToken(token)['user_id']
        except:
            '''if token authentication'''
            auth_token = Token.objects.get(key=token)
            user_id = auth_token.user_id
        if User.active.filter(id=user_id).exists():
            user = User.active.get(id=user_id)
        else:
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
        if not request.GET.keys():
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        request_keys = request.GET.keys()
        '''filter by organization'''
        if 'project' not in request_keys or request.GET['project'] == "":
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        project = request.GET['project']
        ############################################################
        # if not request.GET.keys():
        #     return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        # request_keys = request.GET.keys()
        # '''filter by organization'''
        # if 'organization' not in request_keys or request.GET['organization'] == "":
        #     return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        # organization_id = request.GET['organization']
        # if not Organization.active.filter(id=organization_id).exists():
        #     return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        # organization_project_qs = Project.active.select_related("organization").filter(organization__id=organization_id)
        # '''superuser gets to see all project sites'''
        # if user.is_superuser == True:
        #     print('reached here!')
        #     organization_project_qs = organization_project_qs
        #     print(organization_project_qs, "is organization_project_qs")
        # elif UserRole.active.filter(Q(user=user_id) & Q(active=True)).exists():
        #     userrole_qs = UserRole.active.filter(Q(user=user_id) & Q(active=True))
        #     user_role_list = userrole_qs.values_list('group__id', flat=True)
        #     if int(env('PGIS_WEB_APP_ADMINISTRATOR')) in user_role_list:
        #         '''all projects visible if the user has web app administrator role'''
        #         organization_project_qs = organization_project_qs
        #     else:
        #         userrole_qs = userrole_qs.filter(organization__id=organization_id)
        #         '''now retrieve a list of group the user has been into inside the organization'''
        #         user_org_role_list = userrole_qs.values_list('group__id', flat=True)
        #         if int(env('ORGANIZATION_ADMIN')) in user_org_role_list:
        #             '''all projects visible if the user has organization admin role amongst his roles'''
        #             organization_project_qs = organization_project_qs
        #         else:
        #             '''for user other than organization admin and pgis web administrator, projects are restricted only to the ones they work for.'''
        #             user_org_proj_list = userrole_qs.values_list('project__id', flat=True)
        #             organization_project_qs = organization_project_qs.filter(id__in=user_org_proj_list)
        # else:
        #     return Response(data={'message': 'No any user role of the requesting user found!'}, status=status.HTTP_400_BAD_REQUEST)
        # '''search_key'''
        # if 'search' in request_keys and request.GET['search'] != "":
        #     search_key = request.GET['search']
        #     search_fields = ['name', 'state__name', 'country__name']
        #     filter_kwargs = {}
        #     for field in search_fields:
        #         filter_kwargs[field+'__icontains'] = search_key
        #     list_of_Q = [Q(**{key: val})
        #                     for key, val in filter_kwargs.items()]
        #     organization_project_qs = organization_project_qs.filter(
        #         reduce(operator.or_, list_of_Q)) if search_fields else organization_project_qs
        # '''filter by state'''
        # if 'state' in request_keys and request.GET['state'] != "":
        #     state = request.GET['state']
        #     organization_project_qs = organization_project_qs.filter(state__id=state)
        #     '''filter by state'''
        # elif 'country' in request_keys and request.GET['country'] != "":
        #     country = request.GET['country']
        #     organization_project_qs = organization_project_qs.filter(country__id=country)
        # organization_project_list = organization_project_qs.values_list('id', flat=True)
        #################################################################################

        # organization_project_qs = get_project_queryset(request, user)
        # if not isinstance(organization_project_qs, QuerySet):
        #     print(organization_project_qs, type(organization_project_qs), "is response")
        #     if isinstance(organization_project_qs, HttpResponse):
        #         return organization_project_qs
        #     else:
        #         return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        # organization_project_list = organization_project_qs.values_list('id', flat=True)

        queryset = ProjectLocationFeatureCollection.active.select_related("project").filter(project=project)
        self.vector_tile_queryset = queryset.distinct()
        return BaseVectorTileView.get(self, request=request, z=kwargs.get('z'), x=kwargs.get('x'), y=kwargs.get('y'))

class ImageViewset(viewsets.ModelViewSet):
    queryset=Image.objects.all()
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsAuthenticated]
    serializer_class = ImageSerializer


class DocumentViewset(viewsets.ModelViewSet):
    queryset=Document.objects.all()
    http_method_names=['get', 'post', 'patch']
    permission_classes = [IsAuthenticated, DocumentPermission]
    default_serializer_class = DocumentSerializer
    serializer_classes = {
        'list': DocumentListSerializer,
        'retrieve': DocumentSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def create(self, request, *args, **kwargs):
        '''http://localhost:8000/api/projects/document/'''
        try:
            project = request.data.get('project', None)
            name = request.data.get('name', None)
            project = request.data.get('project', None)
            if not project or not Project.active.filter(id=project).exists():
                return Response(data={'message': 'Invalid project params!'}, status=status.HTTP_400_BAD_REQUEST)
            if name and Document.objects.filter(Q(project__id=project) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate document name for the same project!'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                created_object = serializer.save()
            return Response(data={'data': serializer.data}, status=status.HTTP_201_CREATED)
        except Exception as e:
            Document.objects.get(id=created_object.id).delete()
            return Response(data='Error: '+str(e))

    def partial_update(self, request, pk=None, *args, **kwargs):
        '''http://localhost:8000/api/projects/document/2/'''
        try:
            document_instance = Document.objects.get(pk=pk)
            request.data._mutable = True
            request_dict = request.data
            request_keys = request_dict.keys()
            project = None
            name = None
            if 'project' in request_keys and request_dict['project'] != "" and 'name' in request_keys and request_dict['name'] != "":
                project = request_dict['project']
                name = request_dict['name']
            elif 'project' in request_keys and request_dict['project'] != "":
                project = request_dict['project']
                name = document_instance.name
            elif 'name' in request_keys and request_dict['name'] != "":
                name = request_dict['name']
                project = document_instance.project.id
            if (name or project) and (Document.objects.exclude(pk=pk).filter(Q(project__id=project) & Q(name=name)).exists()):
                return Response(data={'messgae': 'Cannot create duplicate document name for the same project!'})
            if 'cover_image' in request_keys and isinstance(request_dict['cover_image'], str):
                request_dict.pop('cover_image', None)
                document_instance.cover_image = None
                document_instance.cover_image_thumbnail = None
            if 'file' in request_keys and isinstance(request_dict['file'], str):
                request_dict.pop('file', None)
                document_instance.file = None
            serializer = self.get_serializer(document_instance, data=request_dict, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data='Error: '+str(e))

    def list(self, request, *args, **kwargs):
        '''http://localhost:8000/api/maps/document/?project=2'''
        '''search is implemented from name field only.'''
        project = request.query_params.get('project', None)
        if not project:
            return Response(data={'message': 'params project is missing'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.queryset.filter(project__id=project)
        search_key = request.query_params.get('search_key', None)
        if search_key:
            queryset = queryset.filter(name__icontains=search_key)
        serializer = self.get_serializer(queryset, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

'''download document of a project'''
@api_view(['GET'])
@permission_classes([IsAuthenticated, DocumentDownloadPermission])
def document_download(request):
    '''http://localhost:8000/api/projects/document_download/?document=1'''
    try:
        document = request.query_params.get('document', None)
        if not document:
            return Response(data={'message': 'params document is missing'}, status=status.HTTP_400_BAD_REQUEST)
        if not Document.objects.filter(id=document).exists():
            return Response(data={'message': 'No document matching queryset found!'}, status=status.HTTP_400_BAD_REQUEST)
        document_instance = Document.objects.get(id=document)
        if not document_instance.file:
            return Response(data={'message': 'The document you are trying to download has no file.'}, status=status.HTTP_404_NOT_FOUND)
        document_extension = str(document_instance.file).split('.')[1]
        document_url = settings.MEDIA_ROOT + f"/{document_instance.file}"
        document_file = open(document_url, 'rb')
        response = HttpResponse(
            document_file, content_type='application/force-download')
        response[
            'Content-Disposition'] = 'attachment; filename="%s"' % f'{document_instance.name}.{document_extension}'
        return response
    except Exception as e:
        return Response(data='Error: '+str(e))

class RequestDemoViewset(viewsets.ModelViewSet):
    queryset = RequestDemo.objects.all()
    serializer_class = RequestDemoSerializer
    http_method_names = ['get', 'post']

    def get_permissions(self):
        if self.action == 'list' or self.action == 'retrieve':
            permission_classes = [IsAuthenticated]
        elif self.action == 'create':
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

@api_view(['GET'])
@permission_classes([AllowAny])
def get_country_choices(request, *args, **kwargs):
    data = Country.objects.all().values('id', 'name')
    return Response(data=data, status=200)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_state_choices(request, *args, **kwargs):
    country = request.query_params.get('country', None)
    if country:
        country_list = json.loads(country)
        data = State.objects.filter(country__id__in=country_list).values('id', 'name')
    else:
        data = State.objects.all().values('id', 'name')
    return Response(data=data, status=200)

class ContactPersonViewset(viewsets.ModelViewSet):
    queryset = ContactPerson.active.all()
    permission_classes = [IsAuthenticated]
    http_method_names = ['post', 'patch']
    serializer_class = ContactPersonSerializer
