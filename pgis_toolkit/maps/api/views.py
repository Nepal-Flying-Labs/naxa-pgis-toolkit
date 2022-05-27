import json
import os
import shutil

import fiona
import geopandas
import pandas
from celery.result import AsyncResult
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.views.generic import DetailView, ListView
from requests import ReadTimeout
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from sqlalchemy import create_engine

from config.settings.base import MEDIA_ROOT, env
from pgis_toolkit.celery_app import app
from pgis_toolkit.maps.functions import advance_filter_data, clear_dir
from pgis_toolkit.maps.models import (
    FeatureCollection,
    Layer,
    LayerFile,
    LayerGroup,
    RasterLayer,
    SubLayer,
    Theme,
    Vectorlayer,
    WMSLayer,
)
from pgis_toolkit.maps.tasks import (
    UpdateRasterLayer,
    UpdateVectorLayer,
    UploadRasterLayer,
    UploadVectorLayer,
    UploadWMSLayer,
)
from pgis_toolkit.utils.vectortile import BaseVectorTileView, LayerMVTView

from .serializers import (
    LayerSerializer,
    LayerUpdateSerializer,
    SubLayerListSerializer,
    SubLayerSerializer,
    SubLayerUpdateSerializer,
    ThemeListSerializer,
    ThemeSerializer,
    WMSLayerSerializer,
)


@api_view(['GET'])
def project_layers(request,id):
    '''
    http://0.0.0.0:8000/api/maps/project_layers/<project_id>/
    This API is for the left bar of the map page
    '''
    try:
        theme_list=[]
        theme_qs=Theme.active.select_related('project').filter(project=id).order_by('order')
        for theme in theme_qs:
            group_list=[]
            group_qs=LayerGroup.active.select_related('theme').filter(theme=theme.id).order_by("order")
            for group in group_qs:
                group_layer_list=[]
                group_layer_qs=Layer.active.select_related('group').filter(group=group.id).order_by('order')
                for layer in group_layer_qs:
                    layer_item={"id":layer.id,"name":layer.name,'layer_type':layer.layer_type}
                    if layer.layer_type=="Vector":
                        layer_detail_instance=Vectorlayer.objects.select_related('layer').get(layer=layer.id)
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
            layer_qs=Layer.active.select_related('theme').filter(theme=theme.id,group=None).order_by('order')
            for layer in layer_qs:
                layer_item={"id":layer.id,"name":layer.name,'layer_type':layer.layer_type}
                if layer.layer_type=="Vector":
                    # print(layer.id,layer.layer_type)
                    layer_detail_instance=Vectorlayer.objects.select_related('layer').get(layer=layer.id)
                    sub_layer_list=[]
                    sub_layer_qs=SubLayer.active.select_related('layer').filter(layer=layer.id)
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
    def get_object(self, pk):
        try:
            return Layer.objects.get(pk=pk)
        except Layer.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        '''
        http://0.0.0.0:8000/api/maps/layer/<layer_id>/
        '''
        try:
            if not pk:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'error occured', 'error': "pk is missing"})
            layer_instance = self.get_object(pk)
            results={}
            '''layer detail'''
            layer_keys=['id','name','default_load','layer_type','is_osm_layer']
            for key in layer_keys:
                results[key]=layer_instance.__dict__[key]
            results['theme']=layer_instance.theme.id if layer_instance.theme else None
            results['group']=layer_instance.group.id if layer_instance.group else None

            '''Corressponding layer detail'''
            if layer_instance.layer_type=="Vector":
                vector_layer_instance=Vectorlayer.objects.select_related('layer').get(layer=layer_instance.id)
                vector_layer_keys=['geom_type', 'bbox','sub_layers_mapping_field', 'style', 'icon', 'icon_size', 'show_label', 'label_field', 'label_style']
                for key in vector_layer_keys:
                    results[key]=vector_layer_instance.__dict__[key]
            elif layer_instance.layer_type=="Raster":
                raster_layer_instance=RasterLayer.objects.select_related('layer').get(layer=layer_instance.id)
                raster_layer_keys=['geoserver_workspace', 'geoserver_layer_name']
                for key in raster_layer_keys:
                    results[key]=raster_layer_instance.__dict__[key]
            elif layer_instance.layer_type=="WMS":
                wms_layer_instance=WMSLayer.objects.select_related('layer').get(layer=layer_instance.id)
                wms_layer_keys=['url']
                for key in wms_layer_keys:
                    results[key]=wms_layer_instance.__dict__[key]
            return Response(results,status=200)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'error occurred', 'error': str(e)})

    def post(self, request, format=None):
        errors=[]
        try:
            request_dict = request.data
            request_dict._mutable = True
            name = request_dict['name'] if 'name' in request_dict.keys() else None
            if Layer.active.filter(name=name).exists():
                return Response(data={'message': 'Cannot create duplicate layer names.'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = LayerSerializer(data=request_dict)
            if serializer.is_valid():
                created_object = serializer.save()
                layer_type = created_object.layer_type
                if layer_type == "Vector":
                    '''handle Vector layer upload'''
                    if 'file' in request.FILES and request.FILES.get('file') != "":
                        layer_file_instance = LayerFile.objects.create(
                            file=request.FILES['file'],layer=created_object)
                    else:
                        Layer.objects.filter(id=created_object.id).delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'error occured', 'error': "File is missing"})
                    request_dict.pop('file')
                    response=UploadVectorLayer.delay(created_object.id,request_dict)
                    # return Response(response)
                    return Response(status=200,
                                    data={'message': 'Uploading Data', 'task_id': response.task_id})

                elif layer_type == "Raster":
                    '''handle Raster layer upload'''
                    if 'file' in request_dict.keys() and request_dict['file'] != "":
                        LayerFile.objects.create(file=request_dict['file'], layer=created_object)
                    else:
                        Layer.objects.filter(id=created_object.id).delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'error occured', 'error': "File is missing"})
                    request_dict.pop('file')
                    response = UploadRasterLayer.delay(created_object.id, request_dict)
                    # return Response(response)
                    return Response(status=200,
                                    data={'message': 'Uploading Data', 'task_id': response.task_id})

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
        errors=[]
        try:
            request_dict = request.data
            request_keys = request_dict.keys()
            name = request_dict['name'] if 'name' in request_keys else None
            layer_instance=Layer.active.get(pk=pk)
            project_id=layer_instance.theme.project.id
            if Layer.active.exclude(pk=pk).filter(theme__project=project_id,name=name).exists():
                return Response(data={'message': 'Cannot create duplicate layer names with in project.'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = LayerUpdateSerializer(layer_instance, data=request_dict, partial=True)
            if serializer.is_valid():
                created_object = serializer.save()
                layer_type = layer_instance.layer_type
                '''handle Vector layer update'''
                if layer_type == "Vector":
                    response=UpdateVectorLayer(layer_instance,request_dict)
                    if response=="successful":
                        return Response(data={'message':response},status=200)
                    else:
                        return Response(data={'message': 'error occured',"error":response},status=status.HTTP_400_BAD_REQUEST)

                    '''handle Vector layer update'''
                elif layer_type == "Raster":
                    response = UpdateRasterLayer.delay(pk, request_dict)
                    return Response(status=200, data={'message': 'Uploading Data', 'task_id': response.task_id})
                    '''handle Vector layer upload'''
                elif layer_type == "WMS":
                    if 'url' in request_keys and request_dict['url'] != "":
                        wms_instance = WMSLayer.objects.get(layer__id=pk)
                        wms_instance.url = request_dict['url']
                        wms_instance.save()
                else:
                    return Response(data={'message': 'Invalid Layer Type. Choices are: Vector, Raster and WMS'},status=status.HTTP_400_BAD_REQUEST)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
        except Exception as e:
            errors.append({'errorName': str(e), 'details': str(e)})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})


