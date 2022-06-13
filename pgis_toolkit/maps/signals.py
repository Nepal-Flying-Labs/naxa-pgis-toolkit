from django.contrib.gis.db.models import Extent
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from rest_framework import status
from rest_framework.response import Response

from config.settings.local import geoserver
from pgis_toolkit.maps.models import (
    FeatureCollection,
    Layer,
    RasterLayer,
    Theme,
    Vectorlayer,
    WMSLayer,
)


@receiver(post_save, sender=Layer)
def post_save_layer(sender, instance, created,**kwargs):
    '''
    This signal is to create an instance based on layer_type of created Layer
    '''
    errors = []
    try:
        if created:
            if instance.layer_type=="Raster":
                RasterLayer.objects.create(layer=instance)
            elif instance.layer_type=="Vector":
                Vectorlayer.objects.create(layer=instance)
            elif instance.layer_type=="WMS":
                WMSLayer.objects.create(layer=instance)
            return Response(status=status.HTTP_200_OK, data={"Message": "Layer Successfully created"})
    except Exception as e:
        errors.append({'errorName': str(e), 'details': str(e)})
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})

@receiver(post_save, sender=Theme)
def post_save_theme(sender, instance, created,**kwargs):
    '''
    This signal is to create an instance based on layer_type of created Layer
    '''
    errors = []
    try:
        if created:
            theme_qs=Theme.active.filter(project__id=instance.project.id)
            for theme in theme_qs:
                theme.order+=1
                theme.save()
            return Response(status=status.HTTP_200_OK, data={"Message": "Theme Successfully updated"})
    except Exception as e:
        errors.append({'errorName': str(e), 'details': str(e)})
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})

# pre_delete¶

# django.db.models.signals.pre_delete¶

# Sent at the beginning of a model’s delete() method and a queryset’s delete() method.

@receiver(pre_delete, sender=Layer)
def pre_delete_layer(sender, instance,**kwargs):
    '''
    This signal is to delete layer from geoserver before deletion of layer
    '''
    errors = []
    try:
        layer_type=instance.layer_type
        if layer_type=="Vector":
            vector_layer_instance=Vectorlayer.objects.get(layer=instance.id)
            if vector_layer_instance:
                layer_name=vector_layer_instance.geoserver_layer_name
                workspace_name=vector_layer_instance.geoserver_workspace
                # delete layer
                geoserver.delete_layer(layer_name=layer_name, workspace=workspace_name)
                # delete feature store, i.e. remove postgresql connection
                geoserver.delete_featurestore(featurestore_name=layer_name, workspace=workspace_name)
        elif layer_type=="Raster":
            raster_layer_instance=RasterLayer.objects.get(layer=instance.id)
            if raster_layer_instance:
                layer_name=raster_layer_instance.geoserver_layer_name
                workspace_name=raster_layer_instance.geoserver_workspace
                # delete layer
                geoserver.delete_layer(layer_name=layer_name, workspace=workspace_name)

                # delete coveragestore, i.e. delete raster store
                geoserver.delete_coveragestore(coveragestore_name=layer_name, workspace=workspace_name)

                # delete style file
                geoserver.delete_style(style_name=layer_name, workspace=workspace_name)
        return Response(status=status.HTTP_200_OK, data={"Message": "Layer Successfully deleted"})

    except Exception as e:
        errors.append({'errorName': str(e), 'details': str(e)})
        print("error"+str(errors))
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})



# @receiver(post_save, sender=FeatureCollection)
# def post_save_feature(sender, instance, created,**kwargs):
#     '''
#     This signal is to create an instance based on layer_type of created Layer
#     '''
#     errors = []
#     try:
#         if created:
#             layer_instance=Layer.objects.get(id=instance.layer.id)
#             vector_layer_instance=Vectorlayer.objects.get(id=layer_instance.id)
#             if instance.geometry:
#                 feature = instance.aggregate(Extent('geometry'))
#                 bbox = feature['geometry__extent']
#                 print(bbox,"bdhsbhbooox")
#                 # vector_layer_instance.save()
#             return Response(status=status.HTTP_200_OK, data={"Message": "Theme Successfully updated"})
#     except Exception as e:
#         errors.append({'errorName': str(e), 'details': str(e)})
#         return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
