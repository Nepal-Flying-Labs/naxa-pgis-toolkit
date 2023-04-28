import os

os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos import Point as GeosPoint
from django.db import connection
from shapely.geometry import Point
from sqlalchemy import create_engine

from config.settings.base import env
from pgis_toolkit.maps.models import Analysis, ProximityAnalysis, ProximityAreas

db_connection_url = env("CONNECTION_DB", default="postgresql://xIDokAfQUYOjTGhErprxMHnjZTJXMloY:gn63GjyG9AOKLYgrvOcOZFrAeYgjLOA4IkjuTXzISZ3nnMaHxTX1rSxI0fdBSb52@postgres:5432/pgis_toolkit")
con = create_engine(db_connection_url)

def dissolve_data(data):
    """Disolve overlapping geometires

    Parameters
    ----------
    data : GeoDataFrame
        The data to dissolve

    Returns
    -------
    df : GeoDataFrame
        The dissolved geodataframe
    """
    auto_inter = gpd.overlay(data, data, how='union')
    data = auto_inter.unary_union
    df = gpd.GeoDataFrame(crs='epsg:3857', geometry=[data]).explode()
    return df

# def proximity_by_distance(data, distance: float, dissolve: bool) -> dict:
#     """Buffer geometries for provided distance and dissolve overlapping geometries after proximity

#     Parameters
#     ----------
#     data : GeoDataFrame
#         The data to proximity
#     distance : float
#         The proximity distance
#     dissolve : bool
#         If to dissolved overlapping geometries after proximity

#     Returns
#     -------
#     data : GeoDataFrame
#         The dissolved geodataframe
#     """
#     distance = 10 if distance is None else distance
#     dissolve = False if dissolve is None else dissolve
#     gdf = data.to_crs("epsg:3857")
#     data = gdf.proximity(float(distance))
#     data = gpd.GeoDataFrame(crs='epsg:3857', geometry=data, columns=gdf.columns.values)
#     if dissolve:
#         data = dissolve_data(data)
#     data = data.to_crs("epsg:4326")
#     return data

# def proximity_by_column_value(data, column: str, ratio: float, dissolve: bool) -> dict:
#     """Buffer geometries for provided distance and dissolve overlapping geometries after proximity

#     Parameters
#     ----------
#     data : GeoDataFrame
#         The data to proximity
#     column: str
#         Column name which will be used for proximity value
#     ratio : float
#         Factor to multiply the column value
#     dissolve : bool
#         If to dissolved overlapping geometries after proximity

#     Returns
#     -------
#     data : GeoDataFrame
#         The dissolved geodataframe
#     """
#     ratio = 1 if ratio is None else ratio
#     dissolve = False if dissolve is None else dissolve
#     data = data.to_crs("epsg:3857")
#     df = gpd.GeoDataFrame(geometry=[])
#     for index, row in data.iterrows():
#         proximity_value = row[column] * ratio
#         proximity = row['geometry'].proximity(proximity_value)
#         df = df.append(gpd.GeoDataFrame(geometry=[proximity]))
#     if dissolve:
#         df = dissolve_data(df)
#     df = df.to_crs("epsg:4326")
#     return df

# def find_data_within_proximity(data, distance: float, layers: list) -> dict:
#     """Buffer geometries for provided distance and dissolve overlapping geometries after proximity

#     Parameters
#     ----------
#     data : GeoDataFrame
#         The data to proximity
#     distance : float
#         The proximity distance
#     layers : list
#         layer list to find data of

#     Returns
#     -------
#     data : GeoDataFrame
#         The dissolved geodataframe
#     """
#     proximityed_data = proximity_by_distance(data, distance, False)
#     datas = []
#     for layer in layers:
#         df = gpd.sjoin(proximityed_data, layer, op="within")
#         datas.append(df)
#     return datas

