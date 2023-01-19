import collections

import geopandas as gpd
from rest_framework.response import Response
import momepy
import networkx as nx
from config.settings.base import env
from sqlalchemy import create_engine
import pandas as pd
from geopandas import GeoDataFrame
from shapely import ops
from shapely.geometry import MultiLineString, MultiPoint, Point

from pgis_toolkit.maps.models import FeatureCollectionMirror, CleaningErrors

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
    data = get_all_layer(layer)
    total_data = len(data)
    null_rows = []
    for i, row in data.iterrows():
        if row.geom.is_empty:
            null_rows.append(row['id'])
    CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"null": null_rows})
    content = {"error_data": len(null_rows), "total_data": total_data}
    return content

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
        if row.geom.type.startswith("Multi"):
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
    sql = f'''SELECT a.* From
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

def check_snapping(layer):
    """Check for isolated points

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
    isolated = list( g for cc in components for g in cc )
    points = [Point(xy) for xy in isolated]
    gdf = gpd.GeoDataFrame(crs=4326, geometry=points)
    try:
        gdf.to_postgis(con=con, name="snap_points", if_exists='replace', schema='public')
        s = f'''SELECT DISTINCT a.* from (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
            INNER JOIN snap_points b ON
            (a.geometry && b.geometry AND ST_Contains(a.geometry, b.geometry));'''
        f_data = gpd.read_postgis(s, con, geom_col="geometry")
        con.execute('''DROP TABLE IF EXISTS snap_points;''')
        CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"snapping": list(f_data['id'])})
        content = {"error_data": len(f_data), "total_data": total_data}
        return content
    except Exception as e:
        return {"message": str(e)}

#===================
# Cleaning data
#===================
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
        content = check_null(layer)
        return {"new_error": content["error_data"], "prev_error": len(nulls)}
    except Exception as e:
        return {'message': str(e)}

def fix_multipart(layer):
    try:
        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer)
        if cleaning_error_qs.exists():
            multipart_error = cleaning_error_qs.values('multipart')[0]
            multiparts = multipart_error["multipart"]
            if len(multiparts) > 0:
                data = get_layers(multiparts)
                # df = gpd.GeoDataFrame(crs='epsg:4326', geometry=[], columns=data.columns.values)
                # for i, row in data.iterrows():
                #     data = ops.linemerge(row.geometry)
                #     data = gpd.GeoDataFrame(crs='epsg:4326', geometry=[data])
                #     data = data.explode(index_parts=True)
                #     for value in row.keys():
                #         if value != 'geometry':
                #             data.at[i,value] = row[value]
                #     df = pd.concat([df, data])
                # print(df)
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
                # df = gpd.GeoDataFrame(crs='epsg:4326', geometry=[], columns=data.columns.values)
                # for i, row in data.iterrows():
                #     mls = ops.unary_union(row.geometry)
                #     if isinstance(mls, MultiLineString):
                #         coords_list = []
                #         for part in mls.geoms:
                #             coords_list.extend(part.coords)
                #         points = [item for item, count in collections.Counter(coords_list).items() if count > 1]

                #         multi_point = MultiPoint(points)
                #         result = ops.split(row.geometry, multi_point)
                #         for geom in result.geoms:
                #             if geom.length > convert_distance_to_4326(10):
                #                 df = pd.concat([df, gpd.GeoDataFrame(geometry=[geom])], ignore_index=True)
                #     else:
                #         df = pd.concat([df, gpd.GeoDataFrame(geometry=[row.geometry])], ignore_index=True)
        content = check_self_intersection(layer)
        return {"new_error": content["error_data"], "prev_error": len(self_intersect_error["self_instersect"])}
    except Exception as e:
        return {'message': str(e)}

def fix_snapping(layer):
    try:
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
        isolated = list( g for cc in components for g in cc )
        if len(isolated) > 0:
            points = [Point(xy) for xy in isolated]
            gdf = gpd.GeoDataFrame(crs=4326, geometry=points)
            gdf.to_postgis(con=con, name="snap_points", if_exists='replace', schema='public')
            iso = f'''SELECT DISTINCT a.* from (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
                INNER JOIN snap_points b ON
                (a.geometry && b.geometry AND ST_Contains(a.geometry, b.geometry));'''
            isolated_feature = gpd.read_postgis(iso, con, geom_col="geometry")
            l_points = [Point(xy) for xy in list(largest)]
            gdf = gpd.GeoDataFrame(crs=4326, geometry=l_points)
            gdf.to_postgis(con=con, name="snap_points", if_exists='replace', schema='public')
            iso = f'''SELECT DISTINCT a.* from (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={layer}) a
                INNER JOIN snap_points b ON
                (a.geometry && b.geometry AND ST_Contains(a.geometry, b.geometry));'''
            largest_feature = gpd.read_postgis(iso, con, geom_col="geometry")
            find_sql = f'''WITH buffered_network AS (SELECT ST_Buffer(b.st_union, 0.000449) FROM (SELECT ST_Union(a.geometry) FROM (
                        SELECT * FROM maps_featurecollectionmirror
                        WHERE id in {tuple(largest_feature['id'])} ) a) b), 
                        isolated_network AS (SELECT * FROM maps_featurecollectionmirror WHERE id in {tuple(isolated_feature['id'])})
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
        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer)
        if cleaning_error_qs.exists():
            snapping_error = cleaning_error_qs.values('snapping')[0]
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
