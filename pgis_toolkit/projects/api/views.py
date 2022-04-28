import os
import shutil
import tempfile

import fiona
from django.conf import settings
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from projects.api.serializers import *
from projects.models import LayerTemplate, LayerTemplateAttribute
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView


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
