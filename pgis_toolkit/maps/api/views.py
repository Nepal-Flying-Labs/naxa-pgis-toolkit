import json
import operator
import os
import shutil
import time
from functools import reduce

import fiona
import geopandas
import pandas
import pandas as pd
from bson.json_util import dumps, loads
from celery.result import AsyncResult
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.serializers import serialize
from django.db import connection
from django.db.models import Count, F, Func, IntegerField, Q, Value
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView
from django_filters.rest_framework import DjangoFilterBackend
from requests import ReadTimeout
from rest_framework import filters, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from sequences import get_next_value
from sequences.models import Sequence
from sqlalchemy import create_engine

from config.settings.base import MEDIA_ROOT, MONGO_DB, env
from pgis_toolkit.celery_app import app, get_celery_worker_status
from pgis_toolkit.maps.models import (
    Analysis,
    Category,
    CeleryTask,
    CleaningErrors,
    FeatureCollection,
    FeatureCollectionMirror,
    Layer,
    LayerAttribute,
    LayerFile,
    LayerGroup,
    LayerStyle,
    NetworkRoutes,
    OptimumRoute,
    ProjectMapConfig,
    ProjectsLayerTemplate,
    ProjectsLayerTemplateAttribute,
    ProjectStyle,
    QueryFeatureCollection,
    QueryLayer,
    RasterLayer,
    StandardIcon,
    SubLayer,
    SubLayerStyle,
    Theme,
    Vectorlayer,
    WMSLayer,
)
from pgis_toolkit.maps.permissions import (
    FeatureCollectionPermission,
    FeatureGeoJSONPermission,
    ImportTemplatePermission,
    LayerAttributePermission,
    LayerDownloadPermission,
    LayerGroupPermission,
    LayerPermission,
    ProjectLayerTemplatePermission,
    ProjectMapConfigPermission,
    ProjectsLayerTemplateAttributePermission,
    ProjectStylePermission,
    ProjectThemeLayerPermission,
    QueryFeatureCollectionPermission,
    SubLayerPermission,
    ThemePermission,
)
from pgis_toolkit.maps.tasks import (
    CreateNetworkGraph,
    CreateNetworkGraphSystem,
    UpdateRasterLayer,
    UpdateVectorLayer,
    UploadRasterLayer,
    UploadVectorLayer,
    UploadWMSLayer,
    handleDataMergeUpdate,
)
from pgis_toolkit.maps.utils.advance_filter import advance_filter_data
from pgis_toolkit.maps.utils.buffer_analysis import (
    buffer_by_column_value,
    buffer_by_distance,
    find_data_within_buffer,
)
from pgis_toolkit.maps.utils.data_cleaning import (
    check_duplicate,
    check_multipart,
    check_null,
    check_overlapping,
    check_self_intersection,
    check_snapping,
    del_id_from_clean_instance,
    fix_duplicate,
    fix_multipart,
    fix_null,
    fix_overlapping,
    fix_self_intersection,
    fix_snapping,
)
from pgis_toolkit.maps.utils.functions import clear_dir
from pgis_toolkit.maps.utils.project_style import get_style_detail
from pgis_toolkit.projects.models import LayerTemplate, LayerTemplateAttribute, Project
from pgis_toolkit.utils.pagination import CustomPageNumberPagination
from pgis_toolkit.utils.vectortile import (
    BaseVectorTileView,
    LayerMVTView,
    NetworkRoutesMVTView,
)

from .serializers import (
    CleaningErrorsSerializer,
    FeatureCollectionListSerializer,
    FeatureCollectionMirrorSerializer,
    FeatureCollectionSerializer,
    LayerAttributeListSerializer,
    LayerAttributeSerializer,
    LayerGroupListSerializer,
    LayerGroupSerializer,
    LayerListSerializer,
    LayerSerializer,
    LayerUpdateSerializer,
    ProjectLayerTemplateListSerializer,
    ProjectLayerTemplateSerializer,
    ProjectsLayerTemplateAttributeListSerializer,
    ProjectsLayerTemplateAttributeSerializer,
    ProjectStyleListSerializer,
    ProjectStyleSerializer,
    QueryFeatureCollectionListSerializer,
    QueryFeatureCollectionSerializer,
    StandardIconListSerializer,
    SubLayerListSerializer,
    SubLayerRetrieveSerializer,
    SubLayerSerializer,
    SubLayerUpdateSerializer,
    ThemeListSerializer,
    ThemeSerializer,
    WMSLayerSerializer,
)

User = get_user_model()

class StandardIconViewset(viewsets.ModelViewSet):
    '''
    Viewset for Standard Icon Instance.
    '''
    queryset = StandardIcon.active.all()
    http_method_names = ['get']
    serializer_class = StandardIconListSerializer



class ProjectStyleViewset(viewsets.ModelViewSet):
    '''
    Viewset for multiple project style
    '''
    queryset = ProjectStyle.active.all()
    http_method_names = ['get','post','patch']
    permission_classes = [ProjectStylePermission]
    default_serializer_class = ProjectStyleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('project', )

    serializer_classes = {
        'list': ProjectStyleListSerializer,
    }

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def list(self, request, *args, **kwargs):
        try:
            project = request.query_params.get('project', None)
            if not project:
                return Response(data={'message': 'params project is missing'}, status=status.HTTP_400_BAD_REQUEST)
            self.queryset = self.filter_queryset(self.queryset)
            serializer = self.get_serializer(self.queryset, many=True)
            return Response(data=serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)

class LayerAttributeViewset(viewsets.ModelViewSet):
    '''
    Viewset for Layer Attribute
    '''
    queryset = LayerAttribute.objects.all()
    http_method_names = ['get']
    permission_classes = [LayerAttributePermission]
    default_serializer_class = LayerAttributeSerializer
    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ('layer', )

    serializer_classes = {
        'list': LayerAttributeListSerializer,
    }

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def list(self, request, *args, **kwargs):
        try:
            layer = request.query_params.get('layer', None)
            check_mandatory = request.query_params.get('check_mandatory', False)
            if not layer:
                return Response(data={'message': 'params layer is missing'}, status=status.HTTP_400_BAD_REQUEST)
            queryset = self.queryset.filter(layer=layer).values('id', 'name', 'alias', 'data_type')
            if check_mandatory == True or check_mandatory == 'True':
                mandatory_fields = Vectorlayer.objects.get(layer=layer).mandatory_fields
                if mandatory_fields:
                    for data in queryset:
                        data['mandatory'] = True if data['name'] in mandatory_fields else False
                else:
                    for data in queryset:
                        data['mandatory'] = True
            # serializer = self.get_serializer(self.queryset, many=True)
            return Response(data=queryset, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)
'''
#not in use
@api_view(['GET'])
def project_layers(request,id):

    # http://0.0.0.0:8000/api/maps/project_layers/<project_id>/
    # This view is for the left side bar of the map page (theme,layer,group,sublayer navigation)

    try:
        theme_list=[]
        theme_qs=Theme.active.select_related('project').filter(project=id).order_by('order')
        layer_queryset=Layer.active.select_related('theme','group').filter(theme__project=id).order_by('order')
        vector_layer_qs=Vectorlayer.objects.select_related('layer').filter(layer__theme__project=id)
        # vector_layer_qs=Vectorlayer.objects.select_related('layer').filter(layer__theme__project=id).values('id','layer','icon','icon_size','style')
        layer_group_queryset=LayerGroup.active.select_related('theme').filter(theme__project=id).order_by("order")
        for theme in theme_qs:
            group_list=[]
            group_qs=layer_group_queryset.filter(theme=theme.id).order_by("order")
            for group in group_qs:
                group_layer_list=[]
                group_layer_qs=layer_queryset.filter(group=group.id).order_by('order')
                for layer in group_layer_qs:
                    layer_item={"id":layer.id,"name":layer.name,'layer_type':layer.layer_type}
                    if layer.layer_type=="Vector":
                        layer_detail_instance=vector_layer_qs.get(layer=layer.id)
                        # layer_detail_instance=layer.vector_layer
                        icon_url=env("URL")+layer_detail_instance.icon.url if layer_detail_instance.icon else None
                        std_icon_url=env("URL")+layer_detail_instance.std_icon.icon.url if layer_detail_instance.std_icon else None
                        layer_item['icon']=icon_url
                        layer_item['std_icon']=std_icon_url
                        layer_item['icon_size']=layer_detail_instance.icon_size
                        layer_item['style']=layer_detail_instance.style

                    # elif layer.layer_type=="Raster":
                    #     layer_detail_instance=RasterLayer.objects.get(layer=layer.id)
                    # elif layer.layer_type=="WMS":
                    #     layer_detail_instance=WMSLayer.objects.get(layer=layer.id)
                    group_layer_list.append(layer_item)
                group_item={"id":group.id,"name":group.name,'layer':group_layer_list}
                group_list.append(group_item)

            layer_list=[]
            layer_qs=layer_queryset.filter(theme=theme.id,group=None).order_by('order')

            for layer in layer_qs:
                layer_item={"id":layer.id,"name":layer.name,'layer_type':layer.layer_type}
                if layer.layer_type=="Vector":
                    layer_detail_instance=vector_layer_qs.get(layer=layer.id)
                    sub_layer_list=[]
                    sub_layer_qs=SubLayer.active.select_related('layer').filter(layer=layer.id)
                    # sub_layer_qs=SubLayer.active.select_related('layer').filter(layer=layer.id).values('id','name','icon','icon_size','style')
                    for sub_layer in sub_layer_qs:
                        icon_url=env("URL")+sub_layer.icon.url if sub_layer.icon else None
                        std_icon_url=env("URL")+sub_layer.std_icon.icon.url if sub_layer.std_icon else None
                        sub_layer_item={"id":sub_layer.id,"name":sub_layer.name,'icon':icon_url,'std_icon':std_icon_url,'icon_size':sub_layer.icon_size,'style':sub_layer.style}
                        sub_layer_list.append(sub_layer_item)
                    icon_url=env("URL")+layer_detail_instance.icon.url if layer_detail_instance.icon else None
                    std_icon_url=env("URL")+layer_detail_instance.std_icon.icon.url if layer_detail_instance.std_icon else None
                    layer_item['icon']=icon_url
                    layer_item['std_icon']=std_icon_url
                    layer_item['icon_size']=layer_detail_instance.icon_size,
                    layer_item['style']=layer_detail_instance.style
                    layer_item['sub_layer']=sub_layer_list
                # elif layer.layer_type=="Raster":
                #     layer_detail_instance=RasterLayer.objects.get(layer=layer.id)
                # elif layer.layer_type=="WMS":
                #     layer_detail_instance=WMSLayer.objects.get(layer=layer.id)
                layer_list.append(layer_item)
            theme_item={"id":theme.id,'name':theme.name,'description':theme.description,'group':group_list,'layer':layer_list}
            theme_list.append(theme_item)
        return Response(theme_list)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': str(e)})
'''
# def get_style_detail(layer_id,sublayer_id,project_style):
#     icon,icon_size,style,std_icon=None,None,None,None
#     if sublayer_id:
#         if project_style=="default":
#             style_instance=SubLayerStyle.objects.filter(sub_layer=sublayer_id,project_style=None)
#             if not style_instance.exists():
#                 style_instance=LayerStyle.objects.filter(layer=layer_id,project_style=None)
#         else:
#             style_instance=SubLayerStyle.objects.filter(sub_layer=sublayer_id,project_style=project_style)
#             if not style_instance.exists():
#                 style_instance=SubLayerStyle.objects.filter(sub_layer=sublayer_id,project_style=None)
#                 if not style_instance.exists():
#                     style_instance=LayerStyle.objects.filter(layer=layer_id,project_style=None)
#     else:
#         if project_style=="default":
#             style_instance=LayerStyle.objects.filter(layer=layer_id,project_style=None)
#         else:
#             style_instance=LayerStyle.objects.filter(layer=layer_id,project_style=project_style)
#             if not style_instance.exists():
#                 style_instance=LayerStyle.objects.filter(layer=layer_id,project_style=None)
#     if style_instance.exists():
#         # icon_url=env("URL")+style_instance[0].icon.url if style_instance[0].icon else None
#         # std_icon_url=env("URL")+style_instance[0].std_icon.icon.url if style_instance[0].std_icon else None
#         icon=style_instance[0].get_icon_url
#         std_icon=style_instance[0].get_std_icon_url
#         icon_size=style_instance[0].icon_size
#         style=style_instance[0].style
#     return icon,icon_size,style,std_icon
@api_view(['GET'])
@permission_classes([ProjectThemeLayerPermission])
def project_theme_layers(request):
    '''
    layers list under project theme
    http://0.0.0.0:8000/api/maps/project_theme_layers/?theme=<id>&project_style=default
    This view is for the left side bar of the map page (theme,layer,group,sublayer navigation)
    '''
    try:
        options=[]
        theme_id=request.query_params.get("theme",None)
        project_style=request.query_params.get("project_style")
        if not project_style:
            project_style="default"
        if not theme_id:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': "params theme is missing"})

        layer_queryset=Layer.active.select_related('theme','group').filter(theme=theme_id, display_on_map=True).order_by('order')
        layer_group_queryset=LayerGroup.active.select_related('theme').filter(theme=theme_id).order_by("order")
        group_qs=layer_group_queryset.filter(theme=theme_id).order_by("order")
        for group in group_qs:
            group_layer_list=[]
            group_layer_qs=layer_queryset.filter(group=group.id).order_by('order').values('id','name','layer_type', 'upload_status', 'is_clean')
            for layer in group_layer_qs:
                layer_item=layer
                if layer['layer_type']=="Vector":
                    icon,style,std_icon=get_style_detail(layer['id'],None,project_style)
                    layer_item['icon']=icon
                    layer_item['std_icon']=std_icon
                    layer_item['style']=style
                    vector_layer = Vectorlayer.objects.filter(layer=layer['id'])
                    if vector_layer.exists():
                        layer_item['bbox'] = vector_layer[0].bbox
                        layer_item['geom_type'] = vector_layer[0].geom_type
                    else:
                        layer_item['bbox'] = []
                        layer_item['geom'] = ''
                    # layer_item['feature_count']=len(FeatureCollection.active.filter(layer=layer['id']))
                elif layer['layer_type']=='Raster':
                    raster_layer = RasterLayer.objects.filter(layer=layer['id'])
                    if raster_layer.exists():
                        layer_item['geoserver_workspace'] = raster_layer[0].geoserver_workspace
                        layer_item['geoserver_layer_name'] = raster_layer[0].geoserver_layer_name
                    else:
                        layer_item['geoserver_workspace'] = ''
                        layer_item['geoserver_layer_name'] = ''

                elif layer['layer_type']=='WMS':
                    wms_layer = WMSLayer.objects.filter(layer=layer['id']).values('url')
                    if wms_layer.exists():
                        layer_item['url'] = wms_layer[0]['url']
                    else:
                        layer_item['url'] = ''

                group_layer_list.append(layer_item)
            group_item={"id":group.id,"type":"group","name":group.name,'layer':group_layer_list}
            options.append(group_item)

        layer_qs=layer_queryset.filter(theme=theme_id,group=None).order_by('order').values('id','name','layer_type','upload_status', 'is_clean')
        for layer in layer_qs:
            layer_item=layer
            if layer['layer_type']=="Vector":
                sub_layer_list=[]

                sub_layer_qs=SubLayer.active.select_related('layer').filter(layer=layer['id']).values('id','name')
                for sub_layer in sub_layer_qs:
                    icon,style,std_icon=get_style_detail(layer['id'],sub_layer['id'],project_style)
                    sub_layer_item=sub_layer
                    sub_layer_item['icon']=icon
                    sub_layer_item['std_icon']=std_icon
                    sub_layer_item['style']=style
                    sub_layer = SubLayer.objects.filter(id=sub_layer['id'])
                    if sub_layer.exists():
                        sub_layer_item['bbox'] = sub_layer[0].bbox
                    else:
                        sub_layer_item['bbox'] = []
                    # sub_layer_item['feature_count']=len(FeatureCollection.active.filter(sub_layer=sub_layer['id']))
                    sub_layer_list.append(sub_layer_item)

                icon,style,std_icon=get_style_detail(layer['id'],None,project_style)
                layer_item['icon']=icon
                layer_item['std_icon']=std_icon
                layer_item['style']=style
                vector_layer = Vectorlayer.objects.filter(layer=layer['id'])
                if vector_layer.exists():
                    layer_item['bbox'] = vector_layer[0].bbox
                    layer_item['geom_type'] = vector_layer[0].geom_type
                else:
                    layer_item['bbox'] = []
                    layer_item['geom_type'] = ''
                # layer_item['feature_count']=len(FeatureCollection.active.filter(layer=layer['id']))
                layer_item['sub_layer']=sub_layer_list
            elif layer['layer_type']=='Raster':
                raster_layer = RasterLayer.objects.filter(layer=layer['id'])
                if raster_layer.exists():
                    layer_item['geoserver_workspace'] = raster_layer[0].geoserver_workspace
                    layer_item['geoserver_layer_name'] = raster_layer[0].geoserver_layer_name
                else:
                    layer_item['geoserver_workspace'] = ''
                    layer_item['geoserver_layer_name'] = ''

            elif layer['layer_type']=='WMS':
                wms_layer = WMSLayer.objects.filter(layer=layer['id']).values('url')
                if wms_layer.exists():
                    layer_item['url'] = wms_layer[0]['url']
                else:
                    layer_item['url'] = ''
            options.append(layer_item)
        return Response(options,status=200)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

