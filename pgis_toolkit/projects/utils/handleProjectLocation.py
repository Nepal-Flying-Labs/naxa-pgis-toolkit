import glob
import os
import shutil
import zipfile

import geopandas as gpd
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry

from pgis_toolkit.projects.models import Project, ProjectLocationFeatureCollection


def clear_dir(dir):
    '''function to clear files in a specific directory'''
    for files in os.listdir(dir):
        path = os.path.join(dir, files)
        try:
            shutil.rmtree(path)
        except OSError:
            os.remove(path)

def handleProjectGeoJSON(project_id):
    '''Creates objects of ProjectLocationFeatureCollection from each row of the GeoJSON'''
    try:
        project_obj = Project.active.get(id=project_id)
        my_file = project_obj.file
        file_path = settings.MEDIA_ROOT + '/' + str(my_file).split('/')[0]
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
        clear_dir(file_path)
        return "successful"
    except Exception as e:
        return str(e)


def handleProjectShapeFile(project_id):
    '''Creates objects of ProjectFeatureCollection from each row of the Shapefile'''
    try:
        project_obj = Project.active.get(id=project_id)
        my_file = project_obj.file
        file_name = str(my_file).split('/')
        file_path = settings.MEDIA_ROOT + '/' + file_name[0]
        extract_path = settings.MEDIA_ROOT + '/site/raw/' + file_name[1]
        with zipfile.ZipFile(my_file, "r") as zip_ref:
            zip_ref.extractall(extract_path)
        shape = glob.glob(
            r'{}/**/*.shp'.format(extract_path), recursive=True)[0]
        # print(shape, "is shape")
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
        clear_dir(file_path)
        return "successful"
    except Exception as e:
        return str(e)
