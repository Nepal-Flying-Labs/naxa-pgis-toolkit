import glob
import os
import shutil
import zipfile
from distutils.command.config import config

import geopandas as gpd
import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from shapely import speedups
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from sqlalchemy import create_engine

from config.settings.base import env
from config.settings.local import geoserver

from .models import FeatureCollection, Layer, LayerAttribute, LayerFile, Vectorlayer


def geoserver_layer_publish(layer_instance):
    print("geoserver layer publish called")
    '''Geoserver layer publish'''
    connection_db = create_engine(env("CONNECTION_DB"))
    table_name = layer_instance.name.replace(" ", "")
    try:
        '''creating workspace named pgis if '''
        workspaces = geoserver.get_workspaces()
        workspaces_list = []
        for data in workspaces["workspaces"]["workspace"]:
            workspaces_list.append(data['name'])
        if not "pgis" in workspaces_list:
            # For creating workspace
            geoserver.create_workspace(workspace="pgis")
        '''publishing layer in geoserver'''
        geoserver.create_featurestore(store_name=table_name,
                                      workspace='pgis',
                                      db=env("POSTGRES_DB",
                                             default='postgres'),
                                      host=env("POSTGRES_HOST",
                                               default='localhost'),
                                      pg_user=env(
                                          "POSTGRES_USER", default='postgres'),
                                      pg_password=env(
                                          "POSTGRES_PASSWORD", default='postgres'),
                                      schema='public')

        sql = f'SELECT * FROM maps_featurecollection WHERE layer_id = {layer_instance.id}'
        geoserver.publish_featurestore_sqlview(store_name=table_name, name=table_name, sql=sql, workspace='pgis')

        vector_layer_instance=Vectorlayer.objects.get(layer=layer_instance.id)
        vector_layer_instance.geoserver_workspace = "pgis"
        vector_layer_instance.geoserver_layer_name = table_name
        vector_layer_instance.save()
        return "successful"

    except Exception as e:
        print(str(e),"geo error")
        Layer.objects.filter(id=layer_instance.id).delete()
        return str(e)

def get_geometry(geometry, geom_type):
    try:
        geometry = geometry
        has_z = geometry.has_z
        if geom_type == "Point" and has_z == True:
            coords = list(geometry.coords)[0]
            point_2d = Point(coords[0], coords[1])
            geometry = point_2d.wkt
        elif geom_type == "LineString" and has_z == True:
            line_2d = LineString(
                [xy[0:2] for xy in list(geometry.coords)])
            geometry = line_2d.wkt
        elif geom_type == "Polygon" and has_z == True:
            polygon_2d = Polygon([xy[:2] for xy in list(
                geometry.exterior.coords)])
            geometry = polygon_2d.wkt
        elif geom_type == "MultiPoint":
            geom_type_check = (GEOSGeometry(str(geometry))).geom_type
            multipoint_2d = []
            if geom_type_check == "MultiPoint":
                for point in geometry:
                    coords = list(point.coords)[0]
                    point_2d = Point(coords[0], coords[1])
                    multipoint_2d.append(point_2d)
            elif geom_type_check == "Point":
                coords = list(geometry.coords)[0]
                point_2d = Point(coords[0], coords[1])
                multipoint_2d.append(point_2d)
            geometry = MultiPoint(multipoint_2d).wkt
        elif geom_type == "MultiLineString":
            geom_type_check = (GEOSGeometry(str(geometry))).geom_type
            multiline_2d = []
            if geom_type_check == "MultiLineString":
                for line in geometry:
                    line_2d = LineString([xy[0:2]
                                          for xy in list(line.coords)])
                    multiline_2d.append(line_2d)
            elif geom_type_check == "LineString":
                line_2d = LineString([xy[0:2]
                                      for xy in list(geometry.coords)])
                multiline_2d.append(line_2d)
            geometry = MultiLineString(multiline_2d).wkt
        elif geom_type == "MultiPolygon":
            geom_type_check = (GEOSGeometry(str(geometry))).geom_type
            multipolygon_2d = []
            if geom_type_check == "MultiPolygon":
                for polygon in geometry:
                    polygon_2d = Polygon([xy[:2] for xy in list(
                        polygon.exterior.coords)])
                    multipolygon_2d.append(polygon_2d)
            elif geom_type_check == "Polygon":
                polygon_2d = Polygon(
                    [xy[:2] for xy in list(geometry.exterior.coords)])
                multipolygon_2d.append(polygon_2d)
            geometry = MultiPolygon(multipolygon_2d).wkt
        return ("success", geometry)
    except Exception as e:
        return ("error", str(e))