class SubLayerViewset(viewsets.ModelViewSet):
    '''A viewset to get and update Sublayer instance'''
    queryset = SubLayer.objects.all()
    http_method_names = ['get', 'patch']
    default_serializer_class = SubLayerSerializer

    serializer_classes = {
        'list': SubLayerListSerializer,
        'partial_update':SubLayerUpdateSerializer
    }

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def list(self, request, *args, **kwargs):
        layer_id = request.query_params.get('layer', None)
        if not layer_id:
            return Response(data={'message': 'params layer is missing'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.queryset.filter(layer=layer_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


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


'''A viewset to create and update Theme objects.'''
class ThemeViewset(viewsets.ModelViewSet):
    queryset = Theme.active.all()
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = ThemeSerializer

    serializer_classes = {
        'list': ThemeListSerializer,
        'retrieve': ThemeSerializer
    }

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def create(self, request, *args, **kwargs):
        errors = []
        try:
            name = request.data.get('name', None)
            project = request.data.get('project', None)
            if Theme.active.filter(Q(project__id=project) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate theme name for the project.'},status=status.HTTP_400_BAD_REQUEST)
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
        except Exception as e:
            errors.append({'errorName': str(e), 'details': str(e)})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'Message': 'Dataset not created', 'Error': errors})

    def partial_update(self, request, pk=None, *args, **kwargs):
        errors = []
        request_dict = request.data
        request_keys = request_dict.keys()
        theme_instance = Theme.active.get(pk=pk)
        if 'project' in request_keys and request_dict['project'] != "":
            project = request_dict['project']
        else:
            project = theme_instance.project.id
        if 'name' in request_keys and request_dict['name'] != "":
            name = request_dict['name']
            if Theme.active.filter(Q(project__id=project) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate theme name for the project.'},status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(theme_instance, request_dict, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        else:
            for er in serializer._errors:
                errors.append(
                    {'errorName': er, 'details': serializer._errors[er][0]})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})

    def list(self, request, *args, **kwargs):
        project = request.query_params.get('project', None)
        if not project:
            return Response(data={'message': 'params project is missing'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.queryset.filter(project__id=project)
        serializer = self.get_serializer(queryset, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


def reorder_item(table_name,data):
    try:
        if table_name=="theme":
            model=Theme
        else:
            return "Invalid params table"
        for key, value in data.items():
            instance = model.objects.get(id=key)
            instance.order = value
            instance.save()
        return "successful"
    except Exception as e:
        return Response(str(e))

@api_view(['POST'])
def reorder(request):
    '''
    http://0.0.0.0:8000/api/maps/reorder/?table=theme
    '''
    try:
        table = request.query_params.get('table', None)
        if not table:
            return Response(data={'message': 'error occured','error':"params table is missing"}, status=status.HTTP_400_BAD_REQUEST)
        if request.data:
            response=reorder_item(table,request.data)
            if not response=="successful":
                return Response(data={'message': 'error occured','error':response}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': "successful"}, status=200)
    except Exception as e:
        return Response(data={'message': 'error occured','error':str(e)}, status=status.HTTP_400_BAD_REQUEST)


'''VectorTile Generation for Maps Layer'''
class LayerVectorTileQuerySet(LayerMVTView, DetailView):
    '''
    url:"http://0.0.0.0:8000/api/maps/layer_vectortile/{z}/{x}/{y}/?layer=&sub_layer=",
    '''
    vector_tile_layer_name = None
    vector_tile_fields = ('pk','layer','attributes')

    def get(self, request, *args, **kwargs):
        queryset=FeatureCollection.objects.all()
        request_keys = request.GET.keys()
        '''filter by layer id'''
        if 'layer' not in request_keys or request.GET['layer'] == "":
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        layer_id=request.GET['layer']
        queryset=queryset.filter(layer=layer_id)

        if 'sub_layer' in request_keys and request.GET['sub_layer'] != "":
            sub_layer_id=request.GET['sub_layer']
            queryset=queryset.filter(sub_layer=sub_layer_id)
        self.vector_tile_queryset = queryset.distinct()
        return BaseVectorTileView.get(self, request=request, z=kwargs.get('z'), x=kwargs.get('x'), y=kwargs.get('y'))

'''VectorTile Generation for Advance Filter Layer'''

class AdvanceFilterVectorTileQuerySet(LayerMVTView, DetailView):
    #http://localhost:8000/api/maps/advance_filter_vectortile/{z}/{x}/{y}/?layer_id=200&expression=[{"field":"Tap","operator":1,"value":"सकिने"},{"join":"OR"},{"field":"Name","operator":1,"value":"Balmiki Secondary School"}]

    vector_tile_layer_name = None
    vector_tile_fields = ('pk', 'layer', 'attributes')

    def get(self, request, *args, **kwargs):
        if not request.GET.keys():
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        request_keys = request.GET.keys()
        if 'layer_id' not in request_keys or request.GET['layer_id'] == "" or 'expression' not in request_keys or request.GET['expression'] == "":
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        layer_id = request.GET['layer_id']
        if not Layer.active.filter(id=layer_id).exists():
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        layer_instance = Layer.objects.get(id=layer_id)
        expr_params = request.GET['expression']
        operator_list = {1: "equal_to", 2: "less_than", 3: "greater_than", 4: "not_equal_to",
                         5: "less_than_or_equal_to", 6: "greater_than_or_equal_to", 7: "like"}
        if layer_id and expr_params:
            expressions = json.loads(expr_params)
            join = ''
            dataset = FeatureCollection.active.filter(layer=int(layer_id))
            result_dataset = []
            for expr in expressions:
                if 'join' not in expr.keys():
                    field = expr['field']
                    operator = expr['operator']
                    value = expr['value']
                    if join == "OR":
                        OR_dataset = advance_filter_data(
                            field, operator, value, dataset)
                        result_dataset = result_dataset | OR_dataset
                    elif join == "AND":
                        result_dataset = advance_filter_data(
                            field, operator, value, result_dataset)
                    else:
                        result_dataset = advance_filter_data(
                            field, operator, value, dataset)
                else:
                    join = expr['join']
        if result_dataset is None:
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        self.vector_tile_queryset = result_dataset.distinct()
        return BaseVectorTileView.get(self, request=request, z=kwargs.get('z'), x=kwargs.get('x'), y=kwargs.get('y'))

'''download vectort data in popular formats'''
@api_view(['GET'])
def layer_download(request):
    '''
    http://localhost:8000/api/maps/layer_download/?layer_id=200&output_format=shapefile
    choices:'shapefile', 'geojson', 'csv', 'kml', 'gpx'
    '''
    layer_id = request.query_params.get('layer_id', None)
    output_format = request.query_params.get('output_format', None)
    output_format_choices = ['shapefile', 'geojson', 'csv', 'kml', 'gpx']
    '''ensuring request is valid'''
    if not layer_id or layer_id == "" or not output_format or output_format == "":
        return Response(data={'message': 'layer_id and output format params are compulsory.'}, status=status.HTTP_400_BAD_REQUEST)
    if output_format not in output_format_choices:
        return Response(data={'message': 'Unsupported format. Only shapefile, geojson, csv, kml and gpx are supported.'}, status=status.HTTP_400_BAD_REQUEST)
    if not Layer.active.filter(id=layer_id).exists():
        return Response(data={'message': 'The layer_id matching query does not exist!'}, status=status.HTTP_400_BAD_REQUEST)
    layer_instance = Layer.active.get(id=layer_id)
    if layer_instance.layer_type != "Vector":
        return Response(data={'message': 'Only vector layers are available for download!'}, status=status.HTTP_400_BAD_REQUEST)
    '''connect to database and pull required data'''
    try:
        dir = MEDIA_ROOT+"/../mediadownload/"
        db_connection_url = env("CONNECTION_DB", default="postgresql://xIDokAfQUYOjTGhErprxMHnjZTJXMloY:gn63GjyG9AOKLYgrvOcOZFrAeYgjLOA4IkjuTXzISZ3nnMaHxTX1rSxI0fdBSb52@postgres:5432/pgis_toolkit")
        con = create_engine(db_connection_url)
        sql = "SELECT id, geometry AS geom, attributes FROM maps_featurecollection WHERE layer_id=" + layer_id
        gdf = geopandas.read_postgis(sql, con)
        number_df = pandas.DataFrame(gdf['id'])
        attribute_df = pandas.DataFrame(gdf['attributes'].to_list())
        '''remove the attributes dictionary now'''
        gdf = gdf.drop(columns=['attributes'])
        attribute_number_df = pandas.concat([number_df, attribute_df], axis=1)
        gdf=gdf.merge(attribute_number_df, on='id')
        os.makedirs(dir, exist_ok=True)
        '''pack data in different formats'''
        if output_format == "shapefile":
            gdf.to_file(dir+layer_instance.name+".shp")
            # create a ZipFile
            zipfile_path = dir + f'{layer_instance.name}'
            files = dir
            shutil.make_archive(zipfile_path, 'zip', files)
            # zip file path
            file_url = dir + f'{layer_instance.name}.zip'
        elif output_format == "geojson":
            gdf.to_file(dir+layer_instance.name+".geojson", driver='GeoJSON')
            file_url = dir + f'{layer_instance.name}.geojson'
        elif output_format == "csv":
            geopandas.io.file.fiona.drvsupport.supported_drivers['CSV'] = 'raw'
            gdf.to_file(dir+layer_instance.name+".csv", driver='CSV', encoding='utf-8')
            # print(gdf.assign(geometry=gdf["geom"].apply(lambda p: p.wkt)).to_csv(), " is csv")
            file_url = dir + f'{layer_instance.name}.csv'
        elif output_format == "kml":
            geopandas.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'
            gdf.to_file(dir+layer_instance.name+".kml", driver='KML')
            file_url = dir + f'{layer_instance.name}.kml'
        elif output_format == "gpx":
            geopandas.io.file.fiona.drvsupport.supported_drivers['GPX'] = 'rw'
            gdf.to_file(dir + layer_instance.name+".gpx", driver='GPX', GPX_USE_EXTENSIONS='YES')
            file_url = dir + f'{layer_instance.name}.gpx'
            '''prompt download'''
        vector_file = open(file_url, 'rb')
        response = HttpResponse(vector_file, content_type='application/force-download')
        if output_format == "shapefile":
            response['Content-Disposition'] = 'attachment; filename="%s"' % f'{layer_instance.name}.zip'
        elif output_format == "geojson":
            response['Content-Disposition'] = 'attachment; filename="%s"' % f'{layer_instance.name}.geojson'
        elif output_format == "csv":
            response['Content-Disposition'] = 'attachment; filename="%s"' % f'{layer_instance.name}.csv'
        elif output_format == "kml":
            response['Content-Disposition'] = 'attachment; filename="%s"' % f'{layer_instance.name}.kml'
        elif output_format == "gpx":
            response['Content-Disposition'] = 'attachment; filename="%s"' % f'{layer_instance.name}.gpx'
        '''clearing the dir'''
        clear_dir(dir)
        return response
    except Exception as e:
        clear_dir(dir)
        return Response(status=404, data={'Error': str(e)})
