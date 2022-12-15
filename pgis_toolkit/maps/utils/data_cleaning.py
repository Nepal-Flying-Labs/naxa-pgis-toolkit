import geopandas as gpd
import pandas as pd
from shapely import ops
from shapely.geometry import MultiLineString, MultiPoint
import collections

# Checking data
def check_null_geometry(data: gpd.GeoDataFrame) -> dict:
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
    data["is_null"] = False
    null_rows = 0
    for i, row in data.iterrows():
        if row.geom.is_empty:
            data.at[i,'is_null'] = True
            null_rows += 1
        else:
            data.at[i,'is_null'] = False
    content = {"message": f"Total {null_rows} geometries were found empty", "data": data}
    return content

def check_multipart(data: gpd.GeoDataFrame) -> dict:
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
    data["is_multipart"] = True
    multipart_rows = 0
    for i, row in data.iterrows():
        if row.geom.type.startswith("Multi"):
            data.at[i,'is_multipart'] = True
            multipart_rows += 1
        else:
            data.at[i,'is_multipart'] = False
    content = {"message": f"Total {multipart_rows} geometry were found multipart", "data": data}
    return content

def check_duplicate(data: gpd.GeoDataFrame) -> dict:
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
    print("data", data)
    print(type(data))
    sum = data.duplicated()
    print(type(sum))
    content = {"message": f"Total {sum} geometries were found duplicate", "data": data}
    print(content)
    return content

def check_self_intersection(data: gpd.GeoDataFrame) -> dict:
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
    data["has_self_intersection"] = False
    self_intersection_rows = 0
    for i, row in data.iterrows():
        if row['geom'].is_simple:
            data.at[i,'has_self_intersection'] = False
        else:
            data.at[i,'has_self_intersection'] = True
            self_intersection_rows += 1
    content = {"message": f"Total {self_intersection_rows} geometries were found with self intersection", "data": data}
    return content

def check_snapping(data: gpd.GeoDataFrame) -> dict:
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
    pass


# Dry run for cleaning data
def dry_fix_null_geometry(data: gpd.GeoDataFrame) -> dict:
    pass

def dry_fix_multipart(data: gpd.GeoDataFrame) -> dict:
    pass

def dry_fix_duplicate(data: gpd.GeoDataFrame) -> dict:
    pass

def dry_fix_intersection(data: gpd.GeoDataFrame) -> dict:
    pass

def dry_fix_snapping(data: gpd.GeoDataFrame) -> dict:
    pass


# Cleaning data
def fix_null_geometry(data: gpd.GeoDataFrame) -> dict:
    try:
        data = data[~data.is_empty]
        return "Successfully fixed null geometry", data
    except:
        return "Failed to fix null geometry", data

def fix_multipart(data: gpd.GeoDataFrame) -> dict:
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

def fix_duplicate(data: gpd.GeoDataFrame) -> dict:
    try:
        data = data.drop_duplicates(keep='last')
        return "Successfully fixed duplicate geometry", data
    except:
        return "Failed to fix duplicate geometry", data

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

def fix_self_intersection(data: gpd.GeoDataFrame) -> dict:
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

def fix_snapping(data: gpd.GeoDataFrame) -> dict:
    pass