from django.shortcuts import render
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

# import environ
# env = environ.Env()
# environ.Env.read_env()
# Create your views here.
from config.settings.base import env
from pgis_toolkit.maps.models import (
    Layer,
    LayerGroup,
    RasterLayer,
    SubLayer,
    Theme,
    Vectorlayer,
    WMSLayer,
)
from pgis_toolkit.maps.tasks import UploadRasterLayer, UploadVectorLayer, UploadWMSLayer

from .serializers import LayerSerializer


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
                    layer_item={"id":layer.id,"name":layer.name,'layer_type':layer.layer_type}
                    if layer.layer_type=="Vector":
                        layer_detail_instance=Vectorlayer.objects.get(layer=layer.id)
                        icon_url=env("URL")+layer_detail_instance.icon.url if layer_detail_instance.icon else None
                        layer_item['icon']=icon_url
                        layer_item['icon_size']=layer_detail_instance.icon_size,
                        layer_item['style']=layer_detail_instance.style
                    # elif layer.layer_type=="Raster":
                    #     layer_detail_instance=RasterLayer.objects.get(layer=layer.id)
                    # elif layer.layer_type=="WMS":
                    #     layer_detail_instance=WMSLayer.objects.get(layer=layer.id)
                    group_layer_list.append(layer_item)
                group_item={"id":group.id,"name":group.name,'layer':group_layer_list}
                group_list.append(group_item)

            layer_list=[]
            layer_qs=Layer.active.filter(theme=theme.id,group=None)
            for layer in layer_qs:
                layer_item={"id":layer.id,"name":layer.name,'layer_type':layer.layer_type}
                if layer.layer_type=="Vector":
                    print(layer.id,layer.layer_type)
                    layer_detail_instance=Vectorlayer.objects.get(layer=layer.id)
                    sub_layer_list=[]
                    sub_layer_qs=SubLayer.active.filter(layer=layer.id)
                    for sub_layer in sub_layer_qs:
                        icon_url=env("URL")+sub_layer.icon.url if sub_layer.icon else None
                        sub_layer_item={"id":sub_layer.id,"name":sub_layer.name,'icon':icon_url,'icon_size':sub_layer.icon_size,'style':sub_layer.style}
                        sub_layer_list.append(sub_layer_item)
                    icon_url=env("URL")+layer_detail_instance.icon.url if layer_detail_instance.icon else None
                    layer_item['icon']=icon_url
                    layer_item['icon_size']=layer_detail_instance.icon_size,
                    layer_item['style']=layer_detail_instance.style
                    layer_item['sub_layer']=sub_layer_list
                # elif layer.layer_type=="Raster":
                #     layer_detail_instance=RasterLayer.objects.get(layer=layer.id)
                # elif layer.layer_type=="WMS":
                #     layer_detail_instance=WMSLayer.objects.get(layer=layer.id)
                layer_list.append(layer_item)
            theme_item={"id":theme.id,'name':theme.name,'group':group_list,'layer':layer_list}
            theme_list.append(theme_item)
        return Response(theme_list)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': str(e)})


class LayerAPIView(APIView):
    def post(self, request, format=None):
        request_dict = request.data
        name = request_dict['name'] if 'name' in request_dict.keys() else None
        if Layer.active.filter(name=name).exists():
            return Response(data={'message': 'Cannot create duplicate layer names.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = LayerSerializer(data=request_dict)
        if serializer.is_valid():
            created_object = serializer.save()
            layer_type = created_object.layer_type
            '''handle Vector layer upload'''
            if layer_type == "Vector":
                UploadVectorLayer(created_object.id, request_dict)
                '''handle Vector layer upload'''
            elif layer_type == "Raster":
                UploadRasterLayer(created_object.id, request_dict)
                '''handle Vector layer upload'''
            elif layer_type == "WMS":
                UploadWMSLayer(created_object.id, request_dict)
            else:
                Layer.objects.get(id=created_object.id).delete()
                return Response(data={'message': 'Invalid Layer Type. Choices are: Vector, Raster and WMS'})
        return Response(data={'message': 'Layer Created', 'data': serializer.data}, status=status.HTTP_201_CREATED)

    def patch(self, request, pk=None):
        request.data._mutable=True
        request_dict = request.data
        request_keys = request_dict.keys()
        if 'layer_type' in request_keys:
            request_dict.pop('layer_type')
        name = request_dict['name'] if 'name' in request_keys else None
        if Layer.active.exclude(pk=pk).filter(name=name).exists():
            return Response(data={'message': 'Cannot create duplicate layer names.'}, status=status.HTTP_400_BAD_REQUEST)
        layer_instance = Layer.active.get(pk=pk)
        serializer = LayerSerializer(layer_instance, data=request_dict, partial=True)
        if serializer.is_valid():
            created_object = serializer.save()
            layer_type = Layer.active.get(pk=pk).layer_type
            '''handle Vector layer update'''
            if layer_type == "Vector":
                pass
                '''handle Vector layer update'''
            elif layer_type == "Raster":
                pass
                '''handle Vector layer upload'''
            elif layer_type == "WMS":
                if 'url' in request_keys and request_dict['url'] != "":
                    wms_instance = WMSLayer.objects.get(layer__id=pk)
                    wms_instance.url = request_dict['url']
                    wms_instance.save()
            else:
                return Response(data={'message': 'Invalid Layer Type. Choices are: Vector, Raster and WMS'})
            created_object.save()
        return Response(data={'message': 'Layer Updated', 'data': serializer.data}, status=status.HTTP_201_CREATED)