def proximity_analysis(origins, radius, dissolve_output, analysis_id, proximity_id, pois, first_analysis):
    try:
        points = []
        for origin in origins:
            point = Point(origin[0], origin[1])
            points.append(point)
        gdf = gpd.GeoDataFrame(geometry=points, crs=4326)
        gdf = gdf.to_crs("epsg:3857")
        data = gdf.buffer(float(radius))
        data = gpd.GeoDataFrame(crs='epsg:3857', geometry=data, columns=gdf.columns.values)
        if dissolve_output:
            data = dissolve_data(data)
        area = data.iloc[0].geometry.area
        data = data.to_crs("epsg:4326")
        proximity_objs = []
        for i, row in data.iterrows():
            result_dict = {'geometry': row.geometry.wkt, 'area': area, 'bbox': list(row.geometry.bounds), 'analysis_id': analysis_id,'proximity_analysis_id':proximity_id}
            proximity_objs.append(ProximityAreas(**result_dict))
        proximity_areas_list = ProximityAreas.active.bulk_create(proximity_objs)
        iterate = True
        while iterate:
            if ProximityAreas.active.filter(proximity_analysis_id=proximity_id).exists():
                iterate=False
        # if pois:
        try:
            geos_origins = []
            for origin in origins:
                geos_origins.append(GeosPoint(origin[0], origin[1]))
            for proximity_area in proximity_areas_list:
                proximity_area_id = proximity_area.id
                pois_dict = {}
                for poi in pois:
                    pois_sql = f'''
                    SELECT mirror.id
                    FROM (SELECT id, geometry FROM maps_proximityAreas WHERE id={proximity_area_id}) proximity
                    JOIN (SELECT id, geometry FROM maps_featurecollectionmirror WHERE layer_id={poi} and is_deleted=false) mirror
                    ON ST_Contains(proximity.geometry, mirror.geometry);
                    '''
                    # mirror = gpd.read_postgis(pois_sql, con=con, geom_col='geometry', crs="epsg:4326")
                    mirror= pd.read_sql_query(pois_sql, con)
                    pois_dict[poi] = list(mirror['id'])
                proximity_area.pois = pois_dict
                origin_list = []
                for i, point in enumerate(geos_origins):
                    if point.within(proximity_area.geometry):
                        origin_list.append(origins[i])
                ''''''
                # origin_list =[]
                # for id , origin in enumerate(origins):
                #     origin_list.append((id, f'POINT({origin[0]} {origin[1]})'))
                # origin_tuple = tuple(origin_list)
                # print(origin_tuple, "is origin tuple")
                # origin_sql = f'''
                # WITH  origin_table (id, point) AS (VALUES {origin_tuple})
                # SELECT origins.id
                # FROM (SELECT id, geometry FROM maps_proximityAreas WHERE id={proximity_area_id}) proximity
                # JOIN (SELECT id, ST_PointFromText(point::text, 4326) AS geometry FROM origin_table) origins
                # ON ST_Contains(proximity.geometry, origins.geometry);
                # '''
                # print(origin_sql, "is origin sql")
                # with connection.cursor() as cursor:
                #     cursor.execute(origin_sql)
                #     result = cursor.fetchall()
                #     print(result, "is result")
                # origin_df= pd.read_sql_query(origin_sql, con)
                # origin_ids = list(origin_df['id'])
                # final_origin_list = []
                # for id in origin_ids:
                #     print(id, origins[i], "is id and origin point")
                #     final_origin_list.append(origins[i])
                # proximity_area.origin = final_origin_list
                ''''''
                proximity_area.origin = origin_list
                proximity_area.save()
        except Exception as e:
            print('eror in checking pois within proximity zones:', str(e))
            pass
        # analysis_inst = Analysis.active.get(id=analysis_id)
        # analysis_inst.bbox = list(data.total_bounds)
        # analysis_inst.save()
        proximity_inst = ProximityAnalysis.active.get(id=proximity_id)
        proximity_inst.bbox = list(data.total_bounds)
        proximity_inst.total_area = area * len(origins)
        proximity_inst.save()
        return analysis_id, proximity_id, "success", "", 200
    except Exception as e:
        if first_analysis and Analysis.objects.filter(id=analysis_id).exists():
            Analysis.objects.get(id=analysis_id).delete()
        if ProximityAnalysis.objects.filter(id=proximity_id).exists():
            ProximityAnalysis.objects.get(id=proximity_id).delete()
        return None, None, "error", str(e), 400

# def proximity_data(analysis_id, layer_ids):
#     try:
#         sql = f'''SELECT id, geometry FROM maps_proximityAreas WHERE analysis_id={analysis_id}'''
#         gdf = gpd.read_postgis(sql, con=con, geom_col='geometry', crs=4326)
#         print(gdf)
#         return analysis_id, "success", "", 200
#     except Exception as e:
#         return None, "error", str(e), 400
