import glob
import json
import os
import shutil
import time
import zipfile
from logging import exception

import geopandas
from celery import Celery, shared_task
from django.db import connection, transaction
from rest_framework import filters, status, viewsets
from rest_framework.response import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config.settings.base import MEDIA_ROOT, env
from config.settings.local import geoserver
from pgis_toolkit.maps.api.serializers import (
    VectorLayerSerializer,
    VectorLayerUpdateSerializer,
)
from pgis_toolkit.maps.models import (
    FeatureCollection,
    Layer,
    LayerFile,
    LayerStyle,
    ProjectStyle,
    StandardIcon,
    SubLayer,
    Vectorlayer,
    WMSLayer,
)
from pgis_toolkit.maps.utils.functions import clear_dir
from pgis_toolkit.maps.utils.layer_upload import (
    handleCSV,
    handleGeoJSON,
    handleGPX,
    handleKML,
    handleShapeFile,
)


@shared_task(max_retries=1, soft_time_limit=8000)
def UploadVectorLayer(layer_id,request_data):
    print("entered UploadVectorLayer",layer_id)
    errors=[]
    dir = MEDIA_ROOT+"/geofiles/"
    try:
        layer_file_instance=None
        tries=1
        while tries<3:
            if Layer.objects.filter(id=layer_id).exists() and LayerFile.objects.filter(layer=layer_id).exists():
                layer_file_instance=LayerFile.objects.get(layer=layer_id)
                break
            time.sleep(3)
        if not layer_file_instance:
            return 'Error Occured from UploadVectorLayer: couldnot save/extract upoaded file', None

        '''Knowing file extension'''
        path_split = os.path.splitext(layer_file_instance.file.name)
        file_extension = path_split[1]
        if file_extension == ".zip":
            response = handleShapeFile(layer_id)
        elif file_extension == ".csv":
            lat_field = request_data.get('lat_field')
            lon_field = request_data.get('lon_field')
            if not lat_field or not lon_field:
                return "error occured: lat_field and lon_field are required" ,None
            response = handleCSV(layer_id,lat_field,lon_field)
        elif file_extension == ".geojson":
            response = handleGeoJSON(layer_id)
        elif file_extension == ".kml":
            response = handleKML(layer_id)
        elif file_extension == ".gpx":
            response = handleGPX(layer_id)
        else:
            clear_dir(dir)
            return 'Error Occured: Invalid file extension', None

        clear_dir(dir)
        if response=="successful":
            return "successful", layer_id
        else:
            Layer.objects.filter(id=layer_id).delete()
            return response, None

    except Exception as e:
        clear_dir(dir)
        Layer.objects.filter(id=layer_id).delete()
        errors.append({'errorName': str(e), 'details': str(e)})
        return 'Error Occured from UploadVectorLayer: '+ str(errors), None


# '''not in use'''
# def update_bbox(layer_instance):
#     '''calculate and save bbox of sub_layer'''
#     db_connection_url = env("CONNECTION_DB", default="postgresql://xIDokAfQUYOjTGhErprxMHnjZTJXMloY:gn63GjyG9AOKLYgrvOcOZFrAeYgjLOA4IkjuTXzISZ3nnMaHxTX1rSxI0fdBSb52@postgres:5432/pgis_toolkit")
#     con = create_engine(db_connection_url)

#     sub_layer_qs=SubLayer.objects.filter(layer=layer_instance.id)
#     try:
#         for sub_layer in sub_layer_qs:

#             # with transaction.atomic():
#                 # connection.connect()
#             # time.sleep(10)
#             presql = f"SELECT id,layer_id,sub_layer_id,geometry AS geom FROM maps_featurecollection WHERE layer_id={layer_instance.id}"
#             presub_layer_gdf = geopandas.GeoDataFrame.from_postgis(presql, con)
#             print(presql,presub_layer_gdf)
#             print(FeatureCollection.objects.filter(layer=layer_instance.id,sub_layer=sub_layer.id).values_list('sub_layer'),"qs_len")
#             # FeatureCollection.objects.filter(layer=layer_instance.id).refresh_from_db()
#             sql = f"SELECT id,sub_layer_id,geometry AS geom FROM maps_featurecollection WHERE layer_id={layer_instance.id} AND sub_layer_id={sub_layer.id}"
#             sub_layer_gdf = geopandas.GeoDataFrame.from_postgis(sql, con)
#             print(sql,"postsql")
#             '''extracting extent'''
#             print(sub_layer_gdf,"sub_layer_gdf")
#             total_bounds = sub_layer_gdf.total_bounds if sub_layer_gdf else []
#             sub_layer.bbox = total_bounds.tolist()
#             sub_layer.save()

#     except Exception as e:
#         print(str(e),"error in bbox calculation")

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
                    {'errorName11': er, 'details': vector_layer_serializer._errors[er][0]})
            return errors

        '''Save vector layer style'''
        project_style=None if request_data['project_style']=="default" else request_data['project_style']
        style_qs=LayerStyle.objects.filter(layer=layer_instance.id,project_style=project_style)

        if style_qs.exists():
            layerstyle_instance=style_qs[0]
        else:
            project_style_instance=ProjectStyle.active.get(id=project_style) if project_style else None
            layerstyle_instance=LayerStyle.objects.create(layer=layer_instance,project_style=project_style_instance)
        if 'icon' in request_data.keys():
            layerstyle_instance.icon=request_data['icon']
        if 'icon_size' in request_data.keys():
            layerstyle_instance.icon_size=json.loads(request_data['icon_size'])
        if 'style' in request_data.keys():
            layerstyle_instance.style=json.loads(request_data['style'])
        if 'std_icon' in request_data.keys():
            layerstyle_instance.std_icon=StandardIcon.objects.get(id=request_data['std_icon']) if request_data['std_icon'] else None
        layerstyle_instance.save()

        if "sub_layers_mapping_field" in request_data.keys() and request_data['sub_layers_mapping_field'] !="":
            # with transaction.atomic():
            sub_layers_mapping_field=request_data['sub_layers_mapping_field']
            '''deleting sub layer instance if exists'''
            SubLayer.objects.filter(layer=layer_instance.id).delete()

            '''creating sub layers'''
            feature_coll_qs=FeatureCollection.active.filter(layer=layer_instance.id)
            feature_coll_qs.update(sub_layer=None)
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
                        # with transaction.atomic():
                        feature.sub_layer=sublayer_instance
                        feature.save()
                        # print(feature.sub_layer,"after save")
            # update_bbox(layer_instance)
        return "successful"
    except Exception as e:
        return str(e)

