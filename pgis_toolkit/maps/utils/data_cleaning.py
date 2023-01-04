import geopandas as gpd
from geopandas import GeoDataFrame
import pandas as pd
import networkx as nx
from shapely import ops
from shapely.geometry import MultiLineString, MultiPoint
import collections
import momepy

#===================
# Checking data
#===================
def check_null(data: GeoDataFrame) -> dict:
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
    data["is_null"] = False
    null_rows = 0
    for i, row in data.iterrows():
        if row.geom.is_empty:
            data.at[i,'is_null'] = True
            null_rows += 1
        else:
            data.at[i,'is_null'] = False
    content = {"error_data": null_rows, "total_data": total_data, "data": data.to_json()}
    return content

def check_multipart(data: GeoDataFrame) -> dict:
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
    data["is_multipart"] = True
    multipart_rows = 0
    for i, row in data.iterrows():
        if row.geom.type.startswith("Multi"):
            data.at[i,'is_multipart'] = True
            multipart_rows += 1
        else:
            data.at[i,'is_multipart'] = False
    content = {"error_data": multipart_rows, "total_data": total_data, "data": data.to_json()}
    return content

def check_duplicate(data: GeoDataFrame) -> dict:
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
    content = {"error_data": sum, "total_data": total_data, "data": data.to_json()}
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
    sql = f'''SELECT a.*
        FROM maps_featurecollection WHERE layer_id={layer} as a
        INNER JOIN maps_featurecollection WHERE layer_id={layer} as b ON 
        (a.geometry && b.geometry AND ST_Overlaps(a.geometry, b.geometry))
        WHERE a.id != b.id'''
    try:
        data = gpd.read_postgis(sql, con, geom_col="geometry")
        error_data = len(data)
    except:
        data = gdf
        error_data = 0
    content = {"error_data": error_data, "total_data": total_data, "data": data.to_json()}
    return content

def check_self_intersection(data: GeoDataFrame) -> dict:
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
    data["has_self_intersection"] = False
    self_intersection_rows = 0
    for i, row in data.iterrows():
        if row['geom'].is_simple:
            data.at[i,'has_self_intersection'] = False
        else:
            data.at[i,'has_self_intersection'] = True
            self_intersection_rows += 1
    content = {"error_data": self_intersection_rows, "total_data": total_data, "data": data.to_json()}
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
    # largest = components.pop(0)
    isolated = list( g for cc in components for g in cc )
    content = {"error_data": len(isolated), "total_data": total_data, "data": data.to_json()}
    return content

#===================
# Cleaning data
#===================
def fix_null(data: GeoDataFrame) -> dict:
    try:
        data = data[~data.is_empty]
        return "Successfully fixed null geometry", data.to_json()
    except:
        return "Failed to fix null geometry", data.to_json()

def fix_multipart(data: GeoDataFrame) -> dict:
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
        return "Successfully fixed multipart geometry", df
    except:
        return "Failed to fix multipart geometry", data

def fix_duplicate(data: GeoDataFrame) -> dict:
    try:
        data = data.drop_duplicates(keep='last')
        return "Successfully fixed duplicate geometry", data
    except:
        return "Failed to fix duplicate geometry", data

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
                    if geom.length > convert_distance_to_4326(50):
                        df = pd.concat([df, gpd.GeoDataFrame(geometry=[geom])], ignore_index=True)
            else:
                df = pd.concat([df, gpd.GeoDataFrame(geometry=[row.geometry])], ignore_index=True)
        return "Successfully fixed self intersection", df
    except:
        return "Failed to fix self intersection", data

def fix_snapping(data: GeoDataFrame) -> dict:
    try:
        return "Successfully fixed the geometry", data
    except:
        return "Failed to fix the geometry", data