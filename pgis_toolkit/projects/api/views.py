import json
import os
import shutil
import tempfile
import zipfile

import fiona
import geopandas as gpd
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.http import HttpResponse
from django.views.generic import DetailView, ListView
from django_filters.rest_framework import DjangoFilterBackend
from maps.models import Theme
from projects.api.serializers import *
from projects.models import (
    DefaultTheme,
    LayerTemplate,
    LayerTemplateAttribute,
    Organization,
    OrganizationCategory,
    Project,
    ProjectLocationFeatureCollection,
)
from projects.utils.handleProjectLocation import (
    handleProjectGeoJSON,
    handleProjectShapeFile)
from projects.utils.pagination import CustomPageNumberPagination
from projects.utils.vectortile import *
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView


class OrganizationCategoryViewset(viewsets.ModelViewSet):
    queryset = OrganizationCategory.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = OrganizationCategorySerializer
    serializer_classes = {
        'list': OrganizationCategoryListSerializer,
        'retrieve': OrganizationCategorySerializer
    }
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class OrganizationViewset(viewsets.ModelViewSet):
    queryset = Organization.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = OrganizationSerializer
    serializer_classes = {
        'list': OrganizationListSerializer,
        'retrieve': OrganizationSerializer
    }
    pagination_class = CustomPageNumberPagination
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def list(self, request, *args, **kwargs):
        paginator = CustomPageNumberPagination()
        search_key = request.query_params.get('search_key', None)
        order_by = request.query_params.get('order_by', None)
        queryset = self.queryset.filter(name__icontains=search_key) if search_key and search_key != "" else self.queryset
        queryset = queryset.order_by(order_by) if order_by and order_by != "" else queryset
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(paginated_queryset, many=True, context={})
        return paginator.get_paginated_response(data=serializer.data)

'''delets a project object'''
def delete_project(project_id):
    Project.active.filter(id=project_id).delete()

'''create theme objects from default theme objects for each new project object created'''
def create_theme(project_id):
    project = Project.active.get(id=project_id)
    default_themes = DefaultTheme.objects.all()
    for theme in default_themes:
        Theme.objects.create(project=project, name=theme.name, order=theme.order)

class ProjectViewset(viewsets.ModelViewSet):
    queryset = Project.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = ProjectSerializer
    serializer_classes = {
        'list': ProjectListSerializer,
        'retrieve': ProjectSerializer
    }
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def create(self, request, *args, **kwargs):
        errors = []
        try:
            request.data._mutable = True
            request_dict = request.data
            request_keys = request_dict.keys()
            '''retrieveing country'''
            country = request_dict['country']
            request_dict.pop('country')
            '''retrieving state'''
            state = request_dict['state']
            request_dict.pop('state')

            serializer = ProjectSerializer(data=request_dict)
            if serializer.is_valid():
                created_object = serializer.save()
                ''''handle country and state'''
                created_object.country.set(json.loads(country))
                created_object.state.set(json.loads(state))
                created_object.save()
                '''check location file'''
                file_input = False
                if 'location_type' in request_keys and request_dict['location_type'] == 'File Upload':
                    file_input = True
                    file_type_list = ['Shapefile', 'GeoJSON']
                    if 'file' not in request_keys or request_dict['file'] == "" or 'file_type' not in request_keys or request_dict['file_type'] not in file_type_list:
                        return Response(data={'message': 'No file input or file_type!'}, status=status.HTTP_400_BAD_REQUEST)

                '''Location file as Shapfile'''
                if file_input == True:
                    file_type = request_dict['file_type']
                    file = str(request_dict['file'])
                    split_tup = os.path.splitext(file)
                    file_extension = split_tup[1]
                    if file_type == "Shapefile":
                        if file_extension == ".zip":
                            response = handleProjectShapeFile(
                                created_object.id)
                            if response == "successful":
                                create_theme(created_object.id)
                                return Response({'message': response, 'data': serializer.data}, status=status.HTTP_201_CREATED)
                            else:
                                delete_project(created_object.id)
                                return Response({'message': response}, status=status.HTTP_400_BAD_REQUEST)
                        else:
                            delete_project(created_object.id)
                            return Response({'message': "Please provide commpressed .zip file"},
                                            status=status.HTTP_400_BAD_REQUEST)

                        '''Location file as GeoJSON'''
                    elif file_type == "GeoJSON":
                        if file_extension == ".geojson":
                            response = handleProjectGeoJSON(created_object.id)
                            if response == "successful":
                                create_theme(created_object.id)
                                return Response({'message': response, 'data': serializer.data}, status=status.HTTP_201_CREATED)
                            else:
                                delete_project(created_object.id)
                                return Response({'message': response}, status=status.HTTP_400_BAD_REQUEST)
                        else:
                            delete_project(created_object.id)
                            return Response({'message': "Please provide valid .geojson file"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({'message': "Invalid file type"}, status=status.HTTP_400_BAD_REQUEST)

                else:
                    '''Location as wkt from Custom Draw on map'''
                    if 'location_wkt' not in request_keys or request_dict['location_wkt'] == "":
                        delete_project(created_object.id)
                        return Response(data={'message': 'No wkt of project location'}, status=status.HTTP_400_BAD_REQUEST)

                    wkt_list = json.loads(request.data['location_wkt'])
                    for geom in wkt_list:
                        ProjectLocationFeatureCollection.objects.create(project=created_object,
                                                                        geometry=GEOSGeometry(geom))
                    create_theme(created_object.id)
                    return Response(status=200, data={'Message': 'Object Successfully Created', 'data': serializer.data,
                                                        'object_id': created_object.id})
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er]})
                return Response(status=status.HTTP_400_BAD_REQUEST,
                                data={'message': 'Error Occured', 'error': errors})

        except Exception as error:
            return Response({"message": str(error)}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
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
                    for geom in wkt_list:
                        ProjectLocationFeatureCollection.active.create(project=project,
                                                                        geometry=GEOSGeometry(geom))
            serializer = ProjectSerializer(
                project, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_403_FORBIDDEN)



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
    # 'http://localhost:8000/api/projects/project_location_vectortile/{z}/{x}/{y}/?organization_id=1'

    vector_tile_layer_name = None
    vector_tile_fields = ('pk', 'geometry', 'attributes')

    def get(self, request, *args, **kwargs):
        if not request.GET.keys():
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        request_keys = request.GET.keys()
        if 'organization_id' not in request_keys or request.GET['organization_id'] == "":
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        organization_id = request.GET['organization_id']
        if not Organization.active.filter(id=organization_id).exists():
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        if organization_id:
            organization_project_list = Project.active.select_related("organization").filter(organization__id=organization_id).values_list('id', flat=True)
            project_location_qs = ProjectLocationFeatureCollection.active.select_related("project").filter(project__id__in=organization_project_list)
        self.vector_tile_queryset = project_location_qs.distinct()
        return BaseVectorTileView.get(self, request=request, z=kwargs.get('z'), x=kwargs.get('x'), y=kwargs.get('y'))
