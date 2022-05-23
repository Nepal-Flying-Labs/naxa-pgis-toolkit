import os

from celery import Celery, shared_task
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from config.settings.local import geoserver
from pgis_toolkit.maps.api.serializers import (
    VectorLayerSerializer,
    VectorLayerUpdateSerializer
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
def UploadVectorLayer(layer_id,request_data):
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
            # try:
            lat_field = request_data.get('lat_field')
            lon_field = request_data.get('lon_field')
            if not lat_field or not lon_field:
                return "error occured: lat_field and lon_field are required" ,None
            response = handleCSV(layer_id,lat_field,lon_field)
            if response=="successful":
                return "successful", layer_id
            else:
                return response, None
        elif file_extension == ".geojson":
            response = handleGeoJSON(layer_id)
            if response=="successful":
                return "successful", layer_id
            else:
                return response, None
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

@shared_task(max_retries=1, soft_time_limit=8000)
def UploadRasterLayer(layer_id, request_dict):
    from pgis_toolkit.maps.models import Layer, LayerFile, RasterLayer
    from pgis_toolkit.maps.api.serializers import RasterLayerSerializer
    from config.settings.local import geoserver
    from config.settings.base import env, MEDIA_ROOT
    from django.core.files import File
    from pgis_toolkit.maps.functions import clear_dir

    try:
        errors=[]
        layer_instance = Layer.active.get(pk=layer_id)
        raster_layer_instance = RasterLayer.objects.get(layer=layer_id)
        layer_file_instance = LayerFile.objects.get(layer=layer_id)
        workspace = "pgis_" + str(layer_instance.theme.project.id)
        request_dict['geoserver_workspace'] = workspace
        request_dict['geoserver_layer_name'] = layer_instance.name
        raster_layer_serializer = RasterLayerSerializer(raster_layer_instance, data=request_dict, partial=True)
        if raster_layer_serializer.is_valid():
            raster_layer_serializer.save()
        else:
            for er in raster_layer_serializer._errors:
                errors.append(
                    {'errorName': er, 'details': raster_layer_serializer._errors[er][0]})
            return errors
        path = 'pgis_toolkit/media/' + str(layer_file_instance.file)
        workspaces = geoserver.get_workspaces()
        workspaces_list = []
        for data in workspaces["workspaces"]["workspace"]:
            workspaces_list.append(data['name'])
        if not raster_layer_instance.geoserver_workspace in workspaces_list:
            # For creating workspace
            geoserver.create_workspace(workspace=raster_layer_instance.geoserver_workspace)
        # print(raster_layer_instance.geoserver_layer_name, "is raster layer instance")
        # print(path, "is path")
        # print(raster_layer_instance.geoserver_workspace, "is raster layer workspace")
        '''For uploading raster data to the geoserver'''
        geoserver.create_coveragestore(
            layer_name=raster_layer_instance.geoserver_layer_name, path=path, workspace=raster_layer_instance.geoserver_workspace)

        if raster_layer_instance.sld:
            os.makedirs(MEDIA_ROOT + "/raster_layer_sld", exist_ok=True)
            sld_content = raster_layer_instance.sld
            f = open(MEDIA_ROOT + "/raster_layer_sld/" +
                     raster_layer_instance.geoserver_layer_name + '.sld', 'w')
            sld_file = File(f)
            sld_file.write(sld_content)
            f.close()
            sld_path = 'pgis_toolkit/media/raster_layer_sld/' + raster_layer_instance.geoserver_layer_name+'.sld'
            '''For uploading SLD file and connect it with layer'''
            geoserver.upload_style(
                path=sld_path, workspace=raster_layer_instance.geoserver_workspace)
            geoserver.publish_style(layer_name=raster_layer_instance.geoserver_layer_name,
                                    style_name=raster_layer_instance.geoserver_layer_name, workspace=raster_layer_instance.geoserver_workspace)
            '''clearing the uploaded file directory'''
        dir = MEDIA_ROOT + '/geofiles'
        clear_dir(dir)
        return "successful", layer_id
    except Exception as e:
        layer_instance.delete()
        layer_file_instance.delete()
        return str(e), None


def UploadWMSLayer(layer_id, request_dict):
    if 'url' in request_dict.keys() and request_dict['url'] != "":
        layer_instance = Layer.active.get(id=layer_id)
        WMSLayer.objects.get_or_create(layer=layer_instance, url=request_dict['url'])
    return Response(data={'message': 'URL is mandatory!'}, status=status.HTTP_400_BAD_REQUEST)
