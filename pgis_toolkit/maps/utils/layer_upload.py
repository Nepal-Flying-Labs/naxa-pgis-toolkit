import glob
import json
import os
import shutil
import zipfile
from distutils.command.config import config

os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
import kml2geojson
import numpy as np
import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction
from shapely import force_2d, from_wkt, speedups
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from config.settings.base import MONGO_DB, env
from config.settings.local import geoserver
from pgis_toolkit.maps.models import (
    FeatureCollection,
    Layer,
    LayerAttribute,
    LayerFile,
    Vectorlayer,
)

'''
class Geoserver1:
    """
    Attributes
    ----------
    service_url : str
        The URL for the GeoServer instance.
    username : str
        Login name for session.
    password: str
        Password for session.
    """

    def __init__(
        self,
        service_url: str = "http://geoserver:8080/geoserver",  # default deployment url during installation
        username: str = "admin",  # default username during geoserver installation
        password: str = "geoserver",  # default password during geoserver installation
    ):
        self.service_url = service_url
        self.username = username
        self.password = password

        # private request method to reduce repetition of putting auth(username,password) in all requests call. DRY principle

    def _requests(self, method: str, url: str, **kwargs) -> requests.Response:
        if method == "post":
            return requests.post(url, auth=(self.username, self.password), **kwargs)
        elif method == "get":
            return requests.get(url, auth=(self.username, self.password), **kwargs)
        elif method == "put":
            return requests.put(url, auth=(self.username, self.password), **kwargs)

    def get_workspaces(self):
        """
        Returns all the workspaces.
        """
        try:
            url = "{}/rest/workspaces".format(self.service_url)
            r = requests.get(url, auth=(self.username, self.password))
            return r.json()

        except Exception as e:
            return "get_workspaces error: {}".format(e)

    def publish_featurestore_sqlview(
        self,
        name: str,
        store_name: str,
        sql: str,
        geom_name: str = "geom",
        geom_type: str = "Geometry",
        srid: Optional[int] = 4326,
        workspace: Optional[str] = None,
    ):
        """

        Parameters
        ----------
        name : str
        store_name : str
        sql : str
        geom_name : str
        geom_type : str
        workspace : str, optional

        """
        if workspace is None:
            workspace = "default"

        layer_xml = """<featureType>
        <name>{0}</name>
        <enabled>"off"</enabled>
        <inMemoryCached>false</inMemoryCached>
        <namespace>
            <name>{4}</name>
        </namespace>
        <title>{0}</title>
        <srs>EPSG:{5}</srs>
        <metadata>
            <entry key="JDBC_VIRTUAL_TABLE">
                <virtualTable>
                    <name>{0}</name>
                    <sql>{1}</sql>
                    <escapeSql>true</escapeSql>
                    <geometry>
                        <name>{2}</name>
                        <type>{3}</type>
                        <srid>{5}</srid>
                    </geometry>
                </virtualTable>
            </entry>
        </metadata>
        </featureType>""".format(
            name, sql, geom_name, geom_type, workspace, srid
        )

        url = "{}/rest/workspaces/{}/datastores/{}/featuretypes".format(
            self.service_url, workspace, store_name
        )

        headers = {"content-type": "text/xml"}

        try:
            r = requests.post(
                url,
                data=layer_xml,
                auth=(self.username, self.password),
                headers=headers,
            )
            if r.status_code not in [200, 201]:
                return "{}: Data can not be published! {}".format(
                    r.status_code, r.content
                )

        except Exception as e:
            return "Error: {}".format(e)

def test_advertised():
    geoserver1=Geoserver1()
    print(geoserver1.get_workspaces(),"geoserver1")
    sql = 'SELECT * FROM maps_featurecollection WHERE layer_id = 309'
    geoserver.publish_featurestore_sqlview(store_name="SecurityForcesGeoserver88", name="SecurityForcesGeoserver88_mannual7", sql=sql, workspace='pgis')
'''

def get_standard_dtype(dtype):
    dtype = str(dtype)
    if dtype == 'int64':
        return 'int'
    elif dtype == 'float64':
        return 'float'
    elif dtype == 'datetime64':
        return 'date'
    elif dtype == 'object' or dtype == 'bool':
        return 'str'
    else:
        return 'unknown'

