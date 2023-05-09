import json
import os
import uuid

os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
# import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pandas as pd
from bson.json_util import dumps, loads
from shapely.geometry import LineString
from sqlalchemy import create_engine

from config.settings.base import MONGO_DB, env
from pgis_toolkit.maps.api.serializers import NetworkRoutesSerializer
from pgis_toolkit.maps.models import (
    Analysis,
    FeatureCollectionMirror,
    NetworkRoutes,
    OptimumRoute,
)

db_connection_url = env("CONNECTION_DB", default="postgresql://xIDokAfQUYOjTGhErprxMHnjZTJXMloY:gn63GjyG9AOKLYgrvOcOZFrAeYgjLOA4IkjuTXzISZ3nnMaHxTX1rSxI0fdBSb52@postgres:5432/pgis_toolkit")
con = create_engine(db_connection_url)


def generate_routes(origin_long, origin_lat, destination_long, destination_lat, k, G, analysis_id):
    errors=[]
    try:
        road_max_speed = 50 #kmph
        average_velocity = 3.6 #kmph
        nodes, edges = ox.graph_to_gdfs(G)
        orig_node_id, dist_to_orig = ox.distance.nearest_nodes(G, X=origin_long, Y=origin_lat, return_dist=True)
        dest_node_id, dist_to_dest = ox.distance.nearest_nodes(G, X=destination_long, Y=destination_lat, return_dist=True)
        print("Origin node-id:", orig_node_id, "and distance:", dist_to_orig, "meters.")
        print("Destination node-id:", dest_node_id, "and distance:", dist_to_dest, "meters.")
        routes_list = ox.distance.k_shortest_paths(G=G, orig=orig_node_id, dest=dest_node_id, k=k, weight='length')
        '''retrieve edges from array of nodes inside routes_list'''
        network_routes_objs = []
        bbox_list = []
        # analysis_id = uuid.uuid4()
        for route in routes_list:
            edge_df_list = []
            for i in range(0,len(route)-1):
                edge_df_list.append(edges.loc[route[i] , route[i+1], [0]])
            final_df = pd.concat(edge_df_list, ignore_index=False)
            merged_geom = final_df['geometry'].unary_union
            bbox = list(final_df.total_bounds)
            bbox_list.append(bbox)
            total_length = round(final_df['length'].sum(),2)
            total_time_secs = round(total_length/(road_max_speed/average_velocity),2)
            result_dict = {'geometry': merged_geom.wkt, 'length':total_length, 'travel_time':total_time_secs, 'bbox': bbox, 'analysis_id': analysis_id}
            serializer = NetworkRoutesSerializer(data=result_dict)
            if serializer.is_valid():
                network_routes_objs.append(NetworkRoutes(**result_dict))
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return str(errors),400
        network_routes_objs.sort(key = lambda x: x.length)
        route_index=1
        for nr in network_routes_objs:
            nr.route_no = route_index
            route_index+=1
        NetworkRoutes.active.bulk_create(network_routes_objs)
        '''update Analysis object bbox'''
        analysis_bbox = bbox_list[0]
        for bbox in bbox_list:
            if bbox[0] < analysis_bbox[0]: analysis_bbox[0]=bbox[0]
            if bbox[1] < analysis_bbox[1]: analysis_bbox[1]=bbox[1]
            if bbox[2] > analysis_bbox[2]: analysis_bbox[2]=bbox[2]
            if bbox[3] > analysis_bbox[3]: analysis_bbox[3]=bbox[3]
        analysis_inst = Analysis.active.get(id=analysis_id)
        analysis_inst.bbox=analysis_bbox
        analysis_inst.save()
        return analysis_id, 200
    except Exception as e:
        if Analysis.objects.filter(id=analysis_id).exists():
            Analysis.objects.get(id=analysis_id).delete()
        print("error occured in generate_routes: " + str(e))
        return (str(e), 400)

