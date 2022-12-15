import geopandas as gpd

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
    pass

def fix_multipart(data: gpd.GeoDataFrame) -> dict:
    pass

def fix_duplicate(data: gpd.GeoDataFrame) -> dict:
    pass

def fix_self_intersection(data: gpd.GeoDataFrame) -> dict:
    pass

def fix_snapping(data: gpd.GeoDataFrame) -> dict:
    pass