@shared_task(max_retries=1, soft_time_limit=8000)
def UploadRasterLayer(layer_id, request_dict):
    from django.core.files import File

    from config.settings.base import MEDIA_ROOT, env
    from config.settings.local import geoserver
    from pgis_toolkit.maps.api.serializers import RasterLayerSerializer
    from pgis_toolkit.maps.models import Layer, LayerFile, RasterLayer
    from pgis_toolkit.maps.utils.functions import clear_dir

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

@shared_task(max_retries=1, soft_time_limit=8000)
def UpdateRasterLayer(layer_id, request_dict):
    from django.core.files import File

    from config.settings.base import MEDIA_ROOT
    from config.settings.local import geoserver
    from pgis_toolkit.maps.models import Layer, RasterLayer
    '''update sld of raster layer'''
    try:
        layer_instance = Layer.active.get(pk=layer_id)
        raster_layer_instance = RasterLayer.objects.get(layer=layer_id)
        if 'sld' in request_dict.keys() and request_dict['sld'] != '':
            raster_layer_instance.sld = request_dict['sld']
            raster_layer_instance.save()
            geoserver.delete_style(style_name=raster_layer_instance.geoserver_layer_name, workspace=raster_layer_instance.geoserver_workspace)
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
            return "successful", layer_id
        return "successful", layer_id
    except Exception as e:
        return str(e), None

def UploadWMSLayer(layer_id, request_dict):
    if 'url' in request_dict.keys() and request_dict['url'] != "":
        layer_instance = Layer.active.get(id=layer_id)
        WMSLayer.objects.get_or_create(layer=layer_instance, url=request_dict['url'])
    return Response(data={'message': 'URL is mandatory!'}, status=status.HTTP_400_BAD_REQUEST)


def handleDataMergeUpdate(layer_id):
    try:
        print("handle handleDataMergeUpdate entered")
        errors = []
        layer_instance = Layer.objects.get(id=layer_id)
        vector_layer_instance = Vectorlayer.objects.get(layer=layer_id)
        layer_file = LayerFile.objects.get(layer=layer_id).file.path
        file_path = os.path.dirname(layer_file)
        with zipfile.ZipFile(layer_file, 'r') as zip_ref:
            zip_ref.extractall(file_path)
        shape = glob.glob(
            r'{}/**/*.shp'.format(file_path), recursive=True)[0]
        geodataframe = geopandas.read_file(shape)
        try:
            shutil.rmtree(file_path)
        except OSError as e:
            print("Error: %s " % (e.strerror))
        epsg = geodataframe.crs.to_epsg()
        utm_zone = geodataframe.crs.utm_zone,
        if epsg != 4326:
            if utm_zone:
                return "Invalid Coordinate System, only WGS84 coordinate system will be accepted", None
            else:
                return "Unknown Coordinate System", None
        '''retrieving properties from the shapefile using fiona'''
        c = fiona.open(shape)
        schema=c.schema
        geom_type=schema['geometry']
        '''validaing geometry type'''
        if vector_layer_instance.geom_type != geom_type:
            return (f"Existing layer geom type {vector_layer_instance.geom_type} and incoming data geom type {geom_type} doesn't match!")
        col_properties = {}
        for data in schema['properties']:
            data_type=schema['properties'][data].split(':')[0]
            if data_type=='str' or data_type=='int':
                length=schema['properties'][data].split(':')[1]
                precision = None
            elif data_type=="float":
                length = schema['properties'][data].split(':')[1].split('.')[0]
                precision = schema['properties'][data].split(':')[1].split('.')[1]
            values_list = [data_type, length, precision]
            col_properties[str(data)] = values_list
        col_prop_keys = col_properties.keys()
        layer_attributes_qs = LayerAttribute.objects.select_related('layer').filter(layer=layer_instance).values('name', 'data_type', 'length', 'precision')
        for attr in layer_attributes_qs:
            '''validating column, data type, length and precision'''
            name = attr['name']
            if name not in col_prop_keys: return (f'column {name} is missing in uploading file.')
            values_list = col_properties[name]
            if attr['data_type'] != values_list[0]: return (f'Existing data type {attr["data_type"]} and incoming data type {values_list[0]} of column {name} does not match!')
            if attr['length'] != values_list[1]: return (f'Existing data length {attr["length"]} and incoming data length {values_list[1]} of column {name} does not match!')
            if attr['precision'] != values_list[2]: return (f'Existing data precision {attr["precision"]} and incoming data precision {values_list[2]} of column {name} does not match!')

        '''update/merge data using geopandas'''
        response = update_merge_data(geodataframe)

        '''update extent of the layer'''
        total_bounds = geodataframe.total_bounds
        vector_layer_instance.bbox = total_bounds.tolist()
        vector_layer_instance.save()

        # response = upload_feature(
        #     geodataframe, layer_instance, geom_type)
        return response
    except Exception as e:
        return ("error occured in handle shapefile: " + str(e))