def upload_feature(geodataframe, layer_instance, geom_type):
    '''
     POINT Z (85.40863804028356 27.67808677280469 0)
    geometry="LINESTRING Z (85.40221724500003 27.70565588100004 0, 85.40197075100008 27.69849222600004 0)"
    geometry="POLYGON Z ((85.41205525443682 27.7140865386036 0, 85.41194951018038 27.71405093740867 0, 85.41194333326912 27.71406546919642 0, 85.41193271732574 27.71406172988702 0, 85.41191940361558 27.71409166606115 0, 85.41193053112548 27.71409558634003 0, 85.41192908640868 27.71409898327857 0, 85.41203483070319 27.71413458449054 0, 85.41205525443682 27.7140865386036 0))"
    geometry="MULTILINESTRING Z ((85.40796735800006 27.68518126600003 0, 85.42683996700003 27.68700421700004 0, 85.43566465700007 27.68314605500007 0), (85.40065753100004 27.68447448200004 0, 85.40796735800006 27.68518126600003 0), (85.44492809800005 27.67909518600004 0, 85.46105563900005 27.67204051100003 0), (85.46105563900005 27.67204051100003 0, 85.47439857900008 27.66620183400005 0), (85.47439857900008 27.66620183400005 0, 85.48222060600006 27.66277815400002 0), (85.48222060600006 27.66277815400002 0, 85.49190465700008 27.65853858000003 0))"
    MULTIPOLYGON Z (((85.41322120794372 27.71333124815947 0, 85.41320612612407 27.71331073042746 0, 85.41316582220662 27.71333419454469 0, 85.41318090402149 27.71335471228085 0, 85.41322120794372 27.71333124815947 0)), ((85.41322120794372 27.71333124815947 0, 85.41313409423378 27.71338314806147 0, 85.41317209698458 27.71343366916552 0, 85.41325921071919 27.71338176924088 0, 85.41322120794372 27.71333124815947 0)))
    '''
    try:
        print("entered upload feature")
        layer_id = layer_instance.id
        for index, row in geodataframe.iterrows():
            try:
                dropped_geometry = row.drop(["geometry"])
                dropped_geometry_dict = dropped_geometry.to_dict()

                '''replacing Nan value to None'''
                for key, value in dropped_geometry_dict.items():
                    if str(value).lower() == 'nan':
                        dropped_geometry_dict[key] = None

                '''excluding z-dimension from geometry if exist and handle for different geometry type'''
                geometry = row["geometry"]
                result, data = get_geometry(geometry, geom_type)
                if result == "success":
                    geometry = data
                else:
                    return ("error : "+data)

                data_created = FeatureCollection.objects.create(
                                                             layer=layer_instance,
                                                             geometry=GEOSGeometry(
                                                                 str(geometry)),
                                                             attributes=dropped_geometry_dict,
                                                             )
            except Exception as e:
                Layer.objects.filter(id=layer_id).delete()
                return ("error : "+str(e))
        try:
            for col_name in geodataframe.columns:
                if col_name != 'geometry':
                    LayerAttribute.objects.create(
                        layer=layer_instance, name=col_name)
        except Exception as e:
            Layer.objects.filter(id=layer_id).delete()
            return ("attribute_error : "+str(e))

        # '''Geoserver layer publish'''
        response = geoserver_layer_publish(layer_instance)
        # if not response == "successful":
        #     Layer.objects.filter(id=layer_id).delete()
        return response

    except Exception as e:
        Layer.objects.filter(id=layer_id).delete()
        return str(e)