class LayerViewSet(viewsets.ModelViewSet):
    queryset = Layer.active.all()
    http_method_names=['get','post', 'patch', 'delete']
    permission_classes=[LayerPermission]
    serializer_class=LayerSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['group', 'theme', 'status']
    search_fields = ['id', 'name']
    ordering_fields = ['id', 'name', 'source', 'status', 'display_on_map', 'layer_type', 'upload_status', 'geom_type', 'features', 'theme']
    # pagination_class = CustomPageNumberPagination

    '''
    View for Layer instance
    http://0.0.0.0:8000/api/maps/layer/
    '''
    # def get_object(self, pk):
    #     try:
    #         print(Layer.active.get(pk=pk),"Layer.active.get(pk=pk)")
    #         return Layer.active.get(pk=pk)
    #     except Layer.DoesNotExist:
    #         raise Http404
    def list(self, request, *args, **kwargs):
        try:
            # paginator = CustomPageNumberPagination()

            result = []
            project = request.query_params.get('project', None)
            ordering = request.query_params.get('ordering', None)
            if not project:
                return Response(data={'message': 'project params is required!'}, status=400)
            if not Project.active.filter(id=project).exists():
                return Response(data={'message': 'Project not found!'}, status=400)
            theme_ids = Theme.active.select_related('project').filter(project=project).values_list('id', flat=True)
            # layer_qs = Layer.objects.select_related('theme').filter(theme__in=theme_ids).values('id', 'name', 'source', 'status', 'display_on_map', 'layer_type', 'upload_status')
            layer_qs = Layer.active.select_related('theme').filter(theme__in=theme_ids).values('id', 'name', 'source', 'status', 'display_on_map', 'layer_type', 'upload_status').annotate(geom_type=F('vector_layer__geom_type')).annotate(theme=F('theme__name')).annotate(features=Count("layer_feature"))
            if not ordering:
                layer_qs = layer_qs.order_by('-id')
            layer_qs = self.filter_queryset(layer_qs)
            # for layer in layer_qs:
            #     layer_dict=layer
            #     if layer['layer_type']=='Vector':
            #         vector_layer = Vectorlayer.objects.filter(layer=layer['id']).values('geom_type')
            #         if vector_layer.exists():
            #             layer_dict['geom_type'] = vector_layer[0]['geom_type']
            #         feature_count = FeatureCollection.active.filter(layer=layer['id']).count()
            #         layer_dict['features'] = feature_count
            #     result.append(layer_dict)
            # if ordering and ordering=='features':
            #     result = sorted(result, key=lambda x:x[ordering])
            # elif ordering and ordering == '-features':
            #     result = sorted(result, key=lambda x:x['features'], reverse=True)
            ''''''
            # paginated_queryset = paginator.paginate_queryset(result, request)
            # return paginator.get_paginated_response(data=paginated_queryset)
            return Response(data=layer_qs, status=200)
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)

    def retrieve(self, request, pk=None):

        '''
        This action is to retrieve the layer detail
        http://0.0.0.0:8000/api/maps/layer/<layer_id>/
        '''
        # print(Group.objects.get(id=2).permissions.all().first().codename,"requestsssssssssssssssssssssss")
        try:
            if not pk:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': "pk is missing"})
            if not Layer.active.filter(pk=pk).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': "Layer does not exists"})

            # layer_instance = self.get_object(pk)
            layer_instance = Layer.active.get(pk=pk)
            results={}
            '''layer detail'''
            layer_keys=['id','name', 'source','display_on_map','default_load', 'status', 'layer_type', 'upload_status', 'is_osm_layer']
            for key in layer_keys:
                results[key]=layer_instance.__dict__[key]
            # results['category'] = layer_instance.category.id if layer_instance.category else None
            results['theme']=layer_instance.theme.id if layer_instance.theme else None
            results['group']=layer_instance.group.id if layer_instance.group else None

            '''Corressponding layer detail'''
            if layer_instance.layer_type=="Vector":
                vector_layer_instance=Vectorlayer.objects.select_related('layer').get(layer=layer_instance.id)
                vector_layer_keys=['geom_type', 'bbox','sub_layers_mapping_field', 'style', 'show_label', 'label_field', 'label_style']
                for key in vector_layer_keys:
                    results[key]=vector_layer_instance.__dict__[key]
                results['std_icon']=f"{env('BACKEND_URL')}{vector_layer_instance.std_icon.icon.url}" if vector_layer_instance.std_icon else None
                results['icon']=f"{env('BACKEND_URL')}{vector_layer_instance.icon.url}" if vector_layer_instance.icon else None
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
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def create(self, request, *args, **kwargs):
        errors=[]
        try:
            request_dict = request.data
            request_dict._mutable = True

            serializer = LayerSerializer(data=request_dict)
            if serializer.is_valid():
                '''verify whether layer name is unique within project or not'''
                name = request_dict['name'] if 'name' in request_dict.keys() else None
                theme_id = request_dict['theme'] if 'theme' in request_dict.keys() else None
                theme_instance = Theme.objects.get(id=theme_id) if theme_id else None
                project_id=Project.objects.get(id=theme_instance.project.id).id if theme_instance else None

                if not project_id:
                    return Response(data={'message': 'Theme can not be empty'}, status=status.HTTP_400_BAD_REQUEST)

                if Layer.active.filter(theme__project__id=project_id,name=name).exists():
                    return Response(data={'message': 'Cannot create duplicate layer names.'}, status=status.HTTP_400_BAD_REQUEST)

                created_object = serializer.save()
                layer_type = created_object.layer_type
                if layer_type == "Vector":
                    '''check whether celery is working or not'''
                    is_working=get_celery_worker_status()
                    if not is_working=="working":
                        Layer.objects.get(id=created_object.id).delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': "server error: celery is not working"})
                    '''handle Vector layer upload'''
                    if 'file' in request.FILES and request.FILES.get('file') != "":
                        layer_file_instance = LayerFile.objects.create(
                            file=request.FILES['file'],layer=created_object)
                    else:
                        Layer.objects.filter(id=created_object.id).delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': "File is missing"})
                    request_dict.pop('file')
                    '''wait untils the layer instance is created'''
                    iterate=True
                    while iterate:
                        if Layer.objects.filter(id=created_object.id).exists():
                            layer_instane=Layer.objects.get(id=created_object.id)
                            iterate=False
                        else:
                            print("sleeep time")
                            time.sleep(3)

                    print("reached here123")
                    response=UploadVectorLayer.delay(created_object.id,request_dict)
                    CeleryTask.objects.create(layer_id=created_object.id, task_id=response.task_id)
                    # return Response(response)
                    return Response(status=200,
                                    data={'message': 'Uploading Data', 'task_id': response.task_id, 'layer_id': created_object.id})

                elif layer_type == "Raster":
                    is_working=get_celery_worker_status()
                    if not is_working=="working":
                        Layer.objects.get(id=created_object.id).delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': "server error: celery is not working"})
                    '''handle Raster layer upload'''
                    if 'file' in request_dict.keys() and request_dict['file'] != "":
                        LayerFile.objects.create(file=request_dict['file'], layer=created_object)
                    else:
                        Layer.objects.filter(id=created_object.id).delete()
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'error occured', 'error': "File is missing"})
                    request_dict.pop('file')
                    '''wait untils the layer instance is created'''
                    iterate=True
                    while iterate:
                        if Layer.objects.filter(id=created_object.id).exists():
                            # layer_instane=Layer.objects.get(id=created_object.id)
                            iterate=False
                        else:
                            print("sleeep time")
                            time.sleep(3)

                    print("reached here123")
                    response = UploadRasterLayer.delay(created_object.id, request_dict)
                    CeleryTask.objects.create(layer_id=created_object.id, task_id=response.task_id)
                    # return Response(response)
                    return Response(status=200,
                                    data={'message': 'Uploading Data', 'task_id': response.task_id, 'layer_id': created_object.id})

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
                        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
                    created_object.upload_status='successful'
                    created_object.save()
                    return Response(data={'message': 'Layer Created', 'data': serializer.data}, status=status.HTTP_201_CREATED)
                else:
                    Layer.objects.get(id=created_object.id).delete()
                    return Response(data={'message': 'Invalid Layer Type. Choices are: Vector, Raster and WMS'})
                # return Response(data={'message': 'Layer Created', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def partial_update(self, request, pk=None):
        errors=[]
        try:
            request_dict = request.data
            request_keys = request_dict.keys()
            name = request_dict['name'] if 'name' in request_keys else None
            layer_instance=Layer.active.get(pk=pk)
            project_id=layer_instance.theme.project.id
            group_id = None
            if Layer.active.exclude(pk=pk).filter(theme__project=project_id,name=name).exists():
                return Response(data={'message': 'Cannot create duplicate layer names with in project.'}, status=status.HTTP_400_BAD_REQUEST)
            serializer = LayerUpdateSerializer(layer_instance, data=request_dict, partial=True)
            if serializer.is_valid():
                created_object = serializer.save()
                layer_type = layer_instance.layer_type
                '''handle Vector layer update'''
                if layer_type == "Vector":
                    project_style="default"
                    if "project_style" in request_dict and request_dict['project_style']!='' and request_dict['project_style']!='default':
                        project_style=request_dict['project_style']
                    request_dict._mutable=True
                    request_dict['project_style']=project_style
                    response, update_dict=UpdateVectorLayer(layer_instance,request_dict)
                    if response=="successful":
                        data={'message':response,"id":serializer.data['id'],'theme':serializer.data['theme'], "group": serializer.data['group']}
                        data.update(update_dict)
                        return Response(data=data,status=200)
                    else:
                        return Response(data={'message': 'error occured',"error":response},status=status.HTTP_400_BAD_REQUEST)

                    '''handle Vector layer update'''
                elif layer_type == "Raster":
                        # is_working=get_celery_worker_status()
                        # if not is_working=="working":
                        #     return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': "server error: celery is not working"})
                        # response = UpdateRasterLayer.delay(pk, request_dict)
                        # return Response(status=200, data={'message': 'Uploading Data', 'task_id': response.task_id})
                        response = UpdateRasterLayer(pk, request_dict)
                        if response=="successful":
                            data={'message':response,"id":serializer.data['id'],'theme':serializer.data['theme'], "group": serializer.data['group']}
                            return Response(data=data,status=200)
                        else:
                            return Response(data={'message': response},status=status.HTTP_400_BAD_REQUEST)

                        '''handle Vector layer upload'''
                elif layer_type == "WMS":
                    wms_instance = WMSLayer.objects.get(layer__id=pk)
                    if 'url' in request_keys and request_dict['url'] != "":
                        wms_instance.url = request_dict['url']
                        wms_instance.save()
                        # if layer_instance.group:
                        #     group_id = layer_instance.group.id
                    return Response(data={'message':"successful", "id":serializer.data['id'], "group":serializer.data['group'], "theme": serializer.data['theme'], "url": wms_instance.url},status=200)
                else:
                    return Response(data={'message': 'Invalid Layer Type. Choices are: Vector, Raster and WMS'},status=status.HTTP_400_BAD_REQUEST)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            layer_type=instance.layer_type
            '''delete layer'''
            self.perform_destroy(instance)
            if layer_type=="Vector":
                Vectorlayer.objects.filter(layer=instance.id).delete()
                FeatureCollection.objects.filter(layer=instance).delete()
                LayerAttribute.objects.filter(layer=instance).delete()
                LayerFile.objects.filter(layer=instance).delete()
                LayerStyle.objects.filter(layer=instance).delete()
            elif layer_type=="Raster":
                RasterLayer.objects.filter(layer=instance.id).delete()
                LayerFile.objects.filter(layer=instance).delete()
            elif layer_type=="WMS":
                WMSLayer.objects.filter(layer=instance).delete()

        except Http404:
            return Response(status=status.HTTP_204_NO_CONTENT, data={'message': 'Not Found'})
        return Response(status=status.HTTP_200_OK, data={'message': 'Layer Data deleted'})

