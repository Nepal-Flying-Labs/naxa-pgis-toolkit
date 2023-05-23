import collections
import os

os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
import momepy
import networkx as nx
import pandas as pd
from geopandas import GeoDataFrame
from rest_framework.response import Response
from shapely import ops
from shapely.geometry import MultiLineString, MultiPoint, Point
from sqlalchemy import create_engine

from celery import Celery, shared_task

from config.settings.base import env
from pgis_toolkit.maps.models import CleaningErrors, FeatureCollectionMirror, CleaningCheckLogs

db_connection_url = env("CONNECTION_DB", default="postgresql://xIDokAfQUYOjTGhErprxMHnjZTJXMloY:gn63GjyG9AOKLYgrvOcOZFrAeYgjLOA4IkjuTXzISZ3nnMaHxTX1rSxI0fdBSb52@postgres:5432/pgis_toolkit")
con = create_engine(db_connection_url)

def get_all_layer(layer):
    sql = f"SELECT id, geometry AS geom, attributes FROM maps_featurecollectionmirror WHERE layer_id={layer} and is_deleted=false"
    data = gpd.read_postgis(sql, con)
    return data

def get_layers(ids):
    count = len(ids)
    if count == 0:
        return Response (data={'features_count': 0}, status=200)
    if count == 1:
        feature_ids = ids[0]
        raw_query=f"SELECT * FROM maps_featurecollectionmirror WHERE id = {feature_ids} and is_deleted=false"
    else:
        feature_ids = tuple(ids)
        raw_query=f"SELECT * FROM maps_featurecollectionmirror WHERE id IN {feature_ids} and is_deleted=false"
    data = gpd.read_postgis(raw_query, con, geom_col='geometry')
    return data


#===================
# Checking data
#===================
@shared_task(max_retries=1, soft_time_limit=8000)
def check_null(layer):
    """Check if the geometry is null or not

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    content: dict
        message: str
            The message to display
        data : GeoDataFrame
    """
    try:
        data = get_all_layer(layer)
        total_data = len(data)
        null_rows = []
        for i, row in data.iterrows():
            if row.geom.is_empty:
                null_rows.append(row['id'])
        clean_error_inst, created = CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"null": null_rows})
        if created:
            clean_error_inst.null = null_rows
            clean_error_inst.save(update_fields=['null'])
        content = {"error_data": len(null_rows), "total_data": total_data}
        clean_logs_inst, logs_created = CleaningCheckLogs.objects.update_or_create(layer_id=layer, defaults={"null": content})
        if logs_created:
            clean_logs_inst.null = content
            clean_logs_inst.save(update_fields=['null'])
        return content,200
    except Exception as e:
        return {"message": str(e)}, 400

def check_multipart(layer):
    """Check if the data is multipart or not

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    content: dict
        message: str
            The message to display
        data : GeoDataFrame
    """
    data = get_all_layer(layer)
    total_data = len(data)
    multipart_rows = []
    for i, row in data.iterrows():
        if row.geom.geom_type.startswith("Multi"):
            multipart_rows.append(row['id'])
        else:
            data.at[i,'is_multipart'] = False
    CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"multipart": multipart_rows})
    content = {"error_data": len(multipart_rows), "total_data": total_data}
    return content

def check_duplicate(layer):
    """Check if the geometry is duplicate or not

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    content: dict
        message: str
            The message to display
        data : GeoDataFrame
    """
    data = get_all_layer(layer)
    total_data = len(data)
    data = data.drop(axis=1, columns=["attributes"])
    sum = data.duplicated().sum()
    gdf = data.loc[data.duplicated(), :]
    CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"duplicate": list(gdf['id'])})
    content = {"error_data": sum, "total_data": total_data}
    return content

