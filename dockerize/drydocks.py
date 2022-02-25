import pandas as pd
import numpy as np
import geopandas as gpd
import config as cfg
import datetime
from sklearn.cluster import DBSCAN
import pyreadr
from shapely import geometry, wkt
import pyproj
from shapely.geometry import Point
from functools import partial
from shapely.ops import transform
import requests

def preprocess_dry_docks(df):
    df.drop_duplicates(['mmsiserial', 'position_timestamp'], inplace=True)
    df.sort_values('position_timestamp', inplace=True)
    df.drop(df[(df.sog>1) & (df.navigational_status=='Moored')].index, inplace=True)
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs ='epsg:4326')
    gdf['nav_num'] = pd.factorize(gdf.navigational_status)[0]
    gdf.sort_values('position_timestamp', inplace=True)
    gdf['new_berth'] = gdf.groupby('mmsiserial').nav_num.diff()>0
    gdf['berth_num'] = gdf.new_berth.cumsum()
    return gdf

def calculate_centers(df):
    df.sort_values(['mmsiserial', 'position_timestamp'], inplace=True)
    berth_visits = df[df.navigational_status=='Moored'].groupby('berth_num')
    lon = berth_visits.longitude.apply(pd.Series.median).values
    lat = berth_visits.latitude.apply(pd.Series.median).values
    center_coords = list(zip(lat,lon))
    return center_coords

def dbscan_clusters(gdf):
    coords = calculate_centers(gdf)
    db = DBSCAN(eps=cfg.MAX_EPS_KM, min_samples=cfg.MIN_SAMPLES, algorithm='ball_tree', metric='haversine').fit(np.radians(coords))
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
        poly_clusters = poly_clusters.append(pd.DataFrame(data={'anchorage_id':[y],'geometry':[convex_hull_polygon]}))
    poly_clusters.reset_index(inplace=True)
    #poly_clusters.geometry = gpd.GeoSeries.from_wkt(poly_clusters['geometry'])
    poly_clusters.crs = 'epsg:4326'
    return poly_clusters

def ship_duration_analysis(gdf):
    gdf.sort_values(['mmsiserial', 'position_timestamp'], inplace=True)
    visits = gdf[gdf.cluster>-1].groupby('change_in_cluster')
    times = visits.position_timestamp.max()-visits.position_timestamp.min()
    clusters = visits.cluster.describe()['max']
    visits_df = pd.DataFrame().from_dict({'time': times.values, 'cluster': clusters.values})
    visits_df = visits_df[visits_df.time>datetime.timedelta(hours=12)]
    result = pd.DataFrame(visits_df.groupby('cluster').time.mean())
    result.to_html('data/results/ship_durations.html')

def ship_type_analysis(gdf):
    ship_percentage = (gdf.groupby('cluster').ship_type.value_counts()/gdf.groupby('cluster').size()*100).drop(index=-999).reset_index(level=[1])
    ship_percentage.rename(columns= {0:'percentage'},inplace=True)
    ship_percentage.to_html('data/results/ship_types.html')

def add_clusters_to_data(gdf, polygons):
    gdf['cluster'] = -999
    for i, cluster in polygons[1:].iterrows():
        geom = cluster.geometry
        sindex = gdf.sindex
        possible_matches_index = list(sindex.intersection(geom.bounds))
        possible_matches = gdf.iloc[possible_matches_index]
        precise_matches = possible_matches[possible_matches.intersects(geom)]
        gdf.loc[precise_matches.index, 'cluster'] = cluster.anchorage_id
    gdf['enters_cluster'] = gdf.groupby('mmsiserial').cluster.diff()>0
    gdf['leaves_cluster'] = gdf.groupby('mmsiserial').cluster.diff()<0
    gdf['leaves_cluster'] = gdf.leaves_cluster.shift(-1).fillna(False)
    gdf['change_in_cluster'] = (gdf['enters_cluster'] | gdf['leaves_cluster']).cumsum()
    return gdf

def buffer_in_meters(coords, radius):
    lng = coords.geometry.centroid.xy[0][0]
    lat = coords.geometry.centroid.xy[1][0]
    proj_meters = pyproj.Proj('epsg:3857')
    proj_latlng = pyproj.Proj('epsg:4326')
    project_to_meters = partial(pyproj.transform, proj_latlng, proj_meters)
    project_to_latlng = partial(pyproj.transform, proj_meters, proj_latlng)
    pt_latlng = Point(lng, lat)
    pt_meters = transform(project_to_meters, pt_latlng)
    buffer_meters = pt_meters.buffer(radius)
    buffer_latlng = transform(project_to_latlng, buffer_meters)
    return buffer_latlng

def download_image(polygon):
    centroid = buffer_in_meters(polygon, 200)
    resolution = cfg.MAPBOX_RESOLUTION
    token = cfg.MAPBOX_TOKEN
    bounds = '[' + ','.join([str(x) for x in centroid.bounds]) + ']'
    url = f'https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/{bounds}/{resolution}?access_token={token}'
    r = requests.get(url)
    filename = f'data/img/cluster{polygon.anchorage_id}.jpeg'
    if r.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(r.content)
    return r

if __name__ == "__main__":
    rdf = pyreadr.read_r(cfg.AIS_CSV_IN)
    df = rdf[None].copy()
    df = preprocess_dry_docks(df)
    polygons = dbscan_clusters(df)
    polygons[1:].apply(lambda x: download_image(x), axis=1)
    df = add_clusters_to_data(df, polygons)
    ship_duration_analysis(df)
    ship_type_analysis(df)
    polygons.to_csv('data/results/clusters.csv')