def handleShapeFile(layer_id):
    try:
        print("handle shapefile entered")
        errors = []
        layer_instance = Layer.objects.get(id=layer_id)
        vector_layer_instance = Vectorlayer.objects.get(layer=layer_id)
        layer_file = LayerFile.objects.get(layer=layer_id).file.path
        file_path = os.path.dirname(layer_file)
        with zipfile.ZipFile(layer_file, 'r') as zip_ref:
            zip_ref.extractall(file_path)

        shape = glob.glob(
            r'{}/**/*.shp'.format(file_path), recursive=True)[0]
        geodataframe = gpd.read_file(shape)
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
                Layer.objects.filter(id=layer_id).delete()
                return "Unknown Coordinate System", None

        '''validaing geometry type'''
        geom_types = []
        geom_type = None
        for index, row in geodataframe.iterrows():
            geom_type = (GEOSGeometry(
                str(row["geometry"]))).geom_type
            if geom_type not in geom_types:
                geom_types.append(geom_type)
        if len(geom_types) == 1:
            geom_type = geom_type
        elif len(geom_types) == 2:
            if "Point" and "MultiPoint" in geom_types:
                geom_type = "MultiPoint"
            elif "LineString" and "MultiLineString" in geom_types:
                geom_type = "MultiLineString"
            elif "Polygon" and "MultiPolygon" in geom_types:
                geom_type = "MultiPolygon"
            else:
                Layer.objects.filter(id=layer_id).delete()
                return (f"error occured : more than one geometry type is found i.e. {geom_types}")
        elif len(geom_types) > 2:
            return (f"error occured : more than one geometry type is found i.e. {geom_types}")
        else:
            Layer.objects.filter(id=layer_id).delete()
            return (f"error occured : missing geometry")

        vector_layer_instance.geom_type = geom_type
        vector_layer_instance.save()

        response = upload_feature(
            geodataframe, layer_instance, geom_type)
        return response
    except Exception as e:
        Layer.objects.filter(id=layer_id).delete()
        return ("error occured : " + str(e))


# @shared_task(max_retries=1, soft_time_limit=8000)
def handleCSV(layer_id,lat_field,lon_field):
    try:
        layer_instance = Layer.objects.get(id=layer_id)
        file_object = LayerFile.objects.get(layer=layer_id)
        my_file = file_object.file.path
        file_path = os.path.dirname(my_file)
        df = pd.read_csv(my_file, keep_default_na=False)
        crs = {'init': 'epsg:4326'}

        geometry = gpd.points_from_xy(df[lon_field], df[lat_field])
        crs = {'init': 'epsg:4326'}

        '''saving geometry type'''
        geom_type = "Point"
        layer_instance.geom_type = "Point"
        layer_instance.save()

        geodataframe = gpd.GeoDataFrame(df, crs=crs, geometry=geometry)

        response = upload_feature(
            geodataframe, layer_instance,geom_type)
        return response
    except Exception as e:
        Layer.objects.filter(id=layer_id).delete()
        return ("error occured : " + str(e))


# @shared_task(max_retries=1, soft_time_limit=8000)
def handleGeoJSON(shapefile_id, layer_id, dataset_name, user_id, data_type):
    try:
        layer_object = Layer.objects.get(id=layer_id)
        file_object = Shapefile.objects.get(id=shapefile_id)
        my_file = file_object.file.path
        file_path = os.path.dirname(my_file)
        geodataframe = gpd.read_file(my_file)

        '''coordinate system validation'''
        epsg = geodataframe.crs.to_epsg()
        utm_zone = geodataframe.crs.utm_zone,
        if epsg != 4326:
            if utm_zone:
                Layer.objects.filter(id=layer_id).delete()
                return "Invalid Coordinate System, only WGS84 coordinate system will be accepted", None
            else:
                Layer.objects.filter(id=layer_id).delete()
                return "Unknown Coordinate System", None

        '''validaing geometry type'''
        geom_types = []
        geom_type = None
        for index, row in geodataframe.iterrows():
            geom_type = (GEOSGeometry(
                str(row["geometry"]))).geom_type
            if geom_type not in geom_types:
                geom_types.append(geom_type)
        if len(geom_types) == 1:
            geom_type = geom_type
        elif len(geom_types) == 2:
            if "Point" and "MultiPoint" in geom_types:
                geom_type = "MultiPoint"
            elif "LineString" and "MultiLineString" in geom_types:
                geom_type = "MultiLineString"
            elif "Polygon" and "MultiPolygon" in geom_types:
                geom_type = "MultiPolygon"
            else:
                Layer.objects.filter(id=layer_id).delete()
                return (f"error occured : more than one geometry type is found i.e. {geom_types}")
        elif len(geom_types) > 2:
            Layer.objects.filter(id=layer_id).delete()
            return (f"error occured : more than one geometry type is found i.e. {geom_types}")
        else:
            Layer.objects.filter(id=layer_id).delete()
            return (f"error occured : missing geometry")

        '''save geometry type'''
        layer_object.geom_type = geom_type
        layer_object.save()

        response = upload_feature(
            geodataframe, layer_object, shapefile_id, dataset_name, user_id, data_type, geom_type)
        return response
    except Exception as e:
        Layer.objects.filter(id=layer_id).delete()
        return ("error occured : " + str(e))