def check_overlapping(layer):
    """Check if the geometry has overlapping geometries

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    content: dict
        message: str
            The message to display
        data : GeoDataFrame
    """
    gdf = get_all_layer(layer)
    total_data = len(gdf)
    sql = f'''SELECT DISTINCT a.* From
            (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
            INNER JOIN (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) b ON
            (a.geometry && b.geometry AND ST_Overlaps(a.geometry, b.geometry))
            WHERE a.id != b.id'''
    try:
        data = gpd.read_postgis(sql, con, geom_col="geometry")
        error_data = len(data)
        CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"overlap": list(data['id'])})
        content = {"error_data": error_data, "total_data": total_data}
        return content
    except:
        return {"message": "Query failed"}

def check_self_intersection(layer):
    """Check if the geometry has self intersection or not

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    content: dict
        message: str
            The message to display
        data : GeoDataFrame
    """
    data = get_all_layer(layer)
    total_data = len(data)
    self_intersection_rows = []
    for i, row in data.iterrows():
        if not row['geom'].is_simple:
            self_intersection_rows.append(row['id'])
    CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"self_instersect": self_intersection_rows})
    content = {"error_data": len(self_intersection_rows), "total_data": total_data}
    return content

# def check_snapping(layer):
#     """Check for isolated points

#     Parameters
#     ----------
#     data : GeoDataFrame
#         The data to check

#     Returns
#     -------
#     content: dict
#         message: str
#             The message to display
#         data : GeoDataFrame
#     """
#     gdf = get_all_layer(layer)
#     total_data = len(gdf)
#     sql = f'''WITH segments AS (
#         SELECT id as id, (
#         ST_MakeLine(lag((pt).geom, 1, NULL) OVER (PARTITION BY id ORDER BY id, (pt).path), (pt).geom)) AS geometry
#         FROM (SELECT id, ST_DumpPoints(geometry) AS pt FROM maps_featurecollectionmirror WHERE layer_id={layer}) as dumps
#         )
#         SELECT * FROM segments WHERE geometry IS NOT NULL;'''
#     data = gpd.read_postgis(sql, con, geom_col="geometry")
#     graph = momepy.gdf_to_nx(data, approach='primal')
#     components = list(nx.connected_components(graph))
#     components.sort(key=len, reverse=True)
#     largest = components.pop(0)
#     isolated = list( g for cc in components for g in cc )
#     points = [Point(xy) for xy in isolated]
#     gdf = gpd.GeoDataFrame(crs=4326, geometry=points)
#     try:
#         gdf.to_postgis(con=con, name="snap_points", if_exists='replace', schema='public')
#         s = f'''SELECT DISTINCT a.* from (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
#             INNER JOIN snap_points b ON
#             (a.geometry && b.geometry AND ST_Contains(a.geometry, b.geometry));'''
#         f_data = gpd.read_postgis(s, con, geom_col="geometry")
#         con.execute('''DROP TABLE IF EXISTS snap_points;''')
#         CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"snapping": list(f_data['id'])})
#         content = {"error_data": len(f_data), "total_data": total_data}
#         return content
#     except Exception as e:
#         return {"message": str(e)}

