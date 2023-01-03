import uuid

import geopandas as gpd
# import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pandas as pd

from pgis_toolkit.maps.api.serializers import NetworkRoutesSerializer
from pgis_toolkit.maps.models import Analysis, NetworkRoutes


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

def service_area_analysis():
    pass