import os
import shutil
import tempfile
import zipfile

import fiona
from django.conf import settings
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from projects.api.serializers import *
from projects.models import OrganizationCategory, Organization, Project, DefaultTheme, LayerTemplate, LayerTemplateAttribute
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
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class ProjectViewset(viewsets.ModelViewSet):
    queryset = Project.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = ProjectSerializer
    serializer_classes = {
        'list': ProjectListSerializer,
        'retrieve': ProjectSerializer
    }
    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

class DefaultThemeViewset(viewsets.ModelViewSet):
    queryset = Organization.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = OrganizationSerializer
    serializer_classes = {
        'list': DefaultThemeListSerializer,
        'retrieve': DefaultThemeSerializer
    }
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