def check_snapping(layer):
    """Check for isolated points

    Parameters
    ----------
    layer : The layer to check for isolated road features

    Returns
    -------
    content: dict
        message: str
            The message to display
        data : GeoDataFrame
    """
    from django.db import connection
    sql = f"""
            WITH connected_counts AS (
                SELECT a.id, a.geometry,
                    COUNT(b.id) AS connected_count,
                    ARRAY_AGG(b.id) AS connected_ids
                FROM maps_featurecollectionmirror a
                LEFT JOIN maps_featurecollectionmirror b ON
                    a.layer_id = b.layer_id AND b.is_deleted=False AND a.id <= b.id AND (
                        ST_Intersects(a.geometry, b.geometry)
                        OR ST_StartPoint(a.geometry) = ST_EndPoint(b.geometry)
                        OR ST_EndPoint(a.geometry) = ST_StartPoint(b.geometry)
                        OR ST_Contains(a.geometry, ST_StartPoint(b.geometry))
                        OR ST_Contains(a.geometry, ST_EndPoint(b.geometry))
                        OR ST_Contains(b.geometry, ST_StartPoint(a.geometry))
                        OR ST_Contains(b.geometry, ST_EndPoint(a.geometry))
                    )
                WHERE a.layer_id = {layer} AND a.is_deleted = False
                GROUP BY a.id, a.geometry
            ), connected_ids_first AS (
                SELECT connected_ids
                FROM connected_counts
                ORDER BY connected_count DESC
                LIMIT 1
            )
            SELECT id
            FROM maps_featurecollectionmirror
            WHERE layer_id={layer} AND is_deleted=False AND id NOT IN
                (SELECT unnest(connected_ids) AS connected_ids
                FROM connected_ids_first);
            """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
        if result:
            isolated_ids = []
            for res in result:
                isolated_ids.append(res[0])
            CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"snapping": isolated_ids})
            content = {"error_data": len(isolated_ids), "total_data": FeatureCollectionMirror.active.filter(layer=layer).count()}
        else:
            content = {"error_data": 0, "total_data": FeatureCollectionMirror.active.filter(layer=layer).count()}
        return content
    except Exception as e:
        print('Isolated geometries check failed. Details:', str(e))
        return Response(data={'message': 'Isolated geometries check failed. Please try again.'}, status=400)

#===================
# Cleaning data
#===================
@shared_task(max_retries=1, soft_time_limit=8000)
def fix_null(layer):
    try:
        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer)
        if cleaning_error_qs.exists():
            null_error = cleaning_error_qs.values('null')[0]
            nulls = null_error['null']
            count = len(nulls)
            if count == 1:
                feature = nulls[0]
                db = con.connect()
                db.execute(f"UPDATE maps_featurecollectionmirror SET is_deleted=true WHERE id={feature}")
            elif count > 1:
                features = tuple(nulls)
                db = con.connect()
                db.execute(f"UPDATE maps_featurecollectionmirror SET is_deleted=true WHERE id IN {features}")
        content, status = check_null(layer)
        if status == 200:
            return {"new_error": content["error_data"], "prev_error": len(nulls)}, status
        else:
            return content, 400
    except Exception as e:
        return {"message": str(e)}, 400

def fix_multipart(layer):
    try:
        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer)
        if cleaning_error_qs.exists():
            multipart_error = cleaning_error_qs.values('multipart')[0]
            multiparts = multipart_error["multipart"]
            if len(multiparts) > 0:
                data = get_layers(multiparts)
                db = con.connect()
                for i, row in data.iterrows():
                    try:
                        sql = f'''UPDATE maps_featurecollectionmirror
                                SET geometry = (SELECT ST_LineMerge(geometry) FROM maps_featurecollectionmirror WHERE id={row.id})
                                WHERE id={row.id};'''
                        db.execute(sql)
                    except:
                        pass
                get_multi = f'''SELECT * FROM (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
                                WHERE ST_GeometryType(geometry) IN ('ST_MultiPoint', 'ST_MultiLineString', 'ST_MultiPolygon', 'ST_GeometryCollection')'''
                multis = gpd.read_postgis(get_multi, con=con, geom_col='geometry', crs=4326)
                if len(multis) > 0:
                    for i, row in multis.iterrows():
                        try:
                            sql = f'''WITH individual_geoms AS (
                                            SELECT id, (ST_Dump(geometry)).geom as geom
                                            FROM (SELECT * FROM maps_featurecollectionmirror WHERE id={row.id})
                                        )
                                        UPDATE maps_featurecollectionmirror
                                        SET geometry = (SELECT geom FROM individual_geoms WHERE id={row.id})
                                        WHERE id={row.id};'''
                            db.execute(sql)
                        except:
                            pass
                left_multies = gpd.read_postgis(get_multi, con=con, geom_col='geometry', crs=4326)
                if len(left_multies) > 0:
                    for i, row in left_multies.iterrows():
                        try:
                            sql = f'''SELECT a.*, (ST_Dump(a.geometry)).geom as geom
                                        FROM (SELECT * FROM maps_featurecollectionmirror WHERE id={row.id}) a'''
                            sql_result = gpd.read_postgis(sql, con=con, geom_col='geom', crs=4326)
                            sql_result.drop(['synced', 'geometry', 'uploaded_date', 'last_updated'], axis=1, inplace=True)
                            if len(sql_result) == 1:
                                FeatureCollectionMirror.active.update_or_create(id=row.id, defaults={'geometry': sql_result.loc[0,'geom'].wkt, 'synced': False})
                            else:
                                for i, s_row in sql_result.iterrows():
                                    if i == 0:
                                        FeatureCollectionMirror.active.update_or_create(id=row.id, defaults={'geometry': s_row.geom.wkt, 'synced': False})
                                    else:
                                        s_row.pop('id')
                                        s_row.pop('feature_id')
                                        obj_dict = {}
                                        for key, value in s_row.items():
                                            if key == 'geom':
                                                obj_dict['geometry'] = value.wkt
                                            else:
                                                obj_dict[key] = value
                                        FeatureCollectionMirror.objects.create(**obj_dict)
                        except:
                            pass
        content = check_multipart(layer)
        return {"new_error": content["error_data"], "prev_error": len(multiparts)}
    except Exception as e:
        return {'message': str(e)}

