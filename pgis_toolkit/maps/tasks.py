import os

from celery import Celery, shared_task
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from pgis_toolkit.maps.models import Layer, LayerFile, Vectorlayer, WMSLayer

from .functions import handleCSV, handleGeoJSON, handleShapeFile


@shared_task(max_retries=1, soft_time_limit=8000)
def UploadVectorLayer(layer_id):
    errors=[]
    try:
        print(layer_id,"layer_iddddddddddddddd")
        layer_instance=Layer.objects.get(id=layer_id)
        # '''create vector layer instance'''
        # vector_layer_instance=Vectorlayer.objects.get_or_create(layer=layer_instance)
        layer_file_instance=LayerFile.objects.get(layer=layer_id)

        '''Knowing file extension'''
        path_split = os.path.splitext(layer_file_instance.file.name)
        file_extension = path_split[1]
        if file_extension == ".zip":
            response = handleShapeFile(layer_id)
            if response=="successful":
                return "successful", layer_id
            else:
                return response, None
        elif file_extension == ".csv":
            try:
                # lat_field = request_data.get('lat')
                # lon_field = request_data.get('lon')
                response = handleCSV(layer_id)
            except Exception as e:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'Message': 'Error Occured', 'Error': str(e)})

        elif file_extension == ".geojson":
            response = handleGeoJSON(layer_id)
        else:
            return 'Error Occured: Invalid file extension', None

    except Exception as e:
        errors.append({'errorName': str(e), 'details': str(e)})
        return 'Error Occured: '+ str(errors), None
        # return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'error occured', 'error': errors})

def UploadRasterLayer(layer_id, request_dict):
    pass

def UploadWMSLayer(layer_id, request_dict):
    if 'url' in request_dict.keys() and request_dict['url'] != "":
        layer_instance = Layer.active.get(id=layer_id)
        WMSLayer.objects.get_or_create(layer=layer_instance, url=request_dict['url'])
    return Response(data={'message': 'URL is mandatory!'}, status=status.HTTP_400_BAD_REQUEST)
