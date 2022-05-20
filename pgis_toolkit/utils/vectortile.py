from urllib.parse import unquote

import mercantile
from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.functions import GeoFunc, Transform
from django.db import connection
from django.db.models import Func, expressions, query
from django.http import HttpResponse, JsonResponse
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import DetailView, ListView
from rest_framework import status, viewsets

from pgis_toolkit.maps.models import FeatureCollection
# from core.agriculture.agromap_models import FeatureCollection
from pgis_toolkit.projects.models import ProjectLocationFeatureCollection


class BaseVectorTileMixin:
    """
    Base Mixin to handle vector tile generation
    """
    vector_tile_content_type = "application/x-protobuf"
    vector_tile_queryset = None
    vector_tile_queryset_limit = None
    vector_tile_layer_name = None
    vector_tile_geom_name = 'geometry'
    vector_tile_fields = None
    vector_tile_generation = None
    vector_tile_extent = 4096
    vector_tile_buffer = 256
    vector_tile_clip_geom = True

    @ classmethod
    def get_bounds(cls, x, y, z):
        """
        Get extent from xyz tile extent to 3857
        :param x : longitude coordinate tile
        :type x : int
        :param y : latitude coordinate tile
        :type y : int
        :param z : zoom level
        :type z : int
        :return : xmin , ymin , xmax , ymax in 3857 coordinate system
        :rtype : tuple
        """
        return mercantile.xy_bounds(x, y, z)

    def get_vector_tile_queryset(self):
        """
        Get feature queryset in tile dynamically
        """
        return self.vector_tile_queryset if self.vector_tile_queryset is not None else self.get_queryset()

    def get_vector_tile_queryset_limit(self):
        """
        Get feature limit by tile dynamically
        """
        return self.vector_tile_layer_name

    def get_vector_tile_layer_name(self):
        """
        Get layer name in tile dynamically
        """
        return self.vector_tile_layer_name

    def get_tile(self, x, y, z):
        """
        Generate a mapbox vector tile as bytearray
        :param x: longitude coordinate tile
        :type x: int
        :param y: latitude coordinate tile
        :type y: int
        :param z: zoom level
        :type z: int
        :return: Mapbox Vector Tile
        :rtype: bytearray
        """
        raise NotImplementedError()


class VectorLayer:
    vector_tile_layer_id = ""
    vector_tile_layer_description = ""
    vector_tile_layer_min_zoom = 0
    vector_tile_layer_max_zoom = 22

    def __init__(self, id_layer, description="", min_zoom=0, max_zoom=22):
        self.vector_tile_layer_id = id_layer
        self.vector_tile_layer_description = description
        self.vector_tile_layer_min_zoom = min_zoom
        self.vector_tile_layer_max_zoom = max_zoom

    def get_vector_tile_layer_id(self):
        return self.vector_tile_layer_id

    def get_vector_tile_layer_description(self):
        return self.vector_tile_layer_description

    def get_vector_tile_layer_min_zoom(self):
        return self.vector_tile_layer_min_zoom

    def get_vector_tile_layer_max_zoom(self):
        return self.vector_tile_layer_max_zoom

    def get_vector_layer(self):
        return{
            "id": self.get_vector_tile_layer_id(),
            "description": self.get_vector_tile_layer_description(),
            "fields": {},
            "minzoom": self.get_vector_tile_layer_min_zoom(),
            "maxzoom": self.get_vector_tile_layer_max_zoom()
        }


class BaseTileJSONMixin:
    vector_tile_tilejson_name = ""
    vector_tile_tilejson_attribution = ""
    vector_tile_tilejson_description = ""

    def get_vector_tile_tilejson_name(self):
        return self.vector_tile_tilejson_name

    def get_vector_tile_tilejson_attribution(self):
        return self.vector_tile_tilejson_attribution

    def get_vector_tile_tilejson_description(self):
        return self.vector_tile_tilejson_description

    def get_vector_tile_tilejson_min_zoom(self):
        min_zoom = min(item["minzoom"] for item in self.get_vector_layers())
        return min_zoom or 0

    def get_vector_tile_tilejson_max_zoom(self):
        max_zoom = max(item["maxzoom"] for item in self.get_vector_layers())
        return max_zoom or 0

    def get_tile_urls(self, tile_url, base_url=""):
        return [
            unquote(tile_url)
        ]

    def get_vector_layers(self):
        raise NotImplementedError(
            """ you should implement get_vector_layers to return a VectorLayer list""")

    def get_tilejson(self, tile_url, version="3.0.0"):
        return{
            "tilejson": version,
            "name": self.get_vector_tile_tilejson_name(),
            "attribution": self.get_vector_tile_tilejson_attribution(),
            "description": self.get_vector_tile_tilejson_description(),
            "minzoom": self.get_vector_tile_tilejson_min_zoom(),
            "maxzoom": self.get_vector_tile_tilejson_max_zoom(),
            "tiles": self.get_tile_urls(tile_url),
            "vector_layers": self.get_vector_layers(),
        }


