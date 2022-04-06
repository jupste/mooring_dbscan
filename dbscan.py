import pandas as pd
import geopandas as gpd
from sklearn.cluster import DBSCAN
import numpy as np
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
import config as cfg
from shapely import geometry, wkt


def calculate_centers(df):
    df = select_ship_types(df)
    df.sort_values(['sourcemmsi', 't'], inplace=True)
    berth_visits = df[df.navigationalstatus==5].groupby('berth_num')
    lon = berth_visits.lon.apply(pd.Series.median).values
    lat = berth_visits.lat.apply(pd.Series.median).values
    center_coords = list(zip(lat,lon))
    return center_coords

def dbscan_clusters(gdf):
    coords = calculate_centers(gdf)
    epsilon = cfg.MAX_EPS_KM
    db = DBSCAN(eps=epsilon, min_samples=3, algorithm='ball_tree', metric='haversine').fit(np.radians(coords))
    clusters = pd.DataFrame.from_dict({'lat':  [c[0] for c in coords], 'lon':[c[1] for c in coords], 'cluster': db.labels_})
    poly = make_polygons(clusters)
    return poly

def make_polygons(clusters):
    clusters.sort_values(by=['cluster'], ascending=[True], inplace=True)
    clusters.reset_index(drop=True, inplace=True)
    clusters['geometry'] = [geometry.Point(xy) for xy in zip(clusters['lon'], clusters['lat'])]
    poly_clusters = gpd.GeoDataFrame()
    gb = clusters.groupby('cluster')
    for y in gb.groups:
        df0 = gb.get_group(y).copy()
        point_collection = geometry.MultiPoint(list(df0['geometry']))
        # point_collection.envelope
        convex_hull_polygon = point_collection.convex_hull
        poly_clusters = poly_clusters.append(pd.DataFrame(data={'cluster_id':[y],'geometry':[convex_hull_polygon]}))
    poly_clusters.reset_index(inplace=True)
    #poly_clusters.geometry = gpd.GeoSeries.from_wkt(poly_clusters['geometry'])
    poly_clusters.crs = 'epsg:4326'
    
    return poly_clusters

def validate_polygons(polygons):
    validation_data = cfg.VALIDATION_DATA
    print(polygons.dtypes)
    polygons.geometry = polygons.geometry.buffer(0.0005)
    for poly in polygons.geometry:
        intersect = False
        for line in validation_data.geometry:
            if poly.intersects(line):
                intersect= True
        assert intersect

def select_ship_types(df):
    vessel_types = []
    for types in cfg.VESSEL_TYPES:
        vessel_types = vessel_types + (list(range(types[0], types[1]+1)))
    return df[df.shiptype.isin(vessel_types)]

if __name__ == "__main__":
    df = pd.read_csv('processed_ais.csv')
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, crs='epsg:4326')
    print('[Stage 2 - Selecting ship types for clustering] Filtering ship types...')
    
    print('[Stage 3 - Data Clustering] Clustering with DBSCAN...')
    print('[Stage 4 - Cluster polygon creation] Create Polygons from Convex Hulls of DBSCAN Clusters...')

    polygons = make_polygons(gdf)
    #validate_polygons(polygons)
    polygons.to_csv(cfg.POLYGON_CSV_OUT)