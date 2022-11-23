import geopandas as gpd
# import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pandas as pd


# from descartes import PolygonPatch
# from shapely.geometry import LineString, Point, Polygon
def generate_routes(origin_long, origin_lat, destination_long, destination_lat, k, G):

    ox.config(log_console=True, use_cache=True)

    try:
        road_max_speed = 50 #kmph
        average_velocity = 3.6 #kmph
        nodes, edges = ox.graph_to_gdfs(G)
        orig_node_id, dist_to_orig = ox.distance.nearest_nodes(G, X=origin_long, Y=origin_lat, return_dist=True)
        dest_node_id, dist_to_dest = ox.distance.nearest_nodes(G, X=destination_long, Y=destination_lat, return_dist=True)
        print("Origin node-id:", orig_node_id, "and distance:", dist_to_orig, "meters.")
        print("Destination node-id:", dest_node_id, "and distance:", dist_to_dest, "meters.")
        routes_list = ox.distance.k_shortest_paths(G=G, orig=orig_node_id, dest=dest_node_id, k=k, weight='length')
        '''retrieve edges from array of nodes inside routes_list and retrieve array of dictionary containing routes'''
        route_no = 1
        for route in routes_list:
            edge_df_list = []
            for i in range(0,len(route)-1):
                edge_df_list.append(edges.loc[route[i] , route[i+1], [0]])
            final_df = pd.concat(edge_df_list, ignore_index=False)
            # print(final_df, "is final df")
            ''''''
            merged_geom = final_df['geometry'].unary_union
            total_length = final_df['length'].sum()
            total_time_secs = total_length/(road_max_speed/average_velocity)
            result_dict = {'route':route_no, 'geometry': merged_geom, 'length':total_length,'travel_time':total_time_secs}
            route_no+=1
            print(result_dict)
        return 'Route Table populated successfully!', 200
    except Exception as e:
        print("error occured in generate_routes: " + str(e))
        return (str(e), 400)