def geoserver_layer_publish(layer_instance):
    # print("geoserver layer publish called")
    '''Geoserver layer publish'''
    table_name = layer_instance.name.replace(" ", "")
    try:
        '''creating workspace named pgis if '''
        workspaces = geoserver.get_workspaces()
        workspaces_list = []
        for data in workspaces["workspaces"]["workspace"]:
            workspaces_list.append(data['name'])
        workspace_name='pgis_'+str(layer_instance.theme.project.id)
        if not workspace_name in workspaces_list:
            # For creating workspace
            geoserver.create_workspace(workspace=workspace_name)
        '''publishing layer in geoserver'''
        geoserver.create_featurestore(store_name=table_name,
                                      workspace=workspace_name,
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
        geoserver.publish_featurestore_sqlview(store_name=table_name, name=table_name, sql=sql, workspace=workspace_name)

        vector_layer_instance=Vectorlayer.objects.get(layer=layer_instance.id)
        vector_layer_instance.geoserver_workspace = workspace_name
        vector_layer_instance.geoserver_layer_name = table_name
        vector_layer_instance.save()
        return "successful"

    except Exception as e:
        return "geoserver error: "+str(e)

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

# def upload_feature(geodataframe, layer_instance, geom_type):
#     '''
#      POINT Z (85.40863804028356 27.67808677280469 0)
#     geometry="LINESTRING Z (85.40221724500003 27.70565588100004 0, 85.40197075100008 27.69849222600004 0)"
#     geometry="POLYGON Z ((85.41205525443682 27.7140865386036 0, 85.41194951018038 27.71405093740867 0, 85.41194333326912 27.71406546919642 0, 85.41193271732574 27.71406172988702 0, 85.41191940361558 27.71409166606115 0, 85.41193053112548 27.71409558634003 0, 85.41192908640868 27.71409898327857 0, 85.41203483070319 27.71413458449054 0, 85.41205525443682 27.7140865386036 0))"
#     geometry="MULTILINESTRING Z ((85.40796735800006 27.68518126600003 0, 85.42683996700003 27.68700421700004 0, 85.43566465700007 27.68314605500007 0), (85.40065753100004 27.68447448200004 0, 85.40796735800006 27.68518126600003 0), (85.44492809800005 27.67909518600004 0, 85.46105563900005 27.67204051100003 0), (85.46105563900005 27.67204051100003 0, 85.47439857900008 27.66620183400005 0), (85.47439857900008 27.66620183400005 0, 85.48222060600006 27.66277815400002 0), (85.48222060600006 27.66277815400002 0, 85.49190465700008 27.65853858000003 0))"
#     MULTIPOLYGON Z (((85.41322120794372 27.71333124815947 0, 85.41320612612407 27.71331073042746 0, 85.41316582220662 27.71333419454469 0, 85.41318090402149 27.71335471228085 0, 85.41322120794372 27.71333124815947 0)), ((85.41322120794372 27.71333124815947 0, 85.41313409423378 27.71338314806147 0, 85.41317209698458 27.71343366916552 0, 85.41325921071919 27.71338176924088 0, 85.41322120794372 27.71333124815947 0)))
#     '''
#     try:
#         print("entered upload feature")
#         layer_id = layer_instance.id
#         for index, row in geodataframe.iterrows():
#             try:
#                 dropped_geometry = row.drop(["geometry"])
#                 dropped_geometry_dict = dropped_geometry.to_dict()

#                 '''replacing Nan value to None'''
#                 for key, value in dropped_geometry_dict.items():
#                     if str(value).lower() == 'nan':
#                         dropped_geometry_dict[key] = None

#                 '''excluding z-dimension from geometry if exist and handle for different geometry type'''
#                 geometry = row["geometry"]
#                 result, data = get_geometry(geometry, geom_type)
#                 if result == "success":
#                     geometry = data
#                 else:
#                     return ("error : "+data)

#                 data_created = FeatureCollection.objects.create(
#                                                              layer=layer_instance,
#                                                              geometry=GEOSGeometry(
#                                                                  str(geometry)),
#                                                              attributes=dropped_geometry_dict,
#                                                              )
#             except Exception as e:
#                 # Layer.objects.filter(id=layer_id).delete()
#                 return ("error : "+str(e))
#         try:
#             for col_name in geodataframe.columns:
#                 if col_name != 'geometry':
#                     dtype = geodataframe[col_name].dtypes
#                     data_type = get_standard_dtype(dtype)
#                     LayerAttribute.objects.create(
#                         layer=layer_instance, name=col_name, data_type=data_type)
#         except Exception as e:
#             # Layer.objects.filter(id=layer_id).delete()
#             return ("attribute_error : "+str(e))

#         # '''Geoserver layer publish'''
#         # response = geoserver_layer_publish(layer_instance)
#         # return response
#         return "successful"

#     except Exception as e:
#         # Layer.objects.filter(id=layer_id).delete()
#         return "error in feature upload: "+str(e)

def upload_feature(geodataframe, layer_instance, geom_type):
    try:
        print("entered upload feature")
        feature_objs = []
        try:
            for index, row in geodataframe.iterrows():
                dropped_geometry = row.drop(["geometry"])
                dropped_geometry_dict = dropped_geometry.to_dict()
                feature_objs.append(FeatureCollection(layer=layer_instance, geometry=GEOSGeometry(str(row['geometry'])),                     attributes=dropped_geometry_dict))
            FeatureCollection.active.bulk_create(feature_objs)
        except Exception as e:
            return ("error : "+str(e))
        try:
            feature_qs = FeatureCollection.active.filter(layer=layer_instance).values('id', 'feature', 'layer', 'sub_layer', 'attributes')
            if feature_qs:
                feature_coll = MONGO_DB['featurecollections']
                feature_coll.insert_many(feature_qs)
        except Exception as e:
            return ("feature attributes sync to mongo failed")
        try:
            for col_name in geodataframe.columns:
                if col_name != 'geometry':
                    dtype = geodataframe[col_name].dtypes
                    data_type = get_standard_dtype(dtype)
                    LayerAttribute.objects.create(
                        layer=layer_instance, name=col_name, data_type=data_type)
        except Exception as e:
            # Layer.objects.filter(id=layer_id).delete()
            return ("attribute_error : "+str(e))

        # '''Geoserver layer publish'''
        # response = geoserver_layer_publish(layer_instance)
        # return response
        return "successful"

    except Exception as e:
        # Layer.objects.filter(id=layer_id).delete()
        return "error in feature upload: "+str(e)

# def validate_geometry_type(geodataframe):
#     print("validate gemetry typ e entered")
#     try:
#         geom_types = []
#         geom_type = None
#         for index, row in geodataframe.iterrows():
#             geom_type = (GEOSGeometry(
#                 str(row["geometry"]))).geom_type
#             if geom_type not in geom_types:
#                 geom_types.append(geom_type)
#         if len(geom_types) == 1:
#             geom_type = geom_type
#         elif len(geom_types) == 2:
#             if "Point" and "MultiPoint" in geom_types:
#                 geom_type = "MultiPoint"
#             elif "LineString" and "MultiLineString" in geom_types:
#                 geom_type = "MultiLineString"
#             elif "Polygon" and "MultiPolygon" in geom_types:
#                 geom_type = "MultiPolygon"
#             else:
#                 return (f"error occured : more than one geometry type is found i.e. {geom_types}",None)
#         elif len(geom_types) > 2:
#             return (f"error occured : more than one geometry type is found i.e. {geom_types}",None)
#         else:
#             return (f"error occured : missing geometry",None)
#         return ("successful",geom_type)
#     except Exception as e:
#         return (f"error occured in validating geometry type : {str(e)}","")

def validate_geometry_type(geodataframe):
    print("validate gemetry type entered")
    try:
        geom_type = None
        geom_types = list(geodataframe.geom_type.unique())
        if None in geom_types: geom_types.remove(None)
        if len(geom_types) == 1:
            geom_type = geom_types[0]
        elif len(geom_types) == 2:
            if "Point" and "MultiPoint" in geom_types:
                geom_type = "MultiPoint"
            elif "LineString" and "MultiLineString" in geom_types:
                geom_type = "MultiLineString"
            elif "Polygon" and "MultiPolygon" in geom_types:
                geom_type = "MultiPolygon"
            else:
                return (f"error occured : more than one geometry type is found i.e. {geom_types}",None)
        elif len(geom_types) > 2:
            return (f"error occured : more than one geometry type is found i.e. {geom_types}",None)
        else:
            return (f"error occured : missing geometry",None)
        print(geom_type, "is geom_type")
        return ("successful",geom_type)
    except Exception as e:
        return (f"error occured in validating geometry type : {str(e)}","")

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
                return "Invalid Coordinate System, only WGS84 (EPSG: 4326) coordinate system will be accepted", None
            else:
                # Layer.objects.filter(id=layer_id).delete()
                return "Unknown Coordinate System", None
        '''validaing geometry type'''
        response,geom_type=validate_geometry_type(geodataframe)
        if not geom_type:
            return (response)

        '''reomve id column if it exists'''
        if 'id' in geodataframe.columns:
            geodataframe.drop('id', inplace=True, axis=1)
            # errors='ignore'
            print('reomve id column completed')

        '''remove z dimension if exists'''
        geodataframe['geometry'] = geodataframe.geometry.apply(lambda x: force_2d(x))
        print('completed z dimension')
        '''set nan values to None'''
        geodataframe = geodataframe.replace(['NaN', 'nan', np.nan], None)
        print('completed removing nan values')

        '''set null geometry properly'''
        if geom_type == 'Point' or geom_type == 'MultiPoint':
            value_to_set = 'POINT EMPTY'
        elif geom_type == 'LineString' or geom_type == 'MultiLineString':
            value_to_set = 'LINESTRING EMPTY'
        elif geom_type == 'Polygon' or geom_type == 'MultiPolygon':
            value_to_set = 'POLYGON EMPTY'
        geodataframe['geometry']=geodataframe['geometry'].fillna(from_wkt(value_to_set))
        print('completed setting empty geometries')

        '''extracting extent'''
        total_bounds = geodataframe.total_bounds
        vector_layer_instance.geom_type = geom_type
        vector_layer_instance.bbox = total_bounds.tolist()
        vector_layer_instance.save()

        response = upload_feature(
            geodataframe, layer_instance, geom_type)
        print('completed upload feature')
        return response
    except Exception as e:
        return ("error occured in handle shapefile: " + str(e))


def handleCSV(layer_id,lat_field,lon_field):
    try:
        layer_instance = Layer.objects.get(id=layer_id)
        vector_layer_instance = Vectorlayer.objects.get(layer=layer_id)
        file_object = LayerFile.objects.get(layer=layer_id)
        my_file = file_object.file.path
        file_path = os.path.dirname(my_file)
        # df = pd.read_csv(my_file, keep_default_na=False)
        # crs = {'init': 'epsg:4326'}

        # geometry = gpd.points_from_xy(df[lon_field], df[lat_field])
        # crs = {'init': 'epsg:4326'}

        '''saving geometry type'''
        geom_type = "Point"


        # geodataframe = gpd.GeoDataFrame(df, crs=crs, geometry=geometry)
        geodataframe = gpd.read_file('Test 5.csv')
        geodataframe = geodataframe.set_crs(4326)

        '''reomve id column if it exists'''
        if 'id' in geodataframe.columns:
            geodataframe.drop('id', inplace=True, axis=1)
            print('reomve id column completed')

        '''replace NaN values with None'''
        geodataframe = geodataframe.replace(['NaN', 'nan', np.nan], None)
        '''replace blank values in lat long fields to ensure empty geometry is created later on'''
        geodataframe[[lon_field, lat_field]]=geodataframe[[lon_field, lat_field]].replace('', None)
        geodataframe['geometry'] = gpd.points_from_xy(geodataframe[lon_field], geodataframe[lat_field])

        '''extracting extent'''
        total_bounds = geodataframe.total_bounds

        '''save geometry_type and bbox'''
        # with transaction.atomic():
        # layer_instance.geom_type = "Point"
        # layer_instance.save()
        vector_layer_instance.geom_type = geom_type
        vector_layer_instance.bbox = total_bounds.tolist()
        vector_layer_instance.save()

        response = upload_feature(
            geodataframe, layer_instance,geom_type)
        return response
    except Exception as e:
        # Layer.objects.filter(id=layer_id).delete()
        return ("error occured : " + str(e))

def handleKML(layer_id):
    try:
        layer_instance = Layer.objects.get(id=layer_id)
        vector_layer_instance = Vectorlayer.objects.get(layer=layer_id)
        file_object = LayerFile.objects.get(layer=layer_id)
        my_file = file_object.file.path
        file_dir = os.path.dirname(my_file)

        '''convert kml to geojson'''
        convert_response=kml2geojson.main.convert(my_file, "/app/pgis_toolkit/media/")
        temp_geojson_file_path="/app/pgis_toolkit/media/geofiles/temp_geojson.geojson"
        with open(temp_geojson_file_path, 'w') as f:
            json.dump(convert_response[0], f, indent=2)

        '''read geojson file'''
        geodataframe = gpd.read_file(temp_geojson_file_path)

        '''coordinate system validation'''
        epsg = geodataframe.crs.to_epsg()
        utm_zone = geodataframe.crs.utm_zone,
        if epsg != 4326:
            if utm_zone:
                # Layer.objects.filter(id=layer_id).delete()
                return "Invalid Coordinate System, only WGS84 coordinate system will be accepted", None
            else:
                # Layer.objects.filter(id=layer_id).delete()
                return "Unknown Coordinate System", None

        # gpd.io.file.fiona.drvsupport.supported_drivers['KML'] = 'raw'
        # geodataframe = gpd.read_file(my_file, driver='KML')

        # df= pd.DataFrame(geo_df)
        # fiona.drvsupport.supported_drivers['KML'] = 'rw' #LIBKML
        # with fiona.open(my_file) as collection:
        #     geodataframe = gpd.GeoDataFrame.from_features(collection)
        # print(geodataframe,"geodf")

        '''validaing geometry type'''
        response,geom_type=validate_geometry_type(geodataframe)
        if not geom_type:
            return (response)

        '''extracting extent'''
        total_bounds = geodataframe.total_bounds

        '''save geometry_type and bbox'''
        # with transaction.atomic():
        vector_layer_instance.geom_type = geom_type
        vector_layer_instance.bbox = total_bounds.tolist()
        vector_layer_instance.save()

        response = upload_feature(
            geodataframe, layer_instance,geom_type)
        return response
    except Exception as e:
        # Layer.objects.filter(id=layer_id).delete()
        return ("error occured : " + str(e))

def handleGPX(layer_id):
    try:
        layer_instance = Layer.objects.get(id=layer_id)
        vector_layer_instance = Vectorlayer.objects.get(layer=layer_id)
        file_object = LayerFile.objects.get(layer=layer_id)
        my_file = file_object.file.path
        file_dir = os.path.dirname(my_file)

        gpd.io.file.fiona.drvsupport.supported_drivers['GPX'] = 'rw'
        geodataframe = gpd.read_file(my_file, driver='GPX',GPX_USE_EXTENSIONS='NO')

        '''coordinate system validation'''
        epsg = geodataframe.crs.to_epsg()
        utm_zone = geodataframe.crs.utm_zone,
        if epsg != 4326:
            if utm_zone:
                # Layer.objects.filter(id=layer_id).delete()
                return "Invalid Coordinate System, only WGS84 coordinate system will be accepted", None
            else:
                # Layer.objects.filter(id=layer_id).delete()
                return "Unknown Coordinate System", None

        '''validaing geometry type'''
        response,geom_type=validate_geometry_type(geodataframe)
        if not geom_type:
            return (response)

        '''extracting extent'''
        total_bounds = geodataframe.total_bounds

        '''save geometry_type and bbox'''
        # with transaction.atomic():
        vector_layer_instance.geom_type = geom_type
        vector_layer_instance.bbox = total_bounds.tolist()
        vector_layer_instance.save()

        response = upload_feature(
            geodataframe, layer_instance,geom_type)
        return response
    except Exception as e:
        # Layer.objects.filter(id=layer_id).delete()
        return ("error occured : " + str(e))


def handleGeoJSON(layer_id):
    try:
        layer_instance = Layer.objects.get(id=layer_id)
        vector_layer_instance = Vectorlayer.objects.get(layer=layer_id)
        file_object = LayerFile.objects.get(layer=layer_id)
        my_file = file_object.file.path
        file_path = os.path.dirname(my_file)
        geodataframe = gpd.read_file(my_file)

        '''coordinate system validation'''
        epsg = geodataframe.crs.to_epsg()
        utm_zone = geodataframe.crs.utm_zone,
        if epsg != 4326:
            if utm_zone:
                # Layer.objects.filter(id=layer_id).delete()
                return "Invalid Coordinate System, only WGS84 coordinate system will be accepted", None
            else:
                # Layer.objects.filter(id=layer_id).delete()
                return "Unknown Coordinate System", None

        '''validaing geometry type'''
        response,geom_type=validate_geometry_type(geodataframe)
        if not geom_type:
            return (response)

        '''reomve id column if it exists'''
        if 'id' in geodataframe.columns:
            geodataframe.drop('id', inplace=True, axis=1)
            print('reomve id column completed')

        '''remove z dimension if exists'''
        geodataframe['geometry'] = geodataframe.geometry.apply(lambda x: force_2d(x))
        print('completed z dimension')
        '''set nan values to None'''
        geodataframe = geodataframe.replace(['NaN', 'nan', np.nan], None)
        print('completed removing nan values')

        '''set null geometry properly'''
        if geom_type == 'Point' or geom_type == 'MultiPoint':
            value_to_set = 'POINT EMPTY'
        elif geom_type == 'LineString' or geom_type == 'MultiLineString':
            value_to_set = 'LINESTRING EMPTY'
        elif geom_type == 'Polygon' or geom_type == 'MultiPolygon':
            value_to_set = 'POLYGON EMPTY'
        geodataframe['geometry']=geodataframe['geometry'].fillna(from_wkt(value_to_set))
        print('completed setting empty geometries')

        '''extracting extent'''
        total_bounds = geodataframe.total_bounds

        '''save geometry_type and bbox'''
        # with transaction.atomic():
        vector_layer_instance.geom_type = geom_type
        vector_layer_instance.bbox = total_bounds.tolist()
        vector_layer_instance.save()

        response = upload_feature(
            geodataframe, layer_instance,geom_type)
        return response
    except Exception as e:
        # Layer.objects.filter(id=layer_id).delete()
        return ("error occured : " + str(e))

def handleShapeFileForDataMerge(layer_file_path):
    try:
        print('entered utils > layer_upload > handleShapeFileForDataMerge function')
        file_path = os.path.dirname(layer_file_path)
        with zipfile.ZipFile(layer_file_path, 'r') as zip_ref:
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
                return "Invalid Coordinate System, only WGS84 coordinate system will be accepted"
            else:
                return "Unknown Coordinate System"
        return geodataframe
    except Exception as e:
        print('Error occured in handleShapeFileForDataMerge. Details: '+ str(e))
        return ('Error: ' + str(e))

def handleGeoJSONForDataMerge(layer_file_path):
    try:
        print('entered utils > layer_upload > handleGeoJSONForDataMerge function')
        file_path = os.path.dirname(layer_file_path)
        geodataframe = gpd.read_file(layer_file_path)
        '''coordinate system validation'''
        epsg = geodataframe.crs.to_epsg()
        utm_zone = geodataframe.crs.utm_zone,
        if epsg != 4326:
            if utm_zone:
                Layer.objects.filter(id=layer_id).delete()
                return "Invalid Coordinate System, only WGS84 coordinate system will be accepted"
            else:
                return "Unknown Coordinate System"
        return response
    except Exception as e:
        print('Error occured in handleGeoJSONForDataMerge. Details: '+ str(e))
        return ("error occured : " + str(e))
