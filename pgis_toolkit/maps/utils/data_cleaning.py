import geopandas as gpd

# Checking data
def check_null_geometry(data: gpd.GeoDataframe) -> dict:
    """Check if the geometry is null or not

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    message: str
        The message to display
    GeoDataFrame
    """
    data["is_null"] = False
    null_rows = 0
    for i, row in data.iterrows():
        if row.geomey.is_empty:
            data.at[i,'is_null'] = True
            null_rows += 1
        else:
            data.at[i,'is_null'] = False
    return f"Total {null_rows} geometries were found empty", data

def check_multipart(data):
    """Check if the data is multipart or not
    
    Parameters
    ----------
    data : GeoDataFrame
        The data to check
        
    Returns
    -------
    message: str
        The message to display
    GeoDataFrame
    """
    data["is_multipart"] = True
    multipart_rows = 0
    for i, row in data.iterrows():
        if row.geom.type.startswith("Multi"):
            data.at[i,'is_multipart'] = True
            multipart_rows += 1
        else:
            data.at[i,'is_multipart'] = False
    return f"Total {multipart_rows} geometry were found multipart", data

def check_duplicate(data):
    """Check if the geometry is duplicate or not

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    message: str
        The message to display
    data : GeoDataFrame
    """
    sum = data.duplicated().sum()
    return f"Total {sum} geometries were found duplicate", data

def check_self_intersection(data):
    """Check if the geometry has self intersection or not

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    message: str
        The message to display
    GeoDataFrame
    """
    data["has_self_intersection"] = False
    self_intersection_rows = 0
    for i, row in data.iterrows():
        if row['geom'].is_simple:
            data.at[i,'has_self_intersection'] = False
        else:
            data.at[i,'has_self_intersection'] = True
            self_intersection_rows += 1
    return f"Total {self_intersection_rows} geometries were found with self intersection", data

def check_snapping(data):
    """Check for isolated points

    Parameters
    ----------
    data : GeoDataFrame
        The data to check

    Returns
    -------
    message: str
        The message to display
    GeoDataFrame
    """
    pass


# Dry run for cleaning data
def dry_fix_null_geometry(data: gpd.GeoDataframe) -> dict:
    pass

def dry_fix_multipart(data: gpd.GeoDataframe) -> dict:
    pass

def dry_fix_duplicate(data: gpd.GeoDataframe) -> dict:
    pass

def dry_fix_intersection(data: gpd.GeoDataframe) -> dict:
    pass

def dry_fix_snapping(data: gpd.GeoDataframe) -> dict:
    pass


# Cleaning data
def fix_null_geometry(data: gpd.GeoDataframe) -> dict:
    pass

def fix_multipart(data: gpd.GeoDataframe) -> dict:
    pass

def fix_duplicate(data: gpd.GeoDataframe) -> dict:
    pass

def fix_self_intersection(data: gpd.GeoDataframe) -> dict:
    pass

def fix_snapping(data: gpd.GeoDataframe) -> dict:
    pass