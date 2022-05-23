import os

from celery import Celery, shared_task
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from config.settings.local import geoserver
from pgis_toolkit.maps.api.serializers import (
    VectorLayerSerializer,
    VectorLayerUpdateSerializer,
)
from pgis_toolkit.maps.models import (
    FeatureCollection,
    Layer,
    LayerFile,
    SubLayer,
    Vectorlayer,
    WMSLayer,
)

from .functions import handleCSV, handleGeoJSON, handleShapeFile


@shared_task(max_retries=1, soft_time_limit=8000)
def UploadVectorLayer(layer_id):
    print("entered UploadVectorLayer")
    errors=[]
    try:
        layer_instance=Layer.objects.get(id=layer_id)
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
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured2', 'error': str(e)})

        elif file_extension == ".geojson":
            response = handleGeoJSON(layer_id)
        else:
            return 'Error Occured: Invalid file extension', None

    except Exception as e:
        Layer.objects.filter(id=layer_id).delete()
        errors.append({'errorName': str(e), 'details': str(e)})
        return 'Error Occured: '+ str(errors), None
        # return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'error occured', 'error': errors})


def UpdateVectorLayer(layer_instance, request_data):
    try:
        # geoserver.create_workspace(workspace="custom_workspace")
        errors=[]
        vector_layer_instance=Vectorlayer.objects.get(layer=layer_instance.id)
        vector_layer_serializer = VectorLayerUpdateSerializer(vector_layer_instance, data=request_data, partial=True)
        if vector_layer_serializer.is_valid():
            vector_layer_serializer.save()
        else:
            for er in vector_layer_serializer._errors:
                errors.append(
                    {'errorName': er, 'details': vector_layer_serializer._errors[er][0]})
            return errors

        if "sub_layers_mapping_field" in request_data.keys() and "sub_layers_mapping_field" !="":
            sub_layers_mapping_field=request_data['sub_layers_mapping_field']

            '''deleting sub layer instance if exists'''
            SubLayer.objects.filter(layer=layer_instance.id).delete()

            '''creating sub layers'''
            feature_coll_qs=FeatureCollection.objects.filter(layer=layer_instance.id)
            sublayer_name_list = []

            for feature in feature_coll_qs:
                sub_layer_name=feature.attributes[sub_layers_mapping_field]
                if sub_layer_name not in sublayer_name_list:
                    sublayer_name_list.append(sub_layer_name)

            for sub_layer_name in sublayer_name_list:
                sublayer_instance = SubLayer.objects.create(
                    layer=layer_instance,
                    name=sub_layer_name
                )
                for feature in feature_coll_qs:
                    if(feature.attributes[sub_layers_mapping_field] == sub_layer_name):
                        # feature_coll_qs.filter(id=feature.id).update(sub_layer=sublayer_instance)
                        feature.sub_layer=sublayer_instance
                        feature.save()
        return "successful"
    except Exception as e:
        return str(e)

def UploadRasterLayer(layer_id, request_dict):
    pass

def UploadWMSLayer(layer_id, request_dict):
    if 'url' in request_dict.keys() and request_dict['url'] != "":
        layer_instance = Layer.active.get(id=layer_id)
        WMSLayer.objects.get_or_create(layer=layer_instance, url=request_dict['url'])
    return Response(data={'message': 'URL is mandatory!'}, status=status.HTTP_400_BAD_REQUEST)
