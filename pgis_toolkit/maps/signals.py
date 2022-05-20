from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework import status
from rest_framework.response import Response

from pgis_toolkit.maps.models import Layer, RasterLayer, Vectorlayer, WMSLayer


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