class SubLayerViewset(viewsets.ModelViewSet):
    '''A viewset to get and update Sublayer instance'''
    queryset = SubLayer.objects.all()
    http_method_names = ['get', 'patch']
    default_serializer_class = SubLayerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('layer', )
    permission_classes=[SubLayerPermission]

    serializer_classes = {
        'list': SubLayerListSerializer,
        'retrieve': SubLayerRetrieveSerializer,
        'partial_update':SubLayerUpdateSerializer
    }

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def list(self, request, *args, **kwargs):
        layer_id = request.query_params.get('layer', None)
        project_style=request.query_params.get("project_style")
        if not project_style:
            project_style="default"
        if not layer_id:
            return Response(data={'message': 'params layer is missing'}, status=status.HTTP_400_BAD_REQUEST)
        # queryset = self.queryset.filter(layer=layer_id)
        self.queryset=self.filter_queryset(self.queryset)
        serializer = self.get_serializer(self.queryset, many=True,context={"project_style":project_style,"layer_id":layer_id})
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        project_style=request.query_params.get("project_style")
        if not project_style:
            project_style="default"
        sub_layer = get_object_or_404(self.queryset, pk=pk)
        serializer = self.get_serializer(sub_layer,context={"project_style":project_style,"layer_id":sub_layer.layer.id})
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        errors=[]
        try:
            request_dict = request.data
            request_keys = request_dict.keys()
            # name = request_dict['name'] if 'name' in request_keys else None
            sub_layer_instance=SubLayer.active.get(pk=pk)
            project_style="default"
            if "project_style" in request_dict and request_dict['project_style']!='' and request_dict['project_style']!='default':
                project_style=request_dict['project_style']
            request_dict._mutable=True
            request_dict['project_style']=project_style

            serializer = self.get_serializer(sub_layer_instance, data=request_dict, partial=True)
            if serializer.is_valid():
                created_object = serializer.save()
                project_style=None if request_dict['project_style']=="default" else request_dict['project_style']
                style_qs=SubLayerStyle.objects.filter(sub_layer=sub_layer_instance.id,project_style=project_style)

                if style_qs.exists():
                    sub_layer_style_instance=style_qs[0]
                else:
                    project_style_instance=ProjectStyle.active.get(id=project_style) if project_style else None
                    sub_layer_style_instance=SubLayerStyle.objects.create(sub_layer=sub_layer_instance,project_style=project_style_instance)
                if 'icon' in request_dict.keys():
                    sub_layer_style_instance.icon=request_dict['icon']
                # if 'icon_size' in request_dict.keys():
                #     sub_layer_style_instance.icon_size=json.loads(request_dict['icon_size'])
                if 'style' in request_dict.keys():
                    sub_layer_style_instance.style=json.loads(request_dict['style'])
                if 'std_icon' in request_dict.keys():
                    sub_layer_style_instance.std_icon=StandardIcon.objects.get(id=request_dict['std_icon']) if request_dict['std_icon'] else None
                sub_layer_style_instance.save()
                icon = f'{env("BACKEND_URL")}{sub_layer_style_instance.icon.url}' if sub_layer_style_instance.icon else None
                style = sub_layer_style_instance.style
                std_icon = f'{env("BACKEND_URL")}{sub_layer_style_instance.std_icon.icon.url}' if sub_layer_style_instance.std_icon else None
                return Response(data={"message":"successful","id":serializer.data['id'],'layer':sub_layer_instance.layer.id,'theme':sub_layer_instance.layer.theme.id, 'icon': icon, 'style': style, 'std_icon': std_icon},status=200)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})


# @api_view(['GET'])
# def get_layer_upload_task_response(request):
#     '''
#     View to get the response of aynchronous task run for vector and raster layer upload
#     '''
#     try:
#         task_id = request.query_params.get('task_id', None)
#         result = AsyncResult(task_id, app=app)
#         if result.ready():   # check task state: true/false
#             try:
#                 response, layer_id = result.get()
#                 if response == "successful":
#                     layer_instance=Layer.active.get(id=int(layer_id))
#                     theme_id=layer_instance.theme.id if layer_instance.theme else None
#                     group_id = layer_instance.group.id if layer_instance.group else None
#                     return Response({"message": response, "layer_id": layer_id,"name":layer_instance.name,"theme":theme_id, "group": group_id}, status=200)
#                 else:
#                     return Response({"error": response, "layer_id": None}, status=status.HTTP_400_BAD_REQUEST)
#             except Exception as e:
#                 return Response({"error": str(e), "layer_id": None}, status=status.HTTP_400_BAD_REQUEST)
#         return Response({'message': "Please wait result"}, status=200)
#     except Exception as e:
#         return Response({"error": str(e), "layer_id": None}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_layer_upload_task_response(request):
    '''
    View to get the response of aynchronous task run for vector and raster layer upload
    '''
    try:
        layer_id = int(request.query_params.get('layer', None))
        task_qs= CeleryTask.objects.filter(layer_id=layer_id)
        if not task_qs.exists():
            return Response({'message': 'Task not found for the layer'}, status=400)
        task_id = task_qs[0].task_id
        result =  AsyncResult(task_id, app=app)
        if result.ready():
            response, layer_id = result.get()
            # if response == "successful":
            #     layer_instance=Layer.active.get(id=int(layer_id))
            #     theme_id=layer_instance.theme.id if layer_instance.theme else None
            #     group_id = layer_instance.group.id if layer_instance.group else None
            #     return Response({"message": response, "layer_id": layer_id,"name":layer_instance.name,"theme":theme_id, "group": group_id}, status=200)
            # else:
            if response != "successful":
                if isinstance(response, list):
                    response=response[0]
                elif isinstance(response, dict):
                    response=list(response.values())[0]
                return Response(data=response, status=200)
        else:
            return Response({'message': "Please wait result"}, status=200)


        # result = AsyncResult(layer_id, app=app)
        # if result.ready():   # check task state: true/false
        #     try:
        #         response, layer_id = result.get()
        #         if response == "successful":
        #             layer_instance=Layer.active.get(id=int(layer_id))
        #             theme_id=layer_instance.theme.id if layer_instance.theme else None
        #             group_id = layer_instance.group.id if layer_instance.group else None
        #             return Response({"message": response, "layer_id": layer_id,"name":layer_instance.name,"theme":theme_id, "group": group_id}, status=200)
        #         else:
        #             return Response({"error": response, "layer_id": None}, status=status.HTTP_400_BAD_REQUEST)
        #     except Exception as e:
        #         return Response({"error": str(e), "layer_id": None}, status=status.HTTP_400_BAD_REQUEST)
        # return Response({'message': "Please wait result"}, status=200)
    except Exception as e:
        return Response({"error": str(e), "layer_id": None}, status=status.HTTP_400_BAD_REQUEST)

