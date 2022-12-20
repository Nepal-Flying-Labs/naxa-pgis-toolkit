import glob
import os
import shutil
import zipfile

import geopandas as gpd
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry

from pgis_toolkit.maps.models import FeatureCollection, Layer, Theme, Vectorlayer
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
        # bound_dict = {"total_bounds": total_bounds.tolist()}
        project_obj.geometry_type = geometry_type
        project_obj.bbox = total_bounds.tolist()
        project_obj.save()
        theme_qs = Theme.active.filter(project=project_obj, name='Baseline')
        if theme_qs.exists():
            '''create a layer of project location in baseline theme'''
            layer_instance, layer_created = Layer.active.get_or_create(theme=theme_qs[0], name= 'Boundary', layer_type='Vector', defaults={'theme':theme_qs[0], 'name':'Boundary', 'layer_type':'Vector', 'source':'survey', 'display_on_map':'True'})
            if not layer_created: layer_instance.upload_status='uploading'
            vector_layer_instance,vector_created = Vectorlayer.objects.get_or_create(layer=layer_instance, defaults={'layer':layer_instance, 'geom_type':geometry_type, 'bbox':total_bounds.tolist()})
            if not vector_created:
                vector_layer_instance.bbox = []
                vector_layer_instance.geom_type=geometry_type
                vector_layer_instance.save()
            FeatureCollection.active.filter(layer=layer_instance).update(is_deleted=True)

            for index, row in gdf.iterrows():
                dropped_geometry = row.drop(["geometry"])
                dropped_geometry_dict = dropped_geometry.to_dict()
                geometry=GEOSGeometry(str(row["geometry"]))
                ProjectLocationFeatureCollection.objects.create(project=project_obj,
                                                                attributes=dropped_geometry_dict,
                                                                geometry=geometry)
                FeatureCollection.active.create(layer=layer_instance, attributes=dropped_geometry_dict, geometry=geometry)
                layer_instance.upload_status='successful'
                layer_instance.save()
        else:
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
        # bound_dict = {"total_bounds": total_bounds.tolist()}
        project_obj.geometry_type = geometry_type
        project_obj.bbox = total_bounds.tolist()
        project_obj.save()
        crs_name = str(gdf.crs.srs)
        epsg = int(crs_name.replace("epsg:", ""))
        if epsg is None:
            epsg = 4326
        theme_qs = Theme.active.filter(project=project_obj, name='Baseline')
        if theme_qs.exists():
            '''create a layer of project location in baseline theme'''
            layer_instance, layer_created = Layer.active.get_or_create(theme=theme_qs[0], name= 'Boundary', layer_type='Vector', defaults={'theme':theme_qs[0], 'name':'Boundary', 'layer_type':'Vector', 'source':'survey', 'display_on_map':'True'})
            if not layer_created: layer_instance.upload_status='uploading'
            vector_layer_instance,vector_created = Vectorlayer.objects.get_or_create(layer=layer_instance, defaults={'layer':layer_instance, 'geom_type':geometry_type, 'bbox':total_bounds.tolist()})
            if not vector_created:
                vector_layer_instance.bbox = []
                vector_layer_instance.geom_type=geometry_type
                vector_layer_instance.save()
            FeatureCollection.active.filter(layer=layer_instance).update(is_deleted=True)

            for index, row in gdf.iterrows():
                dropped_geometry = row.drop(["geometry"])
                dropped_geometry_dict = dropped_geometry.to_dict()
                geometry=GEOSGeometry(str(row["geometry"]))
                ProjectLocationFeatureCollection.objects.create(project=project_obj,
                                                                attributes=dropped_geometry_dict,
                                                                geometry=geometry)
                FeatureCollection.active.create(layer=layer_instance, attributes=dropped_geometry_dict, geometry=geometry)
            layer_instance.upload_status='successful'
            layer_instance.save()
        else:
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
        print('error occured in handleProjectShapeFile in project: '+str(e))
        return str(e)