def fix_duplicate(layer):
    try:
        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer)
        if cleaning_error_qs.exists():
            duplicate_error = cleaning_error_qs.values('duplicate')[0]
            duplicates = duplicate_error['duplicate']
            count = len(duplicates)
            if count == 1:
                feature = duplicates[0]
                db = con.connect()
                db.execute(f"UPDATE maps_featurecollectionmirror SET is_deleted=true WHERE id={feature}")
            elif count > 1:
                features = tuple(duplicates)
                db = con.connect()
                db.execute(f"UPDATE maps_featurecollectionmirror SET is_deleted=true WHERE id IN {features}")
        content = check_duplicate(layer)
        return {"new_error": content["error_data"], "prev_error": len(duplicates)}
    except Exception as e:
        return {'message': str(e)}

def fix_overlapping(layer):
    try:
        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer)
        if cleaning_error_qs.exists():
            overlap_error = cleaning_error_qs.values('overlap')[0]
            overlaps = overlap_error["overlap"]
            if len(overlaps) > 0:
                data = get_layers(overlaps)
                try:
                    for i, row in data.iterrows():
                        sql = f'''SELECT * FROM (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
                                WHERE EXISTS (SELECT 1 FROM (SELECT * FROM maps_featurecollectionmirror WHERE id={row.id}) b
                                WHERE a.id != b.id AND ST_Overlaps(a.geometry, b.geometry) = true)'''
                        result = gpd.read_postgis(sql, con=con, geom_col='geometry', crs=4326)
                        for i, o_row in result.iterrows():
                            try:
                                over_sql = f'''WITH overlapping_lines AS (
                                                SELECT ST_Intersection(a.geometry, b.geometry) AS overlap
                                                FROM (SELECT * FROM maps_featurecollectionmirror WHERE id = {row.id}) a, (SELECT * FROM maps_featurecollectionmirror WHERE id = {o_row.id}) b
                                                WHERE a.id != b.id AND ST_Overlaps(a.geometry, b.geometry) = true
                                            )
                                            UPDATE maps_featurecollectionmirror
                                            SET geometry = (SELECT ST_Difference(a.geometry, (SELECT overlap FROM overlapping_lines))
                                            FROM maps_featurecollectionmirror a
                                            WHERE a.id = {o_row.id}) WHERE id={o_row.id}'''
                                db = con.connect()
                                db.execute(over_sql)
                            except:
                                pass
                        get_multi = f'''SELECT * FROM (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
                                WHERE ST_GeometryType(geometry) IN ('ST_MultiPoint', 'ST_MultiLineString', 'ST_MultiPolygon', 'ST_GeometryCollection')'''
                        left_multies = gpd.read_postgis(get_multi, con=con, geom_col='geometry', crs=4326)
                        if len(left_multies) > 0:
                            for i, row in left_multies.iterrows():
                                try:
                                    sql = f'''SELECT a.*, (ST_Dump(a.geometry)).geom as geom
                                                FROM (SELECT * FROM maps_featurecollectionmirror WHERE id={row.id}) a'''
                                    sql_result = gpd.read_postgis(sql, con=con, geom_col='geom', crs=4326)
                                    sql_result.drop(['synced', 'geometry', 'uploaded_date', 'last_updated'], axis=1, inplace=True)
                                    if len(sql_result) == 1:
                                        FeatureCollectionMirror.active.update_or_create(id=row.id, defaults={'geometry': sql_result.loc[0,'geom'].wkt, 'synced': False})
                                    else:
                                        for i, s_row in sql_result.iterrows():
                                            if i == 0:
                                                FeatureCollectionMirror.active.update_or_create(id=row.id, defaults={'geometry': s_row.geom.wkt, 'synced': False})
                                            else:
                                                s_row.pop('id')
                                                s_row.pop('feature_id')
                                                obj_dict = {}
                                                for key, value in s_row.items():
                                                    if key == 'geom':
                                                        obj_dict['geometry'] = value.wkt
                                                    else:
                                                        obj_dict[key] = value
                                                FeatureCollectionMirror.objects.create(**obj_dict)
                                except:
                                    pass
                except:
                    pass
        content = check_overlapping(layer)
        return {"new_error": content["error_data"], "prev_error": len(overlaps)}
    except Exception as e:
        return {'message': str(e)}