class ThemeViewset(viewsets.ModelViewSet):
    '''
    Viewset for Theme instance.
    '''
    queryset = Theme.active.all().order_by('order')
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = ThemeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('project', )
    permission_classes=[ThemePermission]
    serializer_classes = {
        'list': ThemeListSerializer,
        # 'retrieve': ThemeSerializer
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
                # '''updating order'''
                # theme_qs=Theme.active.filter(project__id=project)
                # for theme in theme_qs:
                #     theme.order+=1
                #     theme.save()
                return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def partial_update(self, request, pk=None, *args, **kwargs):
        try:
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
                if Theme.active.exclude(id=pk).filter(Q(project__id=project) & Q(name=name)).exists():
                    return Response(data={'message': 'Cannot create duplicate theme name for the project.'},status=status.HTTP_400_BAD_REQUEST)
            serializer = self.get_serializer(theme_instance, request_dict, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def list(self, request, *args, **kwargs):
        project = request.query_params.get('project', None)
        if not project:
            return Response(data={'message': 'params project is missing'}, status=status.HTTP_400_BAD_REQUEST)
        queryset=self.filter_queryset(self.queryset)
        queryset =queryset.order_by('order')
        # queryset = self.queryset.filter(project__id=project)
        serializer = self.get_serializer(queryset, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


def reorder_item(table_name,data):
    try:
        models={'theme':Theme,'layer':Layer}
        try:
            model=models[table_name]
        except:
            return "Invalid params table"
        instances=[]
        for key, value in data.items():
            instance = model.objects.get(id=key)
            instances += [instance]
            instance.order = value

        '''update order in bulk'''
        model.objects.bulk_update(instances, ['order'])
        return "successful"
    except Exception as e:
        return str(e)

@api_view(['POST'])
def reorder(request):
    '''
    General functional view to manage ordering
    table=theme or layer
    http://0.0.0.0:8000/api/maps/reorder/?table=theme
    '''
    try:
        table = request.query_params.get('table', None)
        if not table:
            return Response(data={'message': 'error occured','error':"params table is missing"}, status=status.HTTP_400_BAD_REQUEST)
        if request.data:
            response=reorder_item(table,request.data)
            if not response=="successful":
                return Response(data={'message': response}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': "successful"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LayerVectorTileQuerySet(LayerMVTView, DetailView):
    '''
    VectorTile Generation for Maps Layer
    url:"http://0.0.0.0:8000/api/maps/layer_vectortile/{z}/{x}/{y}/?layer=&sub_layer=",
    '''
    vector_tile_layer_name = None
    vector_tile_fields = ('pk','layer')

    def get(self, request, *args, **kwargs):
        '''Authentication'''
        auth = request.headers['Authorization']
        token = auth.split()[1]
        try:
            '''if JWT authentication'''
            user_id = AccessToken(token)['user_id']
        except:
            '''if token authentication'''
            auth_token = Token.objects.get(key=token)
            user_id = auth_token.user_id
        if not User.active.filter(id=user_id).exists():
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
        queryset=FeatureCollection.active.all()
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

'''{{baseURL}}api/maps/advance_query/
    layer=102
    expression=[{"field":"OBJECTID","operator":1,"value":6262},{"join":"OR"},{"field":"OBJECTID","operator":1,"value":6263}]'''
class AdvanceQueryAPIView(APIView):
    def get(self, request, *args, **kwargs):
        '''{{baseURL}}api/maps/advance_query/?layer=1&field=DISTRICT'''
        try:
            layer_id = request.query_params.get('layer', None)
            field = request.query_params.get('field', None)
            if layer_id and field:
                feature_qs = FeatureCollection.active.filter(layer=int(layer_id))
                values = []
                attrbue_keys = feature_qs[0].attributes.keys()
                for feature in feature_qs:
                    value=feature.attributes[field]
                    if field in attrbue_keys and value not in values:
                        values.append(value)
                return Response (data=values, status=200)
            elif layer_id:
                layer = Layer.active.get(id=layer_id)
                if LayerAttribute.objects.filter(layer=layer_id).exists():
                    attribute_qs=LayerAttribute.objects.filter(layer=layer_id).values('name', 'alias')
                    return Response (data=attribute_qs, status=200)
                else:
                    return Response(data={'message': 'LayerAttributes not found for the layer'}, status=400)
            else:
                return Response(data={'message': 'layer or field params is missing!'}, status=400)
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)

    def post(self, request, *args, **kwargs):
        try:
            errors=[]
            feature_ids=[]
            layer_id = int(request.data.get('layer', None))
            expr_params = request.data.get('expression', None)
            operator_list = {1: "equal_to", 2: "less_than", 3: "greater_than", 4: "not_equal_to",
                            5: "less_than_or_equal_to", 6: "greater_than_or_equal_to", 7: "like"}
            query_layer = None
            if layer_id and expr_params:
                layer = Layer.active.get(id=layer_id)
                vector_layer = Vectorlayer.objects.get(layer=layer_id)
                name = request.data.get('name', None)
                display_on_map = request.data.get('display_on_map', True)
                if not name or name == "":
                    return Response(data={'message': "QueryLayer name field is required"}, status=400)
                # if QueryLayer.active.filter(name=name, theme=layer.theme).exists():
                #     return Response(data={'message': 'QueryLayer name cannot be duplicate.'}, status=400)
                expressions = json.loads(expr_params)
                join = ''
                query={}
                for expr in expressions:
                    if 'join' not in expr.keys():
                        field = expr['field']
                        operator = expr['operator']
                        value = expr['value']
                        if join == "OR":
                            OR_query = advance_filter_data(layer_id,
                                field, operator, value)
                            if query:
                                query = { "$or" : [query, OR_query] }
                        elif join == "AND":
                            AND_query = advance_filter_data(layer_id,
                                field, operator, value)
                            query = { "$and" : [query, AND_query] }
                        else:

                            query = advance_filter_data(layer_id,
                                field, operator, value)
                    else:
                        join = expr['join']
                feature_coll = MONGO_DB['featurecollections']
                result = feature_coll.find(query, {"id":1, "_id":0})
                json_data = json.loads(dumps(result))
                count = len(json_data)
                if count == 0:
                    return Response (data={'features_count': 0}, status=200)
                query_layer = QueryLayer.objects.create(name=name, display_on_map=display_on_map, theme=layer.theme, group=layer.group, source=layer.source, geom_type=vector_layer.geom_type)
                if count == 1:
                    feature_ids = json_data[0]['id']
                    raw_query=f"INSERT INTO maps_queryfeaturecollection (layer_id, is_deleted, attributes, geometry) (SELECT {query_layer.id} AS layer_id , is_deleted, attributes, geometry FROM maps_featurecollection WHERE id = {feature_ids})"
                    bbox_query = f"SELECT ST_Extent(geometry) AS bbox FROM maps_featurecollection WHERE id = {feature_ids}" #faster
                else:
                    feature_ids = ()
                    for data in json_data:
                        feature_ids = feature_ids + (data['id'],)
                    raw_query=f"INSERT INTO maps_queryfeaturecollection (layer_id, is_deleted, attributes, geometry) (SELECT {query_layer.id} AS layer_id , is_deleted, attributes, geometry FROM maps_featurecollection WHERE id IN {feature_ids})"
                    bbox_query = f"SELECT ST_Extent(geometry) AS bbox FROM maps_featurecollection WHERE id IN {feature_ids}" #faster
                # for data in json_data:
                #     feature = FeatureCollection.objects.get(id=data['id'])
                #     serializer = QueryFeatureCollectionSerializer(data={'layer':query_layer.id, 'attributes':feature.attributes, 'geometry':feature.geometry})
                #     if serializer.is_valid():
                #         created_obj=serializer.save()
                #         feature_ids.append(created_obj.id)
                #     else:
                #         for er in serializer._errors:
                #             errors.append(
                #                 {'errorName': er, 'details': serializer._errors[er][0]})
                #         return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
                # bbox = QueryLayer.objects.get(id=query_layer.id).bbox
                try:
                    import re

                    from django.contrib.gis.geos import GEOSGeometry
                    from django.db import connection
                    with connection.cursor() as cursor:
                        # raw_query=f"INSERT INTO maps_queryfeaturecollection (layer_id, is_deleted, attributes, geometry) (SELECT {query_layer.id} AS layer_id , is_deleted, attributes, geometry FROM maps_featurecollection WHERE id IN {feature_ids})"
                        # bbox_query = f"SELECT ST_Extent(geometry) AS bbox FROM maps_featurecollection WHERE id IN {feature_ids}" #faster
                        # bbox_query= f"SELECT ST_Envelope(ST_Union(ST_Envelope(geometry))) as bbox FROM maps_featurecollection WHERE id IN {feature_ids}" #slower
                        cursor = connection.cursor()
                        cursor.execute(raw_query)
                        cursor.execute(bbox_query)
                        #result[0] takes the form: 'BOX(85.4090132495848 27.66365506380353,85.51751110375923 27.717172880622645)'
                        result = cursor.fetchone()
                        result =result[0][4:-1]
                        result = re.split(" |,", result)
                        bbox = [float(data) for data in result]
                        # bbox = GEOSGeometry(result[0]).extent
                except Exception as e:
                    return Response(data={'message': str(e)}, status=400)
                query_layer.bbox = bbox
                query_layer.save()
                return Response(data={'id': query_layer.id, 'name': query_layer.name, 'display_on_map': query_layer.display_on_map, 'bbox': bbox, 'geom_type': query_layer.geom_type, 'features_count': count, 'icon': "", 'std_icon': '', 'style': {}}, status=200)
        except Exception as e:
            if query_layer:
                query_layer.delete()
            if feature_ids:
                QueryFeatureCollection.active.filter(id__in=feature_ids).delete()
            return Response(data={'message': str(e)}, status=400)


class AdvanceFilterVectorTileQuerySet(LayerMVTView, DetailView):
    '''
    VectorTile Generation for Advance Filter Layer
    http://localhost:8000/api/maps/advance_filter_vectortile/{z}/{x}/{y}/?layer=1
    '''

    vector_tile_layer_name = None
    vector_tile_fields = ('pk', 'layer', 'attributes')

    def get(self, request, *args, **kwargs):
        '''Authentication'''
        auth = request.headers['Authorization']
        token = auth.split()[1]
        try:
            '''if JWT authentication'''
            user_id = AccessToken(token)['user_id']
        except:
            '''if token authentication'''
            auth_token = Token.objects.get(key=token)
            user_id = auth_token.user_id
        if not User.active.filter(id=user_id).exists():
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
        if not request.GET.keys():
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        request_keys = request.GET.keys()
        if 'layer' not in request_keys or request.GET['layer'] == "":
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        layer_id = int(request.GET['layer'])
        if not QueryLayer.active.filter(id=layer_id).exists():
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        queryset = QueryFeatureCollection.active.filter(layer=layer_id)
        if queryset is None:
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        self.vector_tile_queryset = queryset.distinct()
        return BaseVectorTileView.get(self, request=request, z=kwargs.get('z'), x=kwargs.get('x'), y=kwargs.get('y'))

class QueryFeatureCollectionViewset(viewsets.ModelViewSet):
    '''
    Viewset for QueryFeatureCollection innstance
    '''
    queryset = QueryFeatureCollection.active.all()
    http_method_names = ['get', 'retrieve']
    default_serializer_class = QueryFeatureCollectionSerializer
    serializer_classes = {
        'list': QueryFeatureCollectionListSerializer,
        'retrieve': QueryFeatureCollectionSerializer
    }
    # permission_classes=[QueryFeatureCollectionPermission]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)
    pagination_class = CustomPageNumberPagination

    def list(self, request, *args, **kwargs):
        paginator = CustomPageNumberPagination()
        layer_id = request.query_params.get('layer', None)
        if not layer_id:
            return Response(data={'message': 'params layer is missing'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.queryset.filter(layer__id=layer_id)
        '''search_key'''
        search_key = request.query_params.get('search', None)
        if search_key:
            search_fields = list(queryset.first().attributes.keys())
            filter_kwargs = {}
            for field in search_fields:
                filter_kwargs['attributes__'+field+'__icontains'] = search_key
            list_of_Q = [Q(**{key: val})
                            for key, val in filter_kwargs.items()]
            queryset = queryset.filter(
                reduce(operator.or_, list_of_Q)) if search_fields else queryset
        ''''order_by'''
        order_by = request.query_params.get('ordering', None)
        if order_by:
            if 'id' in order_by:
                queryset = queryset.order_by(order_by)
            elif '-' in order_by:
                queryset = queryset.order_by('-attributes__'+order_by)
            else:
                queryset = queryset.order_by('attributes__'+order_by)
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(paginated_queryset, many=True, context={})
        return paginator.get_paginated_response(data=serializer.data)

'''Save Query Layer into main Layer Table'''
class LayerFromQueryAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            layer = request.data.get('layer', None)
            name = request.data.get('name', None)
            theme = request.data.get('theme', None)
            if not layer:
                return Response(data={'message': "layer params is missing!"}, status=400)
            if not name:
                return Response(data={'message': 'name params is missing!'}, status=400)
            if not theme:
                return Response(data={'message': 'theme params is missing!'}, status=400)
            query_layer_qs = QueryLayer.active.filter(id=layer)
            if query_layer_qs.exists():
                layer_instance,vector_layer_instance = None, None
                query_layer = query_layer_qs[0]
                theme = Theme.objects.get(id=theme)
                if Layer.active.filter(theme=theme, name=name).exists():
                    return Response(data={'message': 'Layer name cannot be duplicated!'}, status=400)
                query_features = QueryFeatureCollection.active.filter(layer=query_layer)
                if query_features:
                    try:
                        layer_instance = Layer.active.create(theme=theme, group=query_layer.group, name=name, layer_type='Vector',display_on_map=True)
                    except Exception as e:
                        return Response(data={'message': str(e)}, status=400)
                    vector_layer_instance=Vectorlayer.objects.get(layer=layer_instance)
                    vector_layer_instance.bbox=query_layer.bbox
                    vector_layer_instance.geom_type=query_layer.geom_type
                    vector_layer_instance.save()

                    from django.db import connection
                    try:
                        with connection.cursor() as cursor:
                            # raw_query=f"SELECT {layer_instance.id} AS id_value, attributes, geometry FROM maps_queryfeaturecollection WHERE layer_id = {query_layer.id}"
                            raw_query=f"INSERT INTO maps_featurecollection (layer_id, is_deleted, attributes, geometry) (SELECT {layer_instance.id} AS layer_id, is_deleted, attributes, geometry FROM maps_queryfeaturecollection WHERE layer_id = {query_layer.id})"
                            cursor = connection.cursor()
                            cursor.execute(raw_query)
                    except Exception as e:
                        if layer_instance: layer_instance.delete()
                        if vector_layer_instance: vector_layer_instance.delete()
                        return Response(data={'message': str(e)}, status=400)

                    '''create Layer attributes as well'''
                    attribute_objs = []
                    field_list = query_features[0].attributes.keys()
                    for field in field_list:
                        attribute_objs.append(LayerAttribute(layer=layer_instance, name=field))
                    LayerAttribute.objects.bulk_create(attribute_objs)
                    layer_instance.upload_status = 'successful'
                    layer_instance.save()
                    return Response(data={'layer': layer_instance.id, 'theme': layer_instance.theme.id, 'name': layer_instance.name, 'display_on_map':True, 'bbox': vector_layer_instance.bbox, 'geom_type': vector_layer_instance.geom_type}, status=200)

                else:
                    return Response(data={'message': "Query features not found for the layer"}, status=404)
            else:
                return Response(data={'message': "QueryLayer matching queryset does not exist!"}, status=404)

        except Exception as e:
            if layer_instance: layer_instance.delete()
            if vector_layer_instance: vector_layer_instance.delete()
            return Response(data={'message': str(e)}, status=400)

@api_view(['POST'])
def delete_sequence(request, *args, **kwargs):
    try:
        Sequence.objects.all().delete()
        return Response(data={'message': 'All sequence objects are deleted successfully.'}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([LayerDownloadPermission])
def layer_download(request):
    '''
    Download vector data in popular formats
    http://localhost:8000/api/maps/layer_download/?layer_id=200&output_format=shapefile
    format supported: 'shapefile', 'geojson', 'csv', 'kml', 'gpx'
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
        # layer_download_id = str(get_next_value(
        #         sequence_name="layer_download_id", initial_value=1))
        dir = f'{MEDIA_ROOT}/layer_download/{layer_instance.name}/'
        root_dir = f'{MEDIA_ROOT}/layer_download/'
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
            zipfile_name = root_dir + f'{layer_instance.name}'
            base_dir = f'{layer_instance.name}/' #relative dir of files to zip from the root dir
            shutil.make_archive(base_name=zipfile_name, format='zip', root_dir=root_dir, base_dir=base_dir)
            # zip file path
            file_url = root_dir + f'{layer_instance.name}.zip'
        elif output_format == "geojson":
            gdf.to_file(dir+layer_instance.name+".geojson", driver='GeoJSON')
            file_url = dir + f'{layer_instance.name}.geojson'
        elif output_format == "csv":
            df = pandas.DataFrame(gdf)
            df.to_csv(dir+layer_instance.name+'.csv')
            file_url = dir + f'{layer_instance.name}.csv'
            # geopandas.io.file.fiona.drvsupport.supported_drivers['CSV'] = 'raw'
            # gdf.to_file(dir+layer_instance.name+".csv", driver='CSV', encoding='utf-8')
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
        '''clearing the directory'''
        # clear_dir(root_dir)
        if os.path.exists(root_dir): shutil.rmtree(root_dir)
        return response
    except Exception as e:
        # clear_dir(root_dir)
        if os.path.exists(root_dir): shutil.rmtree(root_dir)
        return Response(status=404, data={'message': str(e)})

class FeatureCollectionViewset(viewsets.ModelViewSet):
    '''
    Viewset for FeatureCollection innstance
    '''
    queryset = FeatureCollection.active.all()
    http_method_names = ['get', 'retrieve', 'patch', 'post']
    default_serializer_class = FeatureCollectionSerializer
    serializer_classes = {
        'list': FeatureCollectionListSerializer,
        'retrieve': FeatureCollectionSerializer
    }
    permission_classes=[FeatureCollectionPermission]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)
    pagination_class = CustomPageNumberPagination

    def list(self, request, *args, **kwargs):
        paginator = CustomPageNumberPagination()
        layer_id = request.query_params.get('layer', None)
        if not layer_id:
            return Response(data={'message': 'params layer_id is missing'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.queryset.filter(layer__id=layer_id)
        '''search_key'''
        search_key = request.query_params.get('search', None)
        if search_key:
            search_fields = list(queryset.first().attributes.keys())
            filter_kwargs = {}
            for field in search_fields:
                filter_kwargs['attributes__'+field+'__icontains'] = search_key
            list_of_Q = [Q(**{key: val})
                            for key, val in filter_kwargs.items()]
            queryset = queryset.filter(
                reduce(operator.or_, list_of_Q)) if search_fields else queryset
        ''''order_by'''
        order_by = request.query_params.get('ordering', None)
        if order_by:
            if 'id' in order_by:
                queryset = queryset.order_by(order_by)
            else:
                queryset = queryset.order_by('attributes__'+order_by)
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(paginated_queryset, many=True, context={})
        return paginator.get_paginated_response(data=serializer.data)

    def partial_update(self, request, *args, **kwargs):
        try:
            errors=[]
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if serializer.is_valid():
                Layer.active.filter(id=instance.layer.id).update(is_clean=False)
                serializer.save()
                return Response(data=serializer.data, status=200)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)

    def create(self, request, *args, **kwargs):
        try:
            errors=[]
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                created_object = serializer.save()
                Layer.active.filter(id=created_object.layer.id).update(is_clean=False)
                return Response(data=serializer.data, status=201)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)

class LayerGroupViewset(viewsets.ModelViewSet):
    '''
    Viewset for LayerGroup objects.
    '''
    queryset = LayerGroup.active.all().order_by('order')
    http_method_names = ['get', 'post', 'patch']
    default_serializer_class = LayerGroupSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('theme', )
    permission_classes=[LayerGroupPermission]

    serializer_classes = {
        'list': LayerGroupListSerializer,
        # 'retrieve': LayerGroupSerializer
    }

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def create(self, request, *args, **kwargs):
        errors = []
        try:
            name = request.data.get('name', None)
            theme = request.data.get('theme', None)
            if LayerGroup.active.filter(Q(theme__id=theme) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate LayerGroup name for the theme.'},status=status.HTTP_400_BAD_REQUEST)
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def partial_update(self, request, pk=None, *args, **kwargs):
        errors = []
        request_dict = request.data
        request_keys = request_dict.keys()
        layergroup_instance = LayerGroup.active.get(pk=pk)
        if 'theme' in request_keys and request_dict['theme'] != "":
            theme = request_dict['theme']
        else:
            theme = layergroup_instance.theme.id
        if 'name' in request_keys and request_dict['name'] != "":
            name = request_dict['name']
            if LayerGroup.active.exclude(id=pk).filter(Q(theme__id=theme) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate LayerGroup name for the theme.'},status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(layergroup_instance, request_dict, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        else:
            for er in serializer._errors:
                errors.append(
                    {'errorName': er, 'details': serializer._errors[er][0]})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})

    def list(self, request, *args, **kwargs):
        theme = request.query_params.get('theme', None)
        if not theme:
            return Response(data={'message': 'params theme is missing'}, status=status.HTTP_400_BAD_REQUEST)
        self.queryset=self.filter_queryset(self.queryset)
        # queryset = self.queryset.filter(theme__id=theme)
        serializer = self.get_serializer(self.queryset, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

class ProjectLayerTemplateViewset(viewsets.ModelViewSet):
    '''
    Viewset for ProjectLayerTemplate objects.
    '''
    queryset = ProjectsLayerTemplate.active.all()
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [ProjectLayerTemplatePermission]
    default_serializer_class = ProjectLayerTemplateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('project', )

    serializer_classes = {
        'list': ProjectLayerTemplateListSerializer,
        'retrieve': ProjectLayerTemplateSerializer
    }

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def list(self, request, *args, **kwargs):
        '''
        http://localhost:8000/api/maps/project_layer_template/?project=2
        '''
        project = request.query_params.get('project', None)
        if not project:
            return Response(data={'message': 'params project is missing'}, status=status.HTTP_400_BAD_REQUEST)
        # queryset = self.queryset.filter(project__id=project)
        self.queryset=self.filter_queryset(self.queryset)
        serializer = self.get_serializer(self.queryset, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        '''
        http://localhost:8000/api/maps/project_layer_template/
        '''
        errors = []
        try:
            name = request.data.get('name', None)
            project = request.data.get('project', None)
            if ProjectsLayerTemplate.active.filter(Q(project__id=project) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate ProjectsLayerTemplate name for the project.'},status=status.HTTP_400_BAD_REQUEST)
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

    def partial_update(self, request, pk=None, *args, **kwargs):
        '''
        http://localhost:8000/api/maps/project_layer_template/1/
        '''
        errors = []
        request_dict = request.data
        request_keys = request_dict.keys()
        project_layer_template_instance = ProjectsLayerTemplate.active.get(pk=pk)
        if 'project' in request_keys and request_dict['project'] != "":
            project = request_dict['project']
        else:
            project = project_layer_template_instance.project.id
        if 'name' in request_keys and request_dict['name'] != "":
            name = request_dict['name']
            if ProjectsLayerTemplate.active.exclude(id=pk).filter(Q(project__id=project) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate ProjectsLayerTemplate name for the project.'},status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(project_layer_template_instance, request_dict, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        else:
            for er in serializer._errors:
                errors.append(
                    {'errorName': er, 'details': serializer._errors[er][0]})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})

class ProjectLayerTemplateAttributeViewset(viewsets.ModelViewSet):
    '''
    Viewset for ProjectLayerTemplateAttribute objects.
    '''
    queryset = ProjectsLayerTemplateAttribute.active.all()
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [ProjectsLayerTemplateAttributePermission]
    default_serializer_class = ProjectsLayerTemplateAttributeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('layer_template', )

    serializer_classes = {
        'list': ProjectsLayerTemplateAttributeListSerializer,
        'retrieve': ProjectsLayerTemplateAttributeSerializer
    }

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)

    def list(self, request, *args, **kwargs):
        '''
        http://localhost:8000/api/maps/project_layer_template_attribute/?layer_template=2
        '''
        layer_template = request.query_params.get('layer_template', None)
        if not layer_template:
            return Response(data={'message': 'params layer_template is missing'}, status=status.HTTP_400_BAD_REQUEST)
        # queryset = self.queryset.filter(layer_template__id=layer_template)
        self.queryset=self.filter_queryset(self.queryset)
        serializer = self.get_serializer(self.queryset, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        '''
        http://localhost:8000/api/maps/project_layer_template_attribute/
        '''
        errors = []
        try:
            name = request.data.get('name', None)
            layer_template = request.data.get('layer_template', None)
            if ProjectsLayerTemplateAttribute.active.filter(Q(layer_template__id=layer_template) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate ProjectsLayerTemplateAttribute name for the Template.'},status=status.HTTP_400_BAD_REQUEST)
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'Message': str(e)})

    def partial_update(self, request, pk=None, *args, **kwargs):
        '''
        http://localhost:8000/api/maps/project_layer_template_attribute/1/
        '''
        errors = []
        request_dict = request.data
        request_keys = request_dict.keys()
        project_layer_template_attribute = ProjectsLayerTemplateAttribute.active.get(pk=pk)
        if 'layer_template' in request_keys and request_dict['layer_template'] != "":
            layer_template = request_dict['layer_template']
        else:
            layer_template = project_layer_template_attribute.layer_template.id
        if 'name' in request_keys and request_dict['name'] != "":
            name = request_dict['name']
            if ProjectsLayerTemplateAttribute.active.exclude(id=pk).filter(Q(layer_template__id=layer_template) & Q(name=name)).exists():
                return Response(data={'message': 'Cannot create duplicate ProjectsLayerTemplateAttribute name for the Template.'},status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(project_layer_template_attribute, request_dict, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(data={'message': 'Success', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        else:
            for er in serializer._errors:
                errors.append(
                    {'errorName': er, 'details': serializer._errors[er][0]})
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})

'''Bulk Update ProjectsTemplateAttribute Selection for Download'''
@api_view(['POST'])
def update_template_attributes(request):
    '''
    http://0.0.0.0:8000/api/maps/update_template_attributes/
    '''
    try:
        instances=[]
        for key, value in request.data.items():
            instance = ProjectsLayerTemplateAttribute.active.get(id=key)
            instances += [instance]
            instance.selected = value

        '''update selection in bulk'''
        ProjectsLayerTemplateAttribute.active.bulk_update(instances, ['selected'])
        return Response({'message': "Selection update succssful"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([ImportTemplatePermission])
def import_template(request):
    '''
    View to import General Template for a specific project
    '''
    try:
        project = request.data.get('project', None)
        if not project or not Project.active.filter(id=project).exists():
                return Response(data={'message': 'Invalid project params!'}, status=status.HTTP_400_BAD_REQUEST)
        project_instance = Project.active.get(id=project)
        templates = request.data.get('templates', None)
        if not templates:
            return Response(data={'message': 'templates params is missing!'}, status=status.HTTP_400_BAD_REQUEST)
        if templates == 'all':
            templates_qs = LayerTemplate.active.all().values('id', 'name', 'geometry_type')
        else:
            templates_list = [int(id) for id in templates.split(',')]
            templates_qs = LayerTemplate.active.filter(id__in=templates_list).values('id', 'name', 'geometry_type')
            # templates_list = json.loads(templates)

        if not templates_qs.exists():
            return Response(data={'message': 'Template object does not exist for the templates params list.'}, status=status.HTTP_400_BAD_REQUEST)
        project_template_instance_ids = []
        for template in templates_qs:
            '''retrieving layer template vaulues to clone later'''
            if ProjectsLayerTemplate.active.filter(Q(name=template['name']) & Q(project=project)).exists():
                return Response(data={'message': 'Cannot create duplicate template name for a project'}, status=status.HTTP_400_BAD_REQUEST)
                '''creating project layer template object'''
            project_template_instance = ProjectsLayerTemplate.active.create(name=template['name'], geometry_type=template['geometry_type'], project=project_instance)
            project_template_instance_ids.append(project_template_instance.id)
            template_attributes_values = LayerTemplateAttribute.objects.filter(layer_template=template['id']).values('name', 'alias', 'data_type', 'length', 'precision', 'unit')
            for attribute in template_attributes_values:
                ProjectsLayerTemplateAttribute.active.create(name=attribute['name'], alias=attribute['alias'], data_type=attribute['data_type'], length=attribute['length'], precision=attribute['precision'], unit=attribute['unit'], layer_template=project_template_instance)
        return Response(data={'message': f'Templates imported succesfully into the {project_instance} project'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        if project_template_instance_ids:
            ProjectsLayerTemplate.active.filter(id__in=project_template_instance_ids).delete()
        return Response(data={'message':str(e)}, status=400)

'''bulk download layer templates'''
@api_view(['GET'])
@permission_classes([AllowAny])
def bulk_template_download(request):
    #creating directory to save shapefile
    dir=MEDIA_ROOT + '/template_download/templates/'
    os.makedirs(dir, exist_ok=True)
    file_url=None
    try:
        project = request.query_params.get('project', None)
        if not project:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': "params project is missing"})
        layer_template_qs=ProjectsLayerTemplate.active.filter(project=project, selected=True)
        if not layer_template_qs:
            return Response(data={'message': 'No any selected layer templated found!'}, status=400)
        for layer_template in layer_template_qs:
            attributes=ProjectsLayerTemplateAttribute.active.filter(layer_template=layer_template, selected=True)
            properties={}
            for attribute in attributes:
                if attribute.data_type=="str":
                    properties[attribute.name]='str'
                elif attribute.data_type=="int":
                    properties[attribute.name]=f'int:{attribute.length}'
                elif attribute.data_type=="float":
                    properties[attribute.name]=f'float:{attribute.length}.{attribute.precision}'
                elif attribute.data_type=="date":
                    properties[attribute.name]='date'
            schema={
                'geometry':layer_template.geometry_type,
                'properties':properties
            }
            shapefile_path = MEDIA_ROOT + \
                                f'/template_download/templates/{layer_template.name}.shp'
            shapefile = fiona.open(shapefile_path, mode='w', driver='ESRI Shapefile',
            schema = schema, crs = "EPSG:4326")
            shapefile.close()

        # create a ZipFile
        templates_zip_name = 'templates.zip'
        zipfile_path = MEDIA_ROOT + f'/template_download/templates'
        # files = MEDIA_ROOT + '/template_download/shapefiles/'
        files = zipfile_path
        shutil.make_archive(zipfile_path, 'zip', files)

        # defining zip file path
        file_url = MEDIA_ROOT + \
            f'/template_download/{templates_zip_name}'

        # downloading zip file
        zip_file = open(file_url, 'rb')
        response = HttpResponse(
            zip_file, content_type='application/force-download')
        response[
            'Content-Disposition'] = 'attachment; filename="%s"' % f'{templates_zip_name}'
        clear_dir(dir) #clearing directory
        if os.path.isfile(file_url): os.remove(file_url)
        return response
    except Exception as e:
        clear_dir(dir) #clearing directory
        if os.path.isfile(file_url): os.remove(file_url)
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

'''GeoJSON API for features.'''
'''{{baseURL}}api/maps/feature/2/'''
class FeatureGeoJSONAPIView(APIView):
    permission_classes = [FeatureGeoJSONPermission]
    def get(self, request, pk=None, *args, **kwargs):
        try:
            feature_qs = FeatureCollection.active.filter(id=pk)
            if feature_qs.exists():
                data = serialize('geojson', feature_qs, geometry_field='geometry', fields=('pk', 'layer', 'sub_layer'))
                geojson_data = json.loads(data)
                return Response(data=geojson_data, status=status.HTTP_200_OK)
            else:
                return Response(data={'message': 'FeatureCollection matching queryset does not exist!'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

'''
API for data merge/update
missed_col = yes means merge/udate missed columns with null values. If no, terminate process from frontend.
extra_col = yes means merge/update extra columns
verified = yes means the user has insisted on merging/updating columns even after missed or extra columns and missed rows. If no, terminate process from frontend.
'''
class DataMergeUpdateAPIView(APIView):
    def post(self, request, *args, **kwargs):
        errors=[]
        try:
            missed_col= request.data.get('missed_col', 'no')
            extra_col = request.data.get('extra_col', 'no')
            verified = request.data.get('verified', 'no')
            layer = request.data.get('layer', None)
            layer_file_instance = None
            if layer and Layer.active.filter(id=layer).exists():
                layer_instance = Layer.active.get(id=layer)
                if layer_instance.layer_type != 'Vector':
                    return Response(data={'message': 'Data Merge and Update features are valid for vector layers only!'}, status=status.HTTP_400_BAD_REQUEST)
                if 'file' in request.FILES and request.FILES.get('file') != "":
                    layer_file_instance = LayerFile.objects.get(layer__id=layer)
                    layer_file_instance.file=request.FILES['file']
                    layer_file_instance.save()
                else:
                    return Response(data={'message': 'File is missing!'}, status=status.HTTP_400_BAD_REQUEST)
                '''check whether celery is working or not'''
                is_working=get_celery_worker_status()
                if is_working != "working":
                    return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': "server error: celery is not working"})
                response = handleDataMergeUpdate.delay(layer, missed_col, extra_col, verified)
                return Response(status=200, data={'message': 'Updating/Merging Data', 'task_id': response.task_id})
            else:
                return Response(data={'message': 'Layer matching queryset does not exist!'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_data_merge_update_task_response(request):
    '''
    View to get the response of aynchronous task run for data merge update
    '''
    try:
        task_id = request.query_params.get('task_id', None)
        result = AsyncResult(task_id, app=app)
        if result.ready():   # check task state: true/false
            try:
                response, code = result.get()
                if response == "success" or code == 200:
                    return Response(response, status=status.HTTP_200_OK)
                else:
                    return Response(response, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': "Please wait result"}, status=200)
    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# import geopandas as gpd
# import matplotlib.pyplot as plt
# import networkx as nx
# import osmnx as ox
# import pandas as pd
# from descartes import PolygonPatch
# from shapely.geometry import LineString, Point, Polygon


def road_class_to_kmph(road_class):
    """
    Returns a speed limit value based on road class,
    using typical Finnish speed limit values within urban regions.
    """
    if road_class == "motorway":
        return 100
    elif road_class == "motorway_link":
        return 80
    elif road_class in ["trunk", "trunk_link"]:
        return 60
    elif road_class == "service":
        return 30
    elif road_class == "living_street":
        return 20
    else:
        return 50

class OptimumRouteAnalysisAPIView(APIView):
    # permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwarggs):
        '''
        parameters required:
        -------------------------------------------------------
        source: analysis source
        origin_long <float>: longitude of origin point
        origin_lat <float>: latitude of origin point
        destination_long <float>: longitude of destination point
        destination_lat <float>: latitude of destination point
        k <int>: number of shortest paths to generate
        distance <int: meters>: retain only those nodes within a bounding box of this distance from the origin point.
        -------------------------------------------------------
        returns: task id running in celery worker.
        '''
        try:
            request_dict = request.data
            check_list = ['source', 'mode', 'origin_long', 'origin_lat', 'destination_long', 'destination_lat', 'project', 'name', 'type']
            for key in check_list:
                if key not in request_dict or request_dict[key]=='':
                    return Response(data={'message': 'source, mode, origin_long, origin_lat, destination_long, destination_lat, project, name, type are required!'}, status=400)
            source = request_dict['source']
            origin_long = float(request_dict['origin_long'])
            origin_lat = float(request_dict['origin_lat'])
            destination_long = float(request_dict['destination_long'])
            destination_lat = float(request_dict['destination_lat'])
            road_network = int(request_dict['road_network']) if 'road_network' in request_dict and request_dict['road_network'] != '' else None
            obstcles = json.loads(request_dict['obstcles']) if 'obstcles' in request_dict and request_dict['obstcles'] != '' else None
            k = int(request_dict['paths']) if 'paths' in request_dict and request_dict['paths'] != '' else 3
            distance = int(request_dict['distance']) if 'distance' in request_dict and request_dict['distance'] != '' else 5000
            '''for analysis object'''
            name=request_dict['name']
            type=request_dict['type']
            mode = request_dict['mode']
            display=request_dict['display'] if 'display' in request_dict and request_dict['display'] != '' else False
            project = int(request_dict['project'])
            '''create analysis_instance'''
            if Analysis.active.filter(name=name, type=type, project=project).exists():
                return Response(data={'message': f'{type} with the name {name} for the project already exists!'}, status=400)
            analysis_inst = Analysis.active.create(name=name, type=type, display=display, geom_type='LineString', project=project)
            analysis_id = analysis_inst.id
            optimum_route_inst = OptimumRoute.active.create(analysis_id=analysis_id, mode=mode, paths=k, origin_long=origin_long, origin_lat=origin_lat, destination_long=destination_long, destination_lat=destination_lat)
            optimum_route_id = optimum_route_inst.id
            is_working=get_celery_worker_status()
            if is_working != "working":
                analysis_inst.delete()
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': "server error: celery is not working"})
            if source == 'osm':
                response = CreateNetworkGraph.delay(origin_long, origin_lat, destination_long, destination_lat, k, distance, analysis_id)
                # response, status = CreateNetworkGraph(origin_long, origin_lat, destination_long, destination_lat, k, distance)
            elif source == 'system':
                response = CreateNetworkGraphSystem.delay(road_network, mode, origin_long, origin_lat, destination_long, destination_lat, k, obstcles, analysis_id, optimum_route_id)
            else:
                response = 'source parameter is missing!'
                status = 400
                return Response(data={'message': response}, status=status)
            clear_dir('cache/')
            return Response(status=200, data={'message': 'Performing Optimum Route Analysis', 'task_id': response.task_id})
        except Exception as e:
            analysis_inst.delete()
            return Response(data={'message': 'error', 'details': str(e)}, status=400)

class ServiceAreaAnalysisAPIView(APIView):
    # permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwarggs):
        try:
            request_dict = request.data
            check_list = ['source', 'origin_long', 'origin_lat', 'destination_long', 'destination_lat', 'project', 'name', 'type']
            for key in check_list:
                if key not in request_dict or request_dict[key]=='':
                    return Response(data={'message': 'source, origin_long, origin_lat, destination_long, destination_lat, project, name, type are required!'}, status=400)
            source = request_dict['source']
            origin_long = float(request_dict['origin_long'])
            origin_lat = float(request_dict['origin_lat'])
            destination_long = float(request_dict['destination_long'])
            destination_lat = float(request_dict['destination_lat'])
        except Exception as e:
            # analysis_inst.delete()
            return Response(data={'message': 'error', 'details': str(e)}, status=400)

class BufferAnalysisAPIView(APIView):
    def post(self, request, *args, **kwarggs):
        pass


@api_view(['GET'])
def get_analysis_task_response(request):
    '''
    View to get the response of aynchronous task run for data merge update
    '''
    try:
        task_id = request.query_params.get('task_id', None)
        result = AsyncResult(task_id, app=app)
        if result.ready():   # check task state: true/false
            try:
                response, code = result.get()
                if code == 200:
                    return Response(data={'analysis_id':response}, status=status.HTTP_200_OK)
                else:
                    return Response(data={'message': response}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': "Please wait for result"}, status=200)
    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class OptimumRouteAnalysisTileQuerySet(NetworkRoutesMVTView, DetailView):
    '''
    VectorTile Generation for Maps Layer
    url:"http://0.0.0.0:8000/api/maps/shortest_routes_vectortile/{z}/{x}/{y}/?analysis_id=&route_no=",
    '''
    vector_tile_layer_name = None
    vector_tile_fields = ('id','route_no','length','travel_time')

    def get(self, request, *args, **kwargs):
        '''Authentication'''
        auth = request.headers['Authorization']
        token = auth.split()[1]
        try:
            '''if JWT authentication'''
            user_id = AccessToken(token)['user_id']
        except:
            '''if token authentication'''
            auth_token = Token.objects.get(key=token)
            user_id = auth_token.user_id
        if not User.active.filter(id=user_id).exists():
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
        request_keys = request.GET.keys()
        if 'analysis_id' not in request_keys or request.GET['analysis_id'] == "":
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        analysis_id=request.GET['analysis_id']
        queryset=NetworkRoutes.active.filter(analysis_id=analysis_id)
        if 'route_no' in request_keys and request.GET['route_no'] != "":
            route_no=request.GET['route_no']
            queryset=queryset.filter(route_no=int(route_no))
        self.vector_tile_queryset = queryset.distinct()
        return BaseVectorTileView.get(self, request=request, z=kwargs.get('z'), x=kwargs.get('x'), y=kwargs.get('y'))

'''Map Popup API'''
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feature_popup(request, *args, **kwargs):
    try:
        result={}
        feature_id = request.query_params.get('feature_id', None)
        if not feature_id:
            return Response(data={'message': 'feature_id query params is missing'}, status=400)
        feature_qs = FeatureCollection.active.filter(id=feature_id)
        if feature_qs.exists():
            feature_inst = feature_qs[0]
        attributes = feature_inst.attributes
        vector_layer = Vectorlayer.objects.filter(layer=feature_inst.layer)
        if vector_layer.exists():
            popup_fields = vector_layer[0].popup_fields
        else:
            popup_fields = []
        if popup_fields:
            for field, value in attributes.items():
                if field in popup_fields:
                    result[field] = value
        else:
            result=attributes
        return Response(data=result, status=200)
    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

'''Analysis layers api for map page'''
@api_view(['GET'])
def analysis_layers(request, *args, **kwargs):
    options={}
    try:
        project = request.query_params.get('project', None)
        if not project or project == '':
            return Response(data={'message': 'project params is missing!'}, status=400)
        analysis_types = Analysis.active.filter(project=project).values_list('type', flat=True).distinct()
        for ana_type in analysis_types:
            print(ana_type, type(ana_type), "is ana type")
            '''say network analysis'''
            ana_type_list=[]
            analys_qs = Analysis.active.filter(project=project, type=ana_type)
            for analysis in analys_qs:
                analysis_dict={}
                analysis_dict['id'] = analysis.id
                analysis_dict['name'] = analysis.name
                analysis_dict['geom_type'] = analysis.geom_type
                analysis_dict['bbox'] = analysis.bbox
                analysis_dict['routes'] = NetworkRoutes.active.filter(optimum_route_id=analysis.id).values('id', 'route_no', 'style', 'bbox')
                ana_type_list.append(analysis_dict)
            options[ana_type]=ana_type_list
        return Response(options,status=200)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

class ProjectMapConfigAPIView(APIView):
    permission_classes = [IsAuthenticated, ProjectMapConfigPermission]
    def patch(self, request, *args, **kwargs):
        try:
            project = request.query_params.get('project', None)
            user = request.query_params.get('user', None)
            project_config_qs = ProjectMapConfig.active.filter(project=project, user=user) if user else ProjectMapConfig.active.filter(project=project)
            if project_config_qs.exists():
                instance = project_config_qs[0]
            else:
                instance = ProjectMapConfig.active.create(project=project, user=user) if user else ProjectMapConfig.active.create(project=project)
            request_dict = request.data
            if 'map_config' in request_dict and request_dict['map_config'] != '':
                map_config = json.loads(request_dict['map_config'])
                instance.map_config = map_config
                instance.save()
            result = {'id': instance.id, 'map_config': instance.map_config, 'user': instance.user}
            return Response(data=result, status=200)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': str(e)})

'''category api for layers'''
@api_view(['GET'])
def category(request, *args, **kwargs):
    try:
        qs=Category.objects.all().values('id', 'name')
        return Response(data=qs, status=200)
    except Exception as e:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': str(e)})

# DB Connection
db_connection_url = env("CONNECTION_DB", default="postgresql://xIDokAfQUYOjTGhErprxMHnjZTJXMloY:gn63GjyG9AOKLYgrvOcOZFrAeYgjLOA4IkjuTXzISZ3nnMaHxTX1rSxI0fdBSb52@postgres:5432/pgis_toolkit")
con = create_engine(db_connection_url)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_layer(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            sql = "SELECT id, geometry AS geom, attributes FROM maps_featurecollectionmirror WHERE layer_id=" + layer
            gdf = geopandas.read_postgis(sql, con)
            null_check = check_null(gdf)
            multipart_check = check_multipart(gdf)
            duplicate_check = check_duplicate(gdf)
            intersection_check = check_self_intersection(gdf)
            snapping_check = check_snapping(layer, con)
            return Response(data={'messages': [null_check["message"], multipart_check["message"], duplicate_check["message"], intersection_check["message"], snapping_check["message"]]}, status=200)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_null_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = check_null(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_multipart_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = check_multipart(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_duplicate_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = check_duplicate(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_overlapping_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = check_overlapping(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_self_intersecting_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = check_self_intersection(layer)
            return Response(content)
        else:
            return Response(data={'messages': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_isolated_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = check_snapping(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_error_data(request, *args, **kwargs):
#     try:
#         layer = request.query_params.get('layer', None)
#         if not layer:
#             return Response(data={'message': 'layer params is missing!'}, status=400)
#         layer_qs = Vectorlayer.objects.filter(layer=layer)
#         if layer_qs.exists():
#             sql = "SELECT id, geometry AS geom, attributes FROM maps_featurecollectionmirror WHERE layer_id=" + layer
#             gdf = geopandas.read_postgis(sql, con)
#             try:
#                 error_data = CleaningErrors.objects.get(layer_id=layer)
#                 serializer = CleaningErrorsSerializer(error_data)
#                 return Response(data={"total_data": len(gdf), "errors": serializer.data})
#             except  Exception as e:
#                 return Response(data={'message': str(e)}, status=400)
#         else:
#             return Response(data={'message': "Data does not exists"}, status=400)
#     except Exception as e:
#         return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fix_layer(request, *args, **kwargs):
    layer = request.query_params.get('layer', None)
    if not layer:
        return Response(data={'message': 'layer params is missing!'}, status=400)
    layer_qs = Vectorlayer.objects.filter(layer=layer)
    if layer_qs.exists():
        pass
    return Response(data={"message": "Fixed Layer"}, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fix_null_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = fix_null(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fix_multipart_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = fix_multipart(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fix_duplicate_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = fix_duplicate(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fix_overlay_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = fix_overlapping(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fix_self_intersecting_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = fix_self_intersection(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fix_isolated_geometry(request, *args, **kwargs):
    try:
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing!'}, status=400)
        layer_qs = Vectorlayer.objects.filter(layer=layer)
        if layer_qs.exists():
            content = fix_snapping(layer)
            return Response(content)
        else:
            return Response(data={'message': "Data does not exists"}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buffer_distance(request, *args, **kwargs):
    layer = request.query_params.get('layer', None)
    distance = request.query_params.get('distance', None)
    dissolve = request.query_params.get('dissolve', None)
    if dissolve:
        if dissolve == 'true':
            dissolve = True
        else:
            dissolve = False
    else:
        dissolve = False
    if not layer:
        return Response(data={'message': 'layer params is missing!'}, status=400)
    layer_qs = Vectorlayer.objects.filter(layer=layer)
    if layer_qs.exists():
        sql = "SELECT id, geometry, attributes FROM maps_featurecollection WHERE layer_id=" + layer
        layer_qs = geopandas.read_postgis(sql, con, geom_col="geometry")
        layer_qs = layer_qs.join(pd.DataFrame(layer_qs.pop('attributes').values.tolist()))
        data = buffer_by_distance(layer_qs, float(distance), dissolve)
        return Response(data={"message":"Buffered Successfully", "data": data.to_json()})
    return Response(data={'message': "Data does not exists"}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buffer_column(request, *args, **kwargs):
    layer = request.query_params.get('layer', None)
    column = request.query_params.get('column', None)
    ratio = request.query_params.get('ratio', None)
    dissolve = request.query_params.get('dissolve', None)
    if dissolve:
        if dissolve == 'true':
            dissolve = True
        else:
            dissolve = False
    else:
        dissolve = False
    if not layer or not column or not ratio or not dissolve:
        return Response(data={'message': 'Params are missing!'}, status=400)
    layer_qs = Vectorlayer.objects.filter(layer=layer)
    if layer_qs.exists():
        sql = "SELECT id, geometry, attributes FROM maps_featurecollection WHERE layer_id=" + layer
        layer_qs = geopandas.read_postgis(sql, con, geom_col="geometry")
        layer_qs = layer_qs.join(pd.DataFrame(layer_qs.pop('attributes').values.tolist()))
        data = buffer_by_column_value(layer_qs, column, float(ratio), dissolve)
        return Response(data={"message":"Buffered Successfully", "data": data.to_json()})
    return Response(data={'message': "Data does not exists"}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def data_buffer(request, *args, **kwargs):
    layer = request.query_params.get('layer', None)
    layers = request.query_params.get('layers', None)
    distance = request.query_params.get('distance', None)
    layer_qs = Vectorlayer.objects.filter(layer=layer)
    if layer_qs.exists():
        sql = "SELECT id, geometry, attributes FROM maps_featurecollection WHERE layer_id=" + layer
        layer_qs = geopandas.read_postgis(sql, con, geom_col="geometry")
        layer_qs = layer_qs.join(pd.DataFrame(layer_qs.pop('attributes').values.tolist()))
        layers_qs = []
        for layer in json.loads(layers):
            gdf = geopandas.read_postgis("SELECT id, geometry, attributes FROM maps_featurecollection WHERE layer_id=" + str(layer), con, geom_col="geometry")
            gdf = gdf.join(pd.DataFrame(gdf.pop('attributes').values.tolist()))
            layers_qs.append(gdf)
        data = find_data_within_buffer(layer_qs, float(distance), layers_qs)
        return Response(data={"message":"Data fetched Successfully", "data": data.to_json()})
    return Response(data={'message': "Data does not exists"}, status=400)

'''cleaning error map toogle bar api'''
@api_view(['GET'])
def cleaning_error_features(request, *args, **kwargs):
    try:
        result={}
        layer = request.query_params.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing'}, status=400)
        features = "SELECT COUNT (id) FROM maps_featurecollectionmirror WHERE layer_id=" + layer
        # null = "SELECT ARRAY_LENGTH (snapping, 1) FROM maps_cleaningerrors WHERE layer_id=" + layer
        try:
            with connection.cursor() as cursor:
                cursor = connection.cursor()
                cursor.execute(features)
                features = cursor.fetchone()
                features_count = features[0]
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)

        cleaning_error_qs = CleaningErrors.objects.filter(layer_id=layer).annotate(features=Value(features_count))
        if cleaning_error_qs.exists():
            cleaning_error = cleaning_error_qs.values('layer_id', 'null', 'multipart', 'duplicate', 'overlap', 'self_instersect', 'snapping', 'features')[0]
        else:
            return Response(data={'message': 'Cleaning error instance not found for the layer'}, status=400)
        return Response(data=cleaning_error, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=400)

'''copy features from featurecollection to featurecollectionmirror before data cleaning'''
@api_view(['POST'])
def copy_features(request, *args, **kwargs):
    try:
        layer = request.data.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing'}, status=400)
        if not FeatureCollection.active.filter(layer=layer).exists():
            return Response(data={'message': 'No any features found for the layer'}, status=400)
        # delete_sql = f'DELETE FROM maps_featurecollectionmirror WHERE layer_id={layer}'
        # insert_sql = f'INSERT INTO maps_featurecollectionmirror (feature_id, layer_id, sub_layer_id, attributes, geometry, is_deleted, last_updated, uploaded_date) (SELECT id, layer_id, sub_layer_id, attributes, geometry, is_deleted, last_updated, uploaded_date FROM maps_featurecollection WHERE layer_id = {layer})'
        update_sql = f'''UPDATE maps_featurecollectionmirror m SET
                            feature_id = f.id,
                            layer_id = f.layer_id,
                            sub_layer_id = f.sub_layer_id,
                            attributes = f.attributes,
                            geometry = f.geometry,
                            is_deleted = f.is_deleted,
                            last_updated = f.last_updated,
                            uploaded_date = f. uploaded_date
                        FROM maps_featurecollection f
                        WHERE f.layer_id = {layer} AND f.id=m.feature_id'''

        insert_sql = f'''INSERT INTO maps_featurecollectionmirror (feature_id, layer_id, sub_layer_id, attributes, geometry, is_deleted, last_updated, uploaded_date)
                        (	SELECT id, layer_id, sub_layer_id, attributes, geometry, is_deleted, last_updated, uploaded_date
                            FROM maps_featurecollection
                            WHERE layer_id = {layer} AND id NOT IN (SELECT feature_id FROM maps_featurecollectionmirror WHERE layer_id = {layer} AND feature_id IS NOT NULL)
                        )'''

        try:
            with connection.cursor() as cursor:
                cursor = connection.cursor()
                cursor.execute(update_sql)
                cursor.execute(insert_sql)
            return Response(data={'message': 'Features were replicated successfully'}, status=200)
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)
    except Exception as e:
        return Response(data={'message': str(e)}, status=400)

class FeatureCollectionMirrorViewset(viewsets.ModelViewSet):
    '''
    Viewset for FeatureCollectionMirror objects
    '''
    queryset = FeatureCollectionMirror.active.all()
    http_method_names = ['get', 'patch', 'post']
    default_serializer_class = FeatureCollectionMirrorSerializer
    serializer_classes = {
        # 'list': FeatureCollectionListSerializer,
        'retrieve': FeatureCollectionMirrorSerializer
    }
    # permission_classes=[FeatureCollectionPermission]

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action,self.default_serializer_class)
    pagination_class = CustomPageNumberPagination

    def partial_update(self, request, pk=None, *args, **kwargs):
        try:
            errors=[]
            instance = self.get_object()
            pk = int(pk)
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if serializer.is_valid():
                is_deleted = request.data.get('is_deleted', False)
                if is_deleted == True or is_deleted == 'True':
                    cleaning_err_inst = CleaningErrors.objects.get(layer_id=instance.layer.id)
                    del_id_from_clean_instance(cleaning_err_inst, pk)
                    cleaning_err_inst.save()
                    serializer.save()
                    return Response(data={'message': 'Feature Delete Successful'}, status=200)
                serializer.save()
                return Response(data=serializer.data, status=200)
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'Error': errors})
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)

'''Bulk delete null geometries'''
@api_view(['POST'])
def bulk_del_null_geom(request, *args, **kwargs):
    try:
        feature_ids = request.data.get('feature_ids', None)
        if not feature_ids:
            return Response(data={'message': 'params feature_ids is missing'}, status=400)
        # feature_ids = [int(id) for id in feature_ids.split(',')]
        feature_ids = json.loads(feature_ids)
        feature_qs = FeatureCollectionMirror.active.filter(id__in=feature_ids)
        if feature_qs.exists():
            layer = feature_qs[0].layer.id
            cleaning_err_inst = CleaningErrors.objects.get(layer_id=layer)
            for pk in feature_ids:
                del_id_from_clean_instance(cleaning_err_inst, pk)
            '''finally update cleaning instance'''
            feature_qs.update(is_deleted=True)
            cleaning_err_inst.save()
        else:
            return Response(data={'message': 'Feature matching queryset not found'}, status=400)
        return Response(data={'message': 'Features deleted successful.'}, status=200)
    except Exception as e:
        return Response(data={'message': str(e)}, status=400)


'''cleaning error features vectortile'''
class ErrorFeaturesVectorTileQuerySet(LayerMVTView, DetailView):
    '''
    VectorTile Generation for Data cleaning error features
    url:"http://localhost:8000/api/maps/error_features_vectortile/{z}/{x}/{y}/?layer=816&type=multipart",
    '''
    vector_tile_layer_name = None
    vector_tile_fields = ('pk','layer')

    def get(self, request, *args, **kwargs):
        '''Authentication'''
        auth = request.headers['Authorization']
        token = auth.split()[1]
        try:
            '''if JWT authentication'''
            user_id = AccessToken(token)['user_id']
        except:
            '''if token authentication'''
            auth_token = Token.objects.get(key=token)
            user_id = auth_token.user_id
        if not User.active.filter(id=user_id).exists():
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
        request_keys = request.GET.keys()
        if 'layer' not in request_keys or request.GET['layer'] == "" or 'type' not in request_keys or request.GET['type'] == "":
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        layer_id=request.GET['layer']
        error_type = request.GET['type']
        instance=CleaningErrors.objects.get(layer_id=layer_id)
        '''filter by layer id'''
        if error_type == 'null':
            queryset=FeatureCollectionMirror.active.filter(id__in=instance.null)
        elif error_type == 'multipart':
            queryset=FeatureCollectionMirror.active.filter(id__in=instance.multipart)
        elif error_type == 'duplicate':
            queryset=FeatureCollectionMirror.active.filter(id__in=instance.duplicate)
        elif error_type == 'overlap':
            queryset=FeatureCollectionMirror.active.filter(id__in=instance.overlap)
        elif error_type == 'self_instersect':
            queryset=FeatureCollectionMirror.active.filter(id__in=instance.self_instersect)
        elif error_type == 'snapping':
            queryset=FeatureCollectionMirror.active.filter(id__in=instance.snapping)
        else:
            queryset = None
        self.vector_tile_queryset = queryset.distinct()
        return BaseVectorTileView.get(self, request=request, z=kwargs.get('z'), x=kwargs.get('x'), y=kwargs.get('y'))

'''GeoJSON API for features mirror.'''
'''{{baseURL}}api/maps/feature_mirror_geojson/?feature_id=&mirror_id'''
class FeatureMirrorGeoJSONAPIView(APIView):
    def get(self, request, pk=None, *args, **kwargs):
        try:
            feature_id = request.query_params.get('feature_id', None)
            mirror_id = request.query_params.get('mirror_id', None)
            if feature_id:
                feature_qs = FeatureCollectionMirror.active.filter(feature=feature_id)
            elif mirror_id:
                feature_qs = FeatureCollectionMirror.active.filter(id=mirror_id)
            if feature_qs.exists():
                data = serialize('geojson', feature_qs, geometry_field='geometry', fields=('pk', 'layer', 'sub_layer'))
                geojson_data = json.loads(data)
                return Response(data=geojson_data, status=status.HTTP_200_OK)
            else:
                return Response(data={'message': 'FeatureCollectionMirror matching queryset does not exist!'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(data={'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

'''syn features from featurecollectionmirror  to featurecollection after data cleaning'''
@api_view(['POST'])
def sync_features(request, *args, **kwargs):
    try:
        layer = request.data.get('layer', None)
        if not layer:
            return Response(data={'message': 'layer params is missing'}, status=400)
        if not FeatureCollectionMirror.active.filter(layer=layer).exists():
            return Response(data={'message': 'No any features found for the layer'}, status=400)
        update_sql = f'''UPDATE maps_featurecollection f SET
                            layer_id = m.layer_id,
                            sub_layer_id = m.sub_layer_id,
                            attributes = m.attributes,
                            geometry = m.geometry,
                            is_deleted = m.is_deleted,
                            last_updated = m.last_updated,
                            uploaded_date = m. uploaded_date
                        FROM maps_featurecollectionmirror m
                        WHERE m.layer_id = {layer} AND m.feature_id IS NOT NULL AND f.id=m.feature_id '''

        insert_sql = f'''INSERT INTO maps_featurecollection (layer_id, sub_layer_id, attributes, geometry, is_deleted, last_updated, uploaded_date)
                        (	SELECT layer_id, sub_layer_id, attributes, geometry, is_deleted, last_updated, uploaded_date
                            FROM maps_featurecollectionmirror
                            WHERE layer_id = {layer} AND feature_id IS NULL
                        )'''
        try:
            with connection.cursor() as cursor:
                cursor = connection.cursor()
                cursor.execute(update_sql)
                cursor.execute(insert_sql)
            Layer.active.filter(id=layer).update(is_clean=True)
            return Response(data={'message': 'Sync to featurecollection successful'}, status=200)
        except Exception as e:
            return Response(data={'message': str(e)}, status=400)
    except Exception as e:
        return Response(data={'message': str(e)}, status=400)

class MirrorFeatureVectorTileQuerySet(LayerMVTView, DetailView):
    '''
    VectorTile Generation for Maps Layer
    url:"http://localhsot:8000/api/maps/feature_mirror_vectortile/{z}/{x}/{y}/?layer=&sub_layer=",
    '''
    vector_tile_layer_name = None
    vector_tile_fields = ('pk', 'layer', 'sub_layer', 'feature')

    def get(self, request, *args, **kwargs):
        '''Authentication'''
        auth = request.headers['Authorization']
        token = auth.split()[1]
        try:
            '''if JWT authentication'''
            user_id = AccessToken(token)['user_id']
        except:
            '''if token authentication'''
            auth_token = Token.objects.get(key=token)
            user_id = auth_token.user_id
        if not User.active.filter(id=user_id).exists():
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
        request_keys = request.GET.keys()
        '''filter by layer id'''
        if 'layer' not in request_keys or request.GET['layer'] == "":
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        layer_id=request.GET['layer']
        queryset=FeatureCollectionMirror.active.filter(layer=layer_id)
        if 'sub_layer' in request_keys and request.GET['sub_layer'] != "":
            sub_layer_id=request.GET['sub_layer']
            queryset=queryset.filter(sub_layer=sub_layer_id)
        self.vector_tile_queryset = queryset.distinct()
        return BaseVectorTileView.get(self, request=request, z=kwargs.get('z'), x=kwargs.get('x'), y=kwargs.get('y'))
