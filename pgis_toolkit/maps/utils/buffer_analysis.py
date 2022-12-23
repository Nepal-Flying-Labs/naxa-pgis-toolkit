import geopandas as gpd

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

def buffer_by_distance(data, distance: float, dissolve: bool) -> dict:
    """Buffer geometries for provided distance and dissolve overlapping geometries after buffer

    Parameters
    ----------
    data : GeoDataFrame
        The data to buffer
    distance : float
        The buffer distance
    dissolve : bool
        If to dissolved overlapping geometries after buffer

    Returns
    -------
    data : GeoDataFrame
        The dissolved geodataframe
    """
    distance = 10 if distance is None else distance
    dissolve = False if dissolve is None else dissolve
    gdf = data.to_crs("epsg:3857")
    data = gdf.buffer(float(distance))
    data = gpd.GeoDataFrame(crs='epsg:3857', geometry=data, columns=gdf.columns.values)
    if dissolve:
        data = dissolve_data(data)
    data = data.to_crs("epsg:4326")
    return data

def buffer_by_column_value(data, column: str, ratio: float, dissolve: bool) -> dict:
    """Buffer geometries for provided distance and dissolve overlapping geometries after buffer

    Parameters
    ----------
    data : GeoDataFrame
        The data to buffer
    column: str
        Column name which will be used for buffer value
    ratio : float
        Factor to multiply the column value
    dissolve : bool
        If to dissolved overlapping geometries after buffer

    Returns
    -------
    data : GeoDataFrame
        The dissolved geodataframe
    """
    ratio = 1 if ratio is None else ratio
    dissolve = False if dissolve is None else dissolve
    data = data.to_crs("epsg:3857")
    df = gpd.GeoDataFrame(geometry=[])
    for index, row in data.iterrows():
        buffer_value = row[column] * ratio
        buffer = row['geometry'].buffer(buffer_value)
        df = df.append(gpd.GeoDataFrame(geometry=[buffer]))
    if dissolve:
        df = dissolve_data(df)
    df = df.to_crs("epsg:4326")
    return df

def find_data_within_buffer(data, distance: float, layers: list) -> dict:
    """Buffer geometries for provided distance and dissolve overlapping geometries after buffer

    Parameters
    ----------
    data : GeoDataFrame
        The data to buffer
    distance : float
        The buffer distance
    layers : list
        layer list to find data of

    Returns
    -------
    data : GeoDataFrame
        The dissolved geodataframe
    """
    buffered_data = buffer_by_distance(data, distance, False)
    datas = []
    for layer in layers:
        df = gpd.sjoin(buffered_data, layer, op="within")
        datas.append(df)
    return datas