import geopandas as gpd
from geopandas import GeoDataFrame
import pandas as pd
import networkx as nx
from shapely import ops
from shapely.geometry import MultiLineString, MultiPoint, Point
import collections
import momepy
from pgis_toolkit.maps.models import CleaningErrors

#===================
# Checking data
#===================
def check_null(data: GeoDataFrame, layer) -> dict:
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
    total_data = len(data)
    null_rows = []
    for i, row in data.iterrows():
        if row.geom.is_empty:
            null_rows.append(row['id'])
    CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"null": null_rows})
    content = {"error_data": len(null_rows), "total_data": total_data}
    return content

def check_multipart(data: GeoDataFrame, layer) -> dict:
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

def check_duplicate(data: GeoDataFrame, layer) -> dict:
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
    total_data = len(data)
    data = data.drop(axis=1, columns=["attributes"])
    sum = data.duplicated().sum()
    gdf = data.loc[data.duplicated(), :]
    CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"duplicate": list(gdf['id'])})
    content = {"error_data": sum, "total_data": total_data}
    return content

def check_overlapping(layer, con) -> dict:
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
    sql = "SELECT id, geometry AS geom, attributes FROM maps_featurecollection WHERE layer_id=" + layer
    gdf = gpd.read_postgis(sql, con)
    total_data = len(gdf)
    sql = f'''SELECT a.* From
            (SELECT * FROM maps_featurecollection WHERE layer_id={layer}) a
            INNER JOIN (SELECT * FROM maps_featurecollection WHERE layer_id={layer}) b ON 
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

def check_self_intersection(data: GeoDataFrame, layer) -> dict:
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
    total_data = len(data)
    self_intersection_rows = []
    for i, row in data.iterrows():
        if not row['geom'].is_simple:
            self_intersection_rows.append(row['id'])
    CleaningErrors.objects.update_or_create(layer_id=layer, defaults={"self_instersect": self_intersection_rows})
    content = {"error_data": len(self_intersection_rows), "total_data": total_data}
    return content

def check_snapping(layer, con) -> dict:
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
    sql = "SELECT id, geometry AS geom, attributes FROM maps_featurecollection WHERE layer_id=" + layer
    gdf = gpd.read_postgis(sql, con)
    total_data = len(gdf)
    sql = f'''WITH segments AS (
        SELECT id as id, (
        ST_MakeLine(lag((pt).geom, 1, NULL) OVER (PARTITION BY id ORDER BY id, (pt).path), (pt).geom)) AS geometry
        FROM (SELECT id, ST_DumpPoints(geometry) AS pt FROM maps_featurecollection WHERE layer_id={layer}) as dumps
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
        gdf.to_postgis(con=con, name="snap_points", if_exists='replace', schema='topology')
        s = f'''SELECT DISTINCT a.* from (SELECT * FROM maps_featurecollection WHERE layer_id={layer}) a 
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
def fix_null(data: GeoDataFrame, layer) -> dict:
    try:
        data = data[~data.is_empty]
        content = check_null(data, layer)
        return {"message": "Successfully fixed null geometry", "error_data": content["error_data"], "total_data": content["total_data"]}
    except:
        content = check_null(data, layer)
        return {"message": "Failed to fix null geometry", "error_data": content["error_data"], "total_data": content["total_data"]}

def fix_multipart(data: GeoDataFrame, layer) -> dict:
    try:
        df = gpd.GeoDataFrame(crs='epsg:4326', geometry=[], columns=data.columns.values)
        for i, row in data.iterrows():
            data = ops.linemerge(row.geometry)
            data = gpd.GeoDataFrame(crs='epsg:4326', geometry=[data])
            data = data.explode(index_parts=True)
            for value in row.keys():
                if value != 'geometry':
                    data.at[i,value] = row[value]
            df = pd.concat([df, data])
        content = check_multipart(df, layer)
        return {"message": "Successfully fixed multipart geometry", "error_data": content["error_data"], "total_data": content["total_data"]}
    except:
        content = check_multipart(data, layer)
        return {"message": "Failed to fix null geometry", "error_data": content["error_data"], "total_data": content["total_data"]}

def fix_duplicate(data: GeoDataFrame, layer) -> dict:
    try:
        data = data.drop_duplicates(keep='last')
        content = check_duplicate(data, layer)
        return {"message": "Successfully fixed duplicate geometry", "error_data": content["error_data"], "total_data": content["total_data"]}
    except:
        content = check_duplicate(data, layer)
        return {"message": "Failed to fix duplicate geometry", "error_data": content["error_data"], "total_data": content["total_data"]}

def fix_overlapping(data: GeoDataFrame) -> dict:
    try: 
        return "Successfully fixed overlay geometries", data
    except:
        return "Failed to fix overlay geomtries", data

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

def fix_self_intersection(data: GeoDataFrame) -> dict:
    try:
        df = gpd.GeoDataFrame(crs='epsg:4326', geometry=[], columns=data.columns.values)
        for i, row in data.iterrows():
            # if row['has_self_intersection']:
            mls = ops.unary_union(row.geometry)
            if isinstance(mls, MultiLineString):
                coords_list = []
                for part in mls.geoms:
                    coords_list.extend(part.coords)
                points = [item for item, count in collections.Counter(coords_list).items() if count > 1]

                multi_point = MultiPoint(points)
                result = ops.split(row.geometry, multi_point)
                for geom in result.geoms:
                    if geom.length > convert_distance_to_4326(10):
                        df = pd.concat([df, gpd.GeoDataFrame(geometry=[geom])], ignore_index=True)
            else:
                df = pd.concat([df, gpd.GeoDataFrame(geometry=[row.geometry])], ignore_index=True)
        return "Successfully fixed self intersection", df
    except:
        return "Failed to fix self intersection", data

def fix_snapping(data: GeoDataFrame) -> dict:
    try:
        sql = '''select (ST_Azimuth(h.vec) - ST_Azimuth(h.seg))
                from (
                    select 
                        ST_MakeLine(cp.p, point.geom) vec,
                        ST_MakeLine(cp.p, 
                            ST_LineInterpolatePoint(
                                line.geom, 
                                ST_LineLocatePoint(line.geom, cp.p) * 1.01)
                        ) seg
                        from (
                            select 
                                ST_ClosestPoint(line.geom, point.geom)
                        ) p as cp
                    ) as h'''
        con = '''ST_Contains(ST_Buffer(line.geom, 100, 'side=left'), point.geom)'''
        return "Successfully fixed the geometry", data
    except:
        return "Failed to fix the geometry", data