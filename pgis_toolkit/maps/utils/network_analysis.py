import uuid

import geopandas as gpd
# import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pandas as pd

from pgis_toolkit.maps.api.serializers import NetworkRoutesSerializer
from pgis_toolkit.maps.models import Analysis, NetworkRoutes


def generate_routes(origin_long, origin_lat, destination_long, destination_lat, k, G):
    errors=[]
    try:
        analysis_inst = None
        name='Test Network Analysis 2'
        type='Nearest Path Analysis'
        display='True'
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
        # analysis_id = uuid.uuid4()
        for route in routes_list:
            edge_df_list = []
            for i in range(0,len(route)-1):
                edge_df_list.append(edges.loc[route[i] , route[i+1], [0]])
            final_df = pd.concat(edge_df_list, ignore_index=False)
            merged_geom = final_df['geometry'].unary_union
            total_length = round(final_df['length'].sum(),2)
            total_time_secs = round(total_length/(road_max_speed/average_velocity),2)
            result_dict = {'geometry': merged_geom.wkt, 'length':total_length, 'travel_time':total_time_secs}
            serializer = NetworkRoutesSerializer(data=result_dict)
            if serializer.is_valid():
                network_routes_objs.append(NetworkRoutes(**result_dict))
            else:
                for er in serializer._errors:
                    errors.append(
                        {'errorName': er, 'details': serializer._errors[er][0]})
                return str(errors),400
        '''create analysis object'''
        analysis_inst = Analysis.active.create(name=name, type=type, display=True, geom_type='LineString', project=1)
        '''arrange and assign analysis id and route no in NetworkRoutes object'''
        network_routes_objs.sort(key = lambda x: x.length)
        route_index=1
        for nr in network_routes_objs:
            nr.analysis_id = analysis_inst.id
            nr.route_no = route_index
            route_index+=1
        NetworkRoutes.active.bulk_create(network_routes_objs)
        return analysis_inst.id, 200
    except Exception as e:
        if analysis_inst:
            analysis_inst.delete()
        print("error occured in generate_routes: " + str(e))
        return (str(e), 400)
