from django.shortcuts import render
from maps.models import (
    Layer,
    LayerGroup,
    RasterLayer,
    SubLayer,
    Theme,
    Vectorlayer,
    WMSLayer,
)
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

# Create your views here.

@api_view(['GET'])
def project_layers(request,id):
    '''
    http://0.0.0.0:8000/api/maps/project_layers/<project_id>/
    This API is for the left bar of the map page
    '''
    try:
        theme_list=[]
        theme_qs=Theme.active.filter(project=id).order_by('order')
        for theme in theme_qs:
            group_list=[]
            group_qs=LayerGroup.active.filter(theme=theme.id).order_by("order")
            for group in group_qs:
                group_layer_list=[]
                group_layer_qs=Layer.active.filter(group=group.id).order_by('order')
                for layer in group_layer_qs:
                    if layer.layer_type=="Vector":
                        layer_detail_instance=Vectorlayer.objects.get(layer=layer.id)
                    if layer.layer_type=="Raster":
                        layer_detail_instance=RasterLayer.objects.get(layer=layer.id)
                    if layer.layer_type=="WMS":
                        layer_detail_instance=WMSLayer.objects.get(layer=layer.id)
                    icon_url=layer_detail_instance.icon.url if layer_detail_instance.icon else None
                    layer_item={"id":layer.id,"name":layer.name,'layer_type':layer.layer_type,'icon':icon_url,'icon_size':layer_detail_instance.icon_size,'style':layer_detail_instance.style}
                    group_layer_list.append(layer_item)
                group_item={"id":group.id,"name":group.name,'layer':group_layer_list}
                group_list.append(group_item)

            layer_list=[]
            layer_qs=Layer.active.filter(theme=theme.id,group=None)
            for layer in layer_qs:
                sub_layer_list=[]
                sub_layer_qs=SubLayer.active.filter(layer=layer.id)
                for sub_layer in sub_layer_qs:
                    icon_url=sub_layer.icon.url if sub_layer.icon else None
                    sub_layer_item={"id":sub_layer.id,"name":sub_layer.name,'icon':icon_url,'icon_size':sub_layer.icon_size,'style':sub_layer.style}
                    sub_layer_list.append(sub_layer_item)
                icon_url=layer_detail_instance.icon.url if layer_detail_instance.icon else None
                layer_item={"id":layer.id,"name":layer.name,'layer_type':layer.layer_type,'icon':icon_url,'icon_size':layer_detail_instance.icon_size,'style':layer_detail_instance.style,'sub_layer':sub_layer_list}
                layer_list.append(layer_item)
            theme_item={"id":theme.id,'name':theme.name,'group':group_list,'layer':layer_list}
            theme_list.append(theme_item)
        return Response(theme_list)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': str(e)})
