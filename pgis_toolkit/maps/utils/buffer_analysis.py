import geopandas as gpd
from pgis_toolkit.maps.models import Analysis, BufferAnalysis, BufferAreas
from shapely.geometry import Point

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

def buffer_analysis(origins, radius, dissolve_output, analysis_id, buffer_id):
    try:
        points = []
        for origin in origins:
            point = Point(origin[1], origin[0])
            points.append(point)
        gdf = gpd.GeoDataFrame(geometry=points, crs=4326)
        gdf = gdf.to_crs("epsg:3857")
        data = gdf.buffer(float(radius))
        data = gpd.GeoDataFrame(crs='epsg:3857', geometry=data, columns=gdf.columns.values)
        if dissolve_output:
            data = dissolve_data(data)
        area = data.iloc[0].geometry.area
        data = data.to_crs("epsg:4326")
        buffer_objs = []
        for i, row in data.iterrows():
            result_dict = {'geometry': row.geometry.wkt, 'area': area, 'bbox': list(row.geometry.bounds), 'analysis_id': analysis_id}
            buffer_objs.append(BufferAreas(**result_dict))
        BufferAreas.active.bulk_create(buffer_objs)
        analysis_inst = Analysis.active.get(id=analysis_id)
        analysis_inst.bbox = list(data.total_bounds)
        analysis_inst.save()
        buffer_inst = BufferAnalysis.active.get(id=buffer_id)
        buffer_inst.total_area = area * len(origins)
        buffer_inst.save()
        return analysis_id, "success", "", 200
    except Exception as e:
        if Analysis.objects.filter(id=analysis_id).exists():
            Analysis.objects.get(id=analysis_id).delete()
        if BufferAnalysis.objects.filter(id=buffer_id).exists():
            BufferAnalysis.objects.get(id=buffer_id).delete()
        return None, "error", str(e), 400