import glob
import zipfile

import geopandas as gpd
from django.contrib.gis.geos import GEOSGeometry
from projects.models import Project, ProjectLocationFeatureCollection


def handleProjectGeoJSON(project_id):
    '''Creates objects of ProjectLocationFeatureCollection from each row of the GeoJSON'''
    try:
        project_obj = Project.active.get(id=project_id)
        my_file = project_obj.file
        gdf = gpd.read_file(my_file)
        crs_name = str(gdf.crs.srs)
        epsg = int(crs_name.replace("epsg:", ""))
        if epsg is None:
            epsg = 4326
        geometry_type = gdf['geometry'].iloc[0].geom_type
        total_bounds = gdf.total_bounds
        bound_dict = {"total_bounds": total_bounds.tolist()}
        project_obj.geometry_type = geometry_type
        project_obj.bbox = bound_dict
        project_obj.save()
        for index, row in gdf.iterrows():
            dropped_geometry = row.drop(["geometry"])
            dropped_geometry_dict = dropped_geometry.to_dict()
            ProjectLocationFeatureCollection.objects.create(project=project_obj,
                                                            attributes=dropped_geometry_dict,
                                                            geometry=GEOSGeometry(
                                                                str(row["geometry"])))
        return "successful"
    except Exception as e:
        return str(e)


def handleProjectShapeFile(project_id):
    '''Creates objects of ProjectFeatureCollection from each row of the Shapefile'''
    try:
        project_obj = Project.active.get(id=project_id)
        my_file = project_obj.file
        with zipfile.ZipFile(my_file, "r") as zip_ref:
            zip_ref.extractall(str(my_file))
        shape = glob.glob(
            r'{}/**/*.shp'.format(str(my_file)), recursive=True)[0]
        gdf = gpd.read_file(shape)
        geometry_type = gdf['geometry'].iloc[0].geom_type

        total_bounds = gdf.total_bounds
        bound_dict = {"total_bounds": total_bounds.tolist()}
        project_obj.geometry_type = geometry_type
        project_obj.bbox = bound_dict
        project_obj.save()
        crs_name = str(gdf.crs.srs)
        epsg = int(crs_name.replace("epsg:", ""))
        if epsg is None:
            epsg = 4326
        for index, row in gdf.iterrows():
            dropped_geometry = row.drop(["geometry"])
            dropped_geometry_dict = dropped_geometry.to_dict()
            ProjectLocationFeatureCollection.objects.create(project=project_obj,
                                                            attributes=dropped_geometry_dict,
                                                            geometry=GEOSGeometry(
                                                                str(row["geometry"])))
        return "successful"
    except Exception as e:
        return str(e)