def convert_shp2graph(gdf, make_G_bidi = True, name='unamed'):
    """
    Converts shapefile to routable networkx graph.

    Parameters
    ----------
    p : str, File path - allowed formats geojson and ESRI Shapefile and other formats Fiona can read and write
    make_G_bidi : bool, if True, assumes linestrings are bidirectional
    name : str, Optional name of graph

    Returns
    -------
    G : graph
    """

    #gdf=gdf.to_crs(32645)
    gdf = gdf.explode(index_parts=True)
    gdf['length'] = None
    for i, row in gdf.iterrows():
        gdf.at[i,'length'] = row.geometry.length * 111139 # 1 degree ~ 111km

    # shapefile needs to include minimal: geometry linestring and the length computed (e.g. in QGIS)
    if 'length' not in gdf.columns:
        raise Exception('Shapefile is invalid: length not in attributes:\n{}'.format(gdf.columns))

    if  not gdf.geometry.map(lambda x: type(x) ==  LineString).all():
        s_invalid_geo = gdf.geometry[gdf.geometry.map(lambda x: type(x) ==  LineString)]
        raise Exception('Shapefile is invalid: geometry not all linestring \n{}'.format(s_invalid_geo))

    # Compute the start- and end-position based on linestring
    gdf['Start_pos'] = gdf.geometry.apply(lambda x: x.coords[0])
    gdf['End_pos'] = gdf.geometry.apply(lambda x: x.coords[-1])

    # Create Series of unique nodes and their associated position
    s_points = gdf.Start_pos.append(gdf.End_pos).reset_index(drop=True)

    # Add index of start and end node of linestring to geopandas DataFrame
    df_points = pd.DataFrame(s_points, columns=['Start_pos'])
    df_points = df_points.drop_duplicates(subset=['Start_pos'], keep='last')
    df_points['FNODE_'] = df_points.index
    gdf = pd.merge(gdf, df_points, on='Start_pos', how='inner')

    df_points = pd.DataFrame(s_points, columns=['End_pos'])
    df_points = df_points.drop_duplicates(subset=['End_pos'], keep='last')
    df_points['TNODE_'] = df_points.index
    gdf = pd.merge(gdf, df_points, on='End_pos', how='inner')

    # Bring nodes and their position in form needed for osmnx (give arbitrary osmid (index) despite not osm file)
    df_points.columns = ['pos', 'osmid']
    df_points[['x', 'y']] = df_points['pos'].apply(pd.Series)
    df_node_xy = df_points.drop('pos', 1)

    # Create Graph Object
    G = nx.MultiDiGraph(name=name, crs=gdf.crs)

    # Add nodes to graph
    for node, data in df_node_xy.T.to_dict().items():
        G.add_node(node, **data)

    # Add edges to graph
    for i, row  in gdf.iterrows():
        dict_row  = row.to_dict()
        if 'geometry' in dict_row: del dict_row['geometry']
        u=dict_row['FNODE_']
        v=dict_row['TNODE_']
        G.add_edge(u, v, **dict_row)

    if make_G_bidi:
        gdf.rename(columns={'Start_pos': 'End_pos',
                   'End_pos': 'Start_pos',
                   'FNODE_': 'TNODE_',
                   'TNODE_': 'FNODE_', }, inplace=True)

        # Add edges to graph
        for i, row  in gdf.iterrows():
            dict_row  = row.to_dict()
            if 'geometry' in dict_row: del dict_row['geometry']
            u=dict_row['FNODE_']
            v=dict_row['TNODE_']
            G.add_edge(u, v, **dict_row)
    return G