def convert_distance_to_4326(distance: float) -> float:
    """Convert the distance to WGS 1984 (epsg: 4326)

    Parameters
    ----------
    distance : float

    Returns
    -------
    float
    """
    return (0.001/111.12)*float(distance)

def fix_self_intersection(layer):
    try:
        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer)
        if cleaning_error_qs.exists():
            self_intersect_error = cleaning_error_qs.values('self_instersect')[0]
            self_intersect_errors = self_intersect_error["self_instersect"]
            if len(self_intersect_errors) > 0:
                data = get_layers(self_intersect_errors)
                try:
                    for i, row in data.iterrows():
                        sql = f'''SELECT a.*, (ST_Dump(ST_Node(a.geometry))).geom
                                    FROM (SELECT * FROM maps_featurecollectionmirror WHERE id={row.id}) a'''
                        sql_result = gpd.read_postgis(sql, con=con, geom_col='geom', crs=4326)
                        sql_result.drop(['synced', 'geometry', 'uploaded_date', 'last_updated'], axis=1, inplace=True)
                        if len(sql_result) == 1:
                            FeatureCollectionMirror.active.update_or_create(id=row.id, defaults={'geometry': sql_result.loc[0,'geom'].wkt, 'synced': False})
                        else:
                            for i, s_row in sql_result.iterrows():
                                if i == 0:
                                    FeatureCollectionMirror.active.update_or_create(id=row.id, defaults={'geometry': s_row.geom.wkt, 'synced': False})
                                else:
                                    s_row.pop('id')
                                    s_row.pop('feature_id')
                                    obj_dict = {}
                                    for key, value in s_row.items():
                                        if key == 'geom':
                                            obj_dict['geometry'] = value.wkt
                                        else:
                                            obj_dict[key] = value
                                    FeatureCollectionMirror.objects.create(**obj_dict)
                except:
                    pass
        content = check_self_intersection(layer)
        return {"new_error": content["error_data"], "prev_error": len(self_intersect_error["self_instersect"])}
    except Exception as e:
        return {'message': str(e)}