class BaseVectorTileView:
    """
    Base mixin to handle vector tile in a django View
    """
    content_type = "application/vnd.mapbox-vector-tile"

    def get(self, request, z, x, y):
        """
        Handle GET request to serve tile
        :param request:
        :type request : HttpRequest
        :param x: longitude coordinate tile
        :type x : int
        :param y : latitude coordinate tile
        :type y : int
        :param z : zoom level
        :type z : int
        :rtype HTTPResponse
        """

        content = self.get_tile(x, y, z)
        status = 200 if content else 204

        return HttpResponse(content, content_type=self.content_type, status=status)


class TileJSONView(BaseTileJSONMixin, View):
    tile_url = None

    def get_tile_url(self):
        return self.tile_url

    def get(self, request, *args, **kwargs):
        return JsonResponse(self.get_tilejson(self.get_tile_url()))


class RawGeometryField(GeometryField):
    def select_format(self, compiler, sql, params):
        """
        Override complier format to not cast as bytea.
        ASMVTGeom is used in a custom sql raw. Generated queryset shouldnot not be executed without that.
        """
        return sql, params


class MakeEnvelope(Func):
    function = "ST_MAKEENVELOPE"

    def __init__(self, *expressions, output_field=None, **extra):
        super().__init__(*expressions, output_field=None, **extra)
        self.output_field = GeometryField(srid=expressions[4])


class AsMVTGeom(GeoFunc):
    function = "ST_ASMVTGEOM"

    @ cached_property
    def output_field(self):
        return RawGeometryField()


class PostgisBaseVectorTile(BaseVectorTileMixin):
    def get_tile(self, x, y, z):
        # get tile coordinates from x,y and z
        xmin, ymin, xmax, ymax = self.get_bounds(x, y, z)
        features = self.get_vector_tile_queryset()
        # keep features intersecting tile
        filters = {
            # GeoFuncMixin implicitly transfroms to SRID of geom
            f"{self.vector_tile_geom_name}__intersects": MakeEnvelope(xmin, ymin, xmax, ymax, 3857)
        }
        features = features.filter(**filters)
        # annotate prepared geometry for MVT
        features = features.annotate(geom_prepared=AsMVTGeom(Transform(self.vector_tile_geom_name, 3857),
                                                             MakeEnvelope(
            xmin, ymin, xmax, ymax, 3857),
            self.vector_tile_extent,
            self.vector_tile_buffer,
            self.vector_tile_clip_geom
        ))
        fields = self.vector_tile_fields + \
            ("geom_prepared",) if self.vector_tile_fields else ("geom_prepared",)
        # limit feature number if limit provided
        limit = self.get_vector_tile_queryset_limit()
        if limit:
            features = features[:limit]
        # keep values to include in tile (extra included fileds + geometry )
        features = features.values(*fields)
        sql, params = features.query.sql_with_params()
        with connection.cursor() as cursor:
            cursor.execute("SELECT ST_ASMVT(subquery.*,%s, %s, %s) FROM ({}) as subquery".format(sql),
                           params=[self.get_vector_tile_layer_name(),
                                   self.vector_tile_extent,
                                   "geom_prepared",
                                   *params
                                   ])
            row = cursor.fetchone()[0]
            return row.tobytes() if row else b''

#Project location MVT View
class ProjectLocationMVTView(BaseVectorTileView, PostgisBaseVectorTile, View):
    pass

class PostGISFeatureView(ProjectLocationMVTView, ListView):
    model = ProjectLocationFeatureCollection
    # vector_tile_layer_name = "file_data"
    vector_tile_fields = ("attributes",)


#Layer MVT View
class LayerMVTView(BaseVectorTileView, PostgisBaseVectorTile, View):
    pass

class PostGISFeatureView(LayerMVTView, ListView):
    model = FeatureCollection
    vector_tile_fields = ("layer", "attributes")
