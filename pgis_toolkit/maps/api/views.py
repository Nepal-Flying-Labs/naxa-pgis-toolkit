# from celery.result import AsyncResult
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from config.settings.base import env
from pgis_toolkit.celery_app import app
from pgis_toolkit.maps.models import (
    Layer,
    LayerFile,
    LayerGroup,
    RasterLayer,
    SubLayer,
    Theme,
    Vectorlayer,
    WMSLayer,
)
from pgis_toolkit.maps.tasks import UploadRasterLayer, UploadVectorLayer, UploadWMSLayer

from .serializers import LayerSerializer, WMSLayerSerializer


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
        errors=[]
        try:
            request_dict = request.data
            name = request_dict['name'] if 'name' in request_dict.keys() else None
            if Layer.active.filter(name=name).exists():
                return Response(data={'message': 'Cannot create duplicate layer names.'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = LayerSerializer(data=request_dict)
            if serializer.is_valid():
                created_object = serializer.save()
                print(created_object.id,"idddddddd")
                layer_type = created_object.layer_type
                if layer_type == "Vector":
                    '''handle Vector layer upload'''
                    if 'file' in request.FILES and request.FILES.get('file') != "":
                        layer_file_instance = LayerFile.objects.create(
                            file=request.FILES['file'],layer=created_object)
                    else:
                        Layer.objects.filter(id=created_object.id).delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'error occured', 'error': "File is missing"})
                    response=UploadVectorLayer.delay(created_object.id)
                    # return Response(response)
                    return Response(status=200,
                                    data={'message': 'Uploading Data', 'task_id': response.task_id})

                elif layer_type == "Raster":
                    '''handle Raster layer upload'''
                    UploadRasterLayer(created_object.id, request_dict)

                elif layer_type == "WMS":
                    '''handle WMS layer upload'''
                    wms_layer_instance=WMSLayer.objects.get(layer=created_object.id)
                    wms_serializer = WMSLayerSerializer(wms_layer_instance, data=request_dict, partial=True)
                    if wms_serializer.is_valid():
                        wms_serializer.save()
                    else:
                        for er in wms_serializer._errors:
                            errors.append(
                                {'errorName': er, 'details': wms_serializer._errors[er][0]})
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
                    return Response(data={'message': 'Layer Created', 'data': serializer.data}, status=status.HTTP_201_CREATED)
                else:
                    Layer.objects.get(id=created_object.id).delete()
                    return Response(data={'message': 'Invalid Layer Type. Choices are: Vector, Raster and WMS'})
                return Response(data={'message': 'Layer Created', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
        except Exception as e:
            errors.append({'errorName': str(e), 'details': str(e)})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'Message': 'Dataset not created', 'Error': errors})

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

@api_view(['GET'])
def get_layer_upload_task_response(request):
    task_id = request.query_params.get('task_id', None)
    result = AsyncResult(task_id, app=app)
    if result.ready():                     # check task state: true/false
        try:
            response, layer_id = result.get()
            if response == "successful":
                return Response({"message": response, "layer_id": layer_id}, status=200)
            else:
                return Response({"error": response, "layer_id": None}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e), "layer_id": None}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'message': "Please wait result"}, status=200)