def fix_snapping(layer):
    try:
        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer)
        if cleaning_error_qs.exists():
            snapping_error = cleaning_error_qs.values('snapping')[0]
            isolated = snapping_error["snapping"]
            if len(isolated) > 0:
                sql = f'''WITH segments AS (
                SELECT id as id, (
                ST_MakeLine(lag((pt).geom, 1, NULL) OVER (PARTITION BY id ORDER BY id, (pt).path), (pt).geom)) AS geometry
                FROM (SELECT id, ST_DumpPoints(geometry) AS pt FROM maps_featurecollectionmirror WHERE layer_id={layer}) as dumps
                )
                SELECT * FROM segments WHERE geometry IS NOT NULL;'''
                data = gpd.read_postgis(sql, con, geom_col="geometry")
                graph = momepy.gdf_to_nx(data, approach='primal')
                components = list(nx.connected_components(graph))
                components.sort(key=len, reverse=True)
                largest = components.pop(0)
                l_points = [Point(xy) for xy in list(largest)]
                gdf = gpd.GeoDataFrame(crs=4326, geometry=l_points)
                gdf.to_postgis(con=con, name="snap_points", if_exists='replace', schema='public')
                iso = f'''SELECT DISTINCT a.* from (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
                    INNER JOIN snap_points b ON
                    (a.geometry && b.geometry AND ST_Contains(a.geometry, b.geometry));'''
                largest_feature = gpd.read_postgis(iso, con, geom_col="geometry")
                find_sql = f'''WITH buffered_network AS (SELECT ST_Buffer(b.st_union, 0.0000449) FROM (SELECT ST_Union(a.geometry) FROM (
                            SELECT * FROM maps_featurecollectionmirror
                            WHERE id in {tuple(largest_feature['id'])} ) a) b),
                            isolated_network AS (SELECT * FROM maps_featurecollectionmirror WHERE id in {tuple(isolated)})
                            SELECT * FROM isolated_network WHERE ST_Within(isolated_network.geometry, (SELECT st_buffer FROM buffered_network));'''
                selected_isolates = gpd.read_postgis(find_sql, con=con, geom_col='geometry', crs=4326)
                if len(selected_isolates) > 0:
                    for i, row in selected_isolates.iterrows():
                        update_sql = f'''UPDATE maps_featurecollectionmirror
                                SET geometry = ST_Union((SELECT ST_MakeLine(ST_ClosestPoint((SELECT ST_Union(a.geometry) FROM (
                                    SELECT * FROM maps_featurecollectionmirror
                                    WHERE id in {tuple(largest_feature['id'])}
                                ) a), (SELECT geometry from maps_featurecollectionmirror where id={row.id})), ST_EndPoint((SELECT geometry from maps_featurecollectionmirror where id={row.id})))), (SELECT geometry from maps_featurecollectionmirror where id={row.id}))
                                WHERE id = {row.id};'''
                        db = con.connect()
                        db.execute(update_sql)
        content = check_snapping(layer)
        return {"new_error": content["error_data"], "prev_error": len(snapping_error["snapping"])}
    except Exception as e:
        return {'message': str(e)}

'''used to remove id from clean instance'''
def del_id_from_clean_instance(instance, pk):
    '''update null'''
    null_list = instance.null
    if pk in null_list:
        null_list.remove(pk)
    '''update multipart'''
    multipart_list = instance.multipart
    if pk in multipart_list:
        multipart_list.remove(pk)
    '''update duplicate'''
    duplicate_list = instance.duplicate
    if pk in duplicate_list:
        duplicate_list.remove(pk)
    '''update overlap'''
    overlap_list = instance.overlap
    if pk in overlap_list:
        overlap_list.remove(pk)
    '''update self_instersect'''
    self_instersect_list = instance.self_instersect
    if pk in self_instersect_list:
        self_instersect_list.remove(pk)
    '''update snapping'''
    snapping_list = instance.snapping
    if pk in snapping_list:
        snapping_list.remove(pk)
