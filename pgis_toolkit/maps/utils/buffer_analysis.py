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
from pgis_toolkit.maps.models import Analysis, BufferAnalysis, BufferAreas


def buffer_analysis(layer, radius,  radius_col, dissolve_output, analysis_id, buffer_analysis_id):
    """
    Description:
    ------------
    generate buffer areas
    1 degree is ~ 111139 meters on averaging all over earth.

    Parameters:
    -----------
    layer: <int> layer_id
    radius: <float> buffer radius
    radius_col: <str> radius column name
    dissolve_output: <bool> dissolve overlapping polygons or not.
    analysis_id: <int> analysis_id
    buffer_analysis_id: <int> buffer_analysis_id

    Returns:
    --------
    json data with analysis_id, buffer_analysis_id, message_code, message, status_code

    """
    try:
        if dissolve_output and radius_col:
            buffer_sql = f"(ST_Dump(ST_Union(ST_Buffer(geometry, ((attributes ->> '{radius_col}')::float8)/111139)))).geom AS geometry"
            group_by = ''
        elif dissolve_output and radius:
            buffer_sql = f'(ST_Dump(ST_Union(ST_Buffer(geometry, (({radius}::float8)/111139))))).geom AS geometry'
            group_by = ''
        elif radius_col:
            buffer_sql = f"ST_Buffer(geometry, (((attributes ->> '{radius_col}')::float8)/111139)) AS geometry"
            group_by = 'GROUP BY attributes, geometry'
        elif radius:
            buffer_sql = f'ST_Buffer(geometry, (({radius}::float8)/111139)) AS geometry'
            group_by = 'GROUP BY attributes, geometry'
        sql = f'''
                --create buffer areas
                WITH buffer AS (
                SELECT
                    jsonb_agg(attributes) as attributes,
                    {buffer_sql}
                FROM
                    maps_featurecollectionmirror
                WHERE
                    layer_id = {layer}
                {group_by}
                )
                --insert buffer areas into table
                INSERT INTO maps_bufferareas (analysis_id, buffer_analysis_id, attributes, geometry, area, is_deleted, uploaded_date, last_updated)
                (SELECT
                {analysis_id} AS analysis_id,
                {buffer_analysis_id} as buffer_analysis_id,
                attributes,
                geometry,
                ST_Area(geometry)*(111139^2) AS area,
                False,
                NOW(),
                NOW()
                FROM buffer);

                --update bbox and total area of buffer analysis object
                UPDATE maps_bufferanalysis
                SET bbox = (SELECT json_build_array(
                                ST_XMin(bbox.geom),
                                ST_YMin(bbox.geom),
                                ST_XMax(bbox.geom),
                                ST_YMax(bbox.geom)
                            ) AS bbox
                            FROM (SELECT ST_Envelope(ST_Collect(geometry)) as geom
                                    FROM maps_bufferareas
                                    WHERE buffer_analysis_id = {buffer_analysis_id})bbox),
                    total_area = (SELECT SUM(area)
                                  FROM maps_bufferareas
                                  WHERE buffer_analysis_id = {buffer_analysis_id})
                WHERE id = {buffer_analysis_id};
        '''
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            return analysis_id, buffer_analysis_id, "success", "", 200
        except Exception as e:
            return None, None, "error", str(e), 500
    except Exception as e:
        if BufferAnalysis.objects.filter(id=buffer_analysis_id).exists():
            BufferAnalysis.objects.get(id=buffer_analysis_id).delete()
        return None, None, "error", str(e), 400