def optimum_path_analysis(road_network, mode, origin_long, origin_lat, destination_long, destination_lat, k, obstacles, analysis_id, optimum_route_id):
    errors=[]
    try:
        drive_osm_keys = ("primary", "secondary", "tertiary", "unclassified", "residential", "motorway")
        cycle_osm_keys = ('footway','service', 'path', 'track')
        walk_osm_keys = ('footway','service', 'path', 'track')
        if mode == 'drive':
            mode_keys = drive_osm_keys
        elif mode == 'cycle':
            mode_keys = cycle_osm_keys
        elif mode == 'walk':
            mode_keys = walk_osm_keys
        feature_qs = FeatureCollectionMirror.active.filter(layer=road_network)
        if feature_qs.exists():
            attribute_keys = feature_qs[0].attributes.keys()
            if 'highway' in attribute_keys:
                # feature_ids = tuple(feature_qs.filter(attributes__highway__in=mode_keys).values_list('id', flat=True))
                # mirro_coll = MONGO_DB['featurecollectionsmirror']
                # features = mirro_coll.find({"layer": road_network, "attributes.highway": {"$in":mode_keys}}, {"id":1, "_id":0})
                # features_json = json.loads(dumps(features))
                # feature_ids = ()
                # for data in features_json:
                #     feature_ids = feature_ids + (data['id'],)
                sql = f'''WITH segments AS (
                    SELECT id as id, (
                    ST_MakeLine(lag((pt).geom, 1, NULL) OVER (PARTITION BY id ORDER BY id, (pt).path), (pt).geom)) AS geometry
                    FROM (SELECT id, ST_DumpPoints(geometry) AS pt FROM (SELECT id, geometry FROM maps_featurecollectionmirror WHERE id IN (SELECT id FROM maps_featurecollectionmirror WHERE layer_id = {road_network} AND (attributes ->> 'highway') IN {mode_keys})) a) as dumps
                    )
                    SELECT * FROM segments WHERE geometry IS NOT NULL'''
            else:
                sql = f'''WITH segments AS (
                    SELECT id as id, (
                    ST_MakeLine(lag((pt).geom, 1, NULL) OVER (PARTITION BY id ORDER BY id, (pt).path), (pt).geom)) AS geometry
                    FROM (SELECT id, ST_DumpPoints(geometry) AS pt FROM (SELECT id, geometry FROM maps_featurecollectionmirror WHERE layer_id={road_network}) a) as dumps
                    )
                    SELECT * FROM segments WHERE geometry IS NOT NULL'''
        else:
            raise Exception('No features mirror found')
        # sql = f'''SELECT * FROM maps_featurecollectionmirror WHERE layer_id={road_network}'''
        segments = gpd.read_postgis(sql, con=con, geom_col="geometry", crs="epsg:4326")
        G = convert_shp2graph(segments)
        orig_node_id, dist_to_orig = ox.distance.nearest_nodes(G, X=origin_long, Y=origin_lat, return_dist=True)
        dest_node_id, dist_to_dest = ox.distance.nearest_nodes(G, X=destination_long, Y=destination_lat, return_dist=True)
        routes_list = ox.distance.k_shortest_paths(G=G, orig=orig_node_id, dest=dest_node_id, k=k, weight='length')
        road_max_speed = 50 #kmph
        if mode == "walk":
            average_velocity = 3.6
        elif mode == "cycle":
            average_velocity = 20
        else:
            average_velocity = 50
        nodes, edges = ox.graph_to_gdfs(G)
        '''retrieve edges from array of nodes inside routes_list'''
        network_routes_objs = []
        bbox_list = []
        try:
            for route in routes_list:
                edge_df_list = []
                for i in range(0,len(route)-1):
                    edge_df_list.append(edges.loc[route[i] , route[i+1], [0]])
                final_df = pd.concat(edge_df_list, ignore_index=False)
                merged_geom = final_df['geometry'].unary_union
                bbox = list(final_df.total_bounds)
                bbox_list.append(bbox)
                total_length = round(final_df['length'].sum(),2)
                # total_time_secs = round(total_length/(road_max_speed/average_velocity),2)
                total_time_secs = round(total_length/average_velocity,2)
                result_dict = {'geometry': merged_geom.wkt, 'length':total_length, 'travel_time':total_time_secs, 'bbox': bbox, 'analysis_id': analysis_id,'optimum_id':optimum_route_id}
                serializer = NetworkRoutesSerializer(data=result_dict)
                if serializer.is_valid():
                    network_routes_objs.append(NetworkRoutes(**result_dict))
                else:
                    for er in serializer._errors:
                        errors.append(
                            {'errorName': er, 'details': serializer._errors[er][0]})
                    return str(errors),400
            network_routes_objs.sort(key = lambda x: x.length)
            route_index=1
            for nr in network_routes_objs:
                nr.route_no = route_index
                nr.is_optimum = True if route_index == 1 else False
                route_index+=1
            network_list = NetworkRoutes.active.bulk_create(network_routes_objs)
            iterate = True
            while iterate:
                if NetworkRoutes.active.filter(optimum_id=optimum_route_id).exists():
                    iterate=False
            buffer_distance = 0.00004499640028797696 # 5m in degree
            if obstacles is not None:
                try:
                    for network in network_list:
                        network_id = network.id
                        obs_dict = {}
                        for obstacle in obstacles:
                            obs_sql = f'''SELECT p.* FROM (SELECT * FROM maps_networkroutes WHERE id={network_id}) l
                                        JOIN (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={obstacle} and is_deleted=false) p ON
                                        ST_Contains(ST_Buffer(l.geometry, {buffer_distance}), p.geometry)'''
                            obs = gpd.read_postgis(obs_sql, con=con, geom_col='geometry', crs="epsg:4326")
                            obs_dict[obstacle] = list(obs['id'])
                        route_inst = NetworkRoutes.active.get(id=network_id)
                        # route_inst.obstacles = json.dumps(obs_dict)
                        route_inst.obstacles = obs_dict
                        route_inst.save()
                except:
                    pass
            # '''update Analysis object bbox'''
            # analysis_bbox = bbox_list[0]
            # for bbox in bbox_list:
            #     if bbox[0] < analysis_bbox[0]: analysis_bbox[0]=bbox[0]
            #     if bbox[1] < analysis_bbox[1]: analysis_bbox[1]=bbox[1]
            #     if bbox[2] > analysis_bbox[2]: analysis_bbox[2]=bbox[2]
            #     if bbox[3] > analysis_bbox[3]: analysis_bbox[3]=bbox[3]
            # analysis_inst = Analysis.active.get(id=analysis_id)
            # analysis_inst.bbox=analysis_bbox
            # analysis_inst.save()
            optimum_route_inst = OptimumRoute.active.get(id=optimum_route_id)
            optimum_route_inst.bbox = bbox_list[0]
            optimum_route_inst.route_origin = [G.nodes[orig_node_id]['y'], G.nodes[orig_node_id]['x']]
            optimum_route_inst.route_destination = [G.nodes[dest_node_id]['y'], G.nodes[dest_node_id]['x']]
            optimum_route_inst.save()
            return analysis_id, optimum_route_id, "success", "", 200
        except Exception as e:
            if OptimumRoute.objects.filter(id=optimum_route_id).exists():
                OptimumRoute.objects.get(id=optimum_route_id).delete()
            return None, None, "route_not_found", str(e), 200
    except Exception as e:
        if OptimumRoute.objects.filter(id=optimum_route_id).exists():
            OptimumRoute.objects.get(id=optimum_route_id).delete()
        return None, None, "error", str(e), 400

def service_area_analysis(road_network, analysis_id, optimum_route_id):
    errors=[]
    try:
        sql = f'''WITH segments AS (
            SELECT id as id, (
            ST_MakeLine(lag((pt).geom, 1, NULL) OVER (PARTITION BY id ORDER BY id, (pt).path), (pt).geom)) AS geometry
            FROM (SELECT id, ST_DumpPoints(geometry) AS pt FROM (SELECT * FROM maps_featurecollectionmirror WHERE layer_id={road_network}) a) as dumps
            )
            SELECT * FROM segments WHERE geometry IS NOT NULL'''
        # sql = f'''SELECT * FROM maps_featurecollectionmirror WHERE layer_id={road_network}'''
        segments = gpd.read_postgis(sql, con=con, geom_col="geometry", crs="epsg:4326")
        G = convert_shp2graph(segments)
    except Exception as e:
        if Analysis.objects.filter(id=analysis_id).exists():
            Analysis.objects.get(id=analysis_id).delete()
        if OptimumRoute.objects.filter(id=optimum_route_id).exists():
            OptimumRoute.objects.get(id=optimum_route_id).delete()
        return None, "error", str(e), 400
