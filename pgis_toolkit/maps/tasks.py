from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from pgis_toolkit.maps.models import Layer, WMSLayer


def UploadVectorLayer(layer_id, request_dict):
    pass
    
def UploadRasterLayer(layer_id, request_dict):
    pass

def UploadWMSLayer(layer_id, request_dict):
    if 'url' in request_dict.keys() and request_dict['url'] != "":
        layer_instance = Layer.active.get(id=layer_id)
        WMSLayer.objects.get_or_create(layer=layer_instance, url=request_dict['url'])
    return Response(data={'message': 'URL is mandatory!'}, status=status.HTTP_400_BAD_REQUEST)
