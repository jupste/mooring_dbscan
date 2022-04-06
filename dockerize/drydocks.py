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
import logging

## For logging purposes
class TimeFilter(logging.Filter):
    def filter(self, record):
        try:
          last = self.last
        except AttributeError:
          last = record.relativeCreated
        delta = datetime.datetime.fromtimestamp(record.relativeCreated/1000.0) - datetime.datetime.fromtimestamp(last/1000.0)
        record.relative = '{0:.2f}'.format(delta.seconds + delta.microseconds/1000000.0)
        self.last = record.relativeCreated
        return True


def preprocess_dry_docks(df):
    logging.info('[Start preprocessing]')
    df.drop_duplicates(['mmsiserial', 'position_timestamp'], inplace=True)
    df.sort_values('position_timestamp', inplace=True)
    df.drop(df[(df.sog>1) & (df.navigational_status=='Moored')].index, inplace=True)
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs ='epsg:4326')
    logging.info('[Made geodataframe]')
    gdf['mmsiserial'] = gdf['mmsiserial'].astype('category')
    gdf['nav_num'] = pd.factorize(gdf.navigational_status)[0]
    gdf.sort_values(['mmsiserial','position_timestamp'], inplace=True)
    gdf['prev_mmsi'] = gdf.mmsiserial.shift()
    gdf['new_berth'] = ((gdf.nav_num.diff()!=0) | (gdf.mmsiserial!=gdf.prev_mmsi))
    gdf['berth_num'] = gdf.new_berth.cumsum()
    logging.info('[Preprocess complete]')
    return gdf

def select_ports(df):
    dfs = []
    ports = gpd.read_file(cfg.PORT_FILE)
    port_points = ports[ports.PORT_NAME.isin(cfg.PORT_NAMES)].geometry.values
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.LON, df.LAT), crs = 'epsg:4326')
    distance = cfg.INCLUSION_ZONE
    for port in port_points:
        circle_buffer = port.buffer(distance)
        xmin, ymin, xmax, ymax = circle_buffer.envelope.bounds
        dfs.append(gdf.cx[xmin:xmax, ymin:ymax])
    df = pd.concat(dfs, ignore_index=True)
    return df

def calculate_centers(df):
    logging.info('[Calculate centers for mooring places]')
    df.sort_values(['mmsiserial', 'position_timestamp'], inplace=True)
    berth_visits = df[df.navigational_status=='Moored'].groupby('berth_num')
    lon = berth_visits.longitude.apply(pd.Series.median).values
    lat = berth_visits.latitude.apply(pd.Series.median).values
    center_coords = list(zip(lat,lon))
    logging.info('[Center calculation complete]')
    return center_coords

def dbscan_clusters(gdf):
    logging.info('[Run DBSCAN algorithm]')
    coords = calculate_centers(gdf)
    db = DBSCAN(eps=cfg.MAX_EPS_KM, min_samples=cfg.MIN_SAMPLES, algorithm='ball_tree', metric='haversine').fit(np.radians(coords))
    clusters = pd.DataFrame.from_dict({'lat':  [c[0] for c in coords], 'lon':[c[1] for c in coords], 'cluster': db.labels_})
    poly = make_polygons(clusters)
    logging.info('[Clustering complete]')
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
    poly_clusters['size'] = poly_clusters.anchorage_id.map(clusters.cluster.value_counts())
    poly_clusters['center'] = poly_clusters.geometry.apply(lambda x: x.centroid)
    
    return poly_clusters

def ship_duration_analysis(gdf):
    logging.info('[Start duration analysis]')
    gdf.sort_values(['mmsiserial', 'position_timestamp'], inplace=True)
    visits = gdf[gdf.cluster>-1].groupby('change_in_cluster')
    times = visits.position_timestamp.max()-visits.position_timestamp.min()
    clusters = visits.cluster.max()
    logging.info('[Created cluster dataframe]')
    visits_df = pd.DataFrame().from_dict({'time': times.values, 'cluster': clusters.values})
    visits_df = visits_df[visits_df.time>datetime.timedelta(hours=12)]
    result = pd.DataFrame(visits_df.groupby('cluster').time.mean())
    clusters = gdf.groupby('cluster')
    result['Unique ships'] = clusters.mmsiserial.nunique()
    result['Number of visits'] = clusters.change_in_cluster.nunique()
    result.rename(columns = {'time': 'Mean time in cluster'}, inplace = True)
    result.to_html('data/results/ship_durations.html')
    result.to_csv('data/results/ship_durations.csv')
    logging.info('[Duration analysis complete]')

def ship_type_analysis(gdf):
    logging.info('[Start ship type analysis]')
    ship_percentage = (gdf.groupby('cluster').ship_type.value_counts()/gdf.groupby('cluster').size()*100).drop(index=-1).reset_index(level=[1])
    ship_percentage.rename(columns= {0:'percentage'},inplace=True)
    ship_percentage.to_html('data/results/ship_types.html')
    ship_percentage.to_csv('data/results/ship_types.csv')
    logging.info('[Ship type analysis complete]')

def add_clusters_to_data(gdf, polygons):
    logging.info('[Adding clusters to data]')
    gdf['cluster'] = -1
    for i, cluster in polygons[1:].iterrows():
        geom = cluster.geometry
        sindex = gdf.sindex
        possible_matches_index = list(sindex.intersection(geom.bounds))
        possible_matches = gdf.iloc[possible_matches_index]
        precise_matches = possible_matches[possible_matches.intersects(geom)]
        gdf.loc[precise_matches.index, 'cluster'] = cluster.anchorage_id
    gdf.sort_values(['mmsiserial', 'position_timestamp'], inplace=True)
    logging.info('[Adding clusters to data done]')
    gdf['enters_cluster'] = (((gdf.cluster.diff() != 0) & (gdf.cluster>-1)) & (gdf.mmsiserial==gdf.prev_mmsi))
    gdf['leaves_cluster'] = (((gdf.cluster.diff() != 0) & (gdf.cluster==-1)) & (gdf.mmsiserial==gdf.prev_mmsi))
    gdf['leaves_cluster'] = gdf.leaves_cluster.shift(-1).fillna(False)
    gdf['change_in_cluster'] = (gdf['enters_cluster'] | gdf['leaves_cluster']).cumsum()
    logging.info('[Calculated changes in clusters]')
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
    logging.basicConfig(filename='app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=cfg.LOGGING_LEVEL)
    fmt = logging.Formatter(fmt="%(asctime)s (%(relative)ss) %(message)s")
    log = logging.getLogger()
    [hndl.addFilter(TimeFilter()) for hndl in log.handlers]
    [hndl.setFormatter(fmt) for hndl in log.handlers]
    rdf = pyreadr.read_r(cfg.AIS_CSV_IN)
    df = rdf[None].copy()
    if cfg.PORT_NAMES:
        df = select_ports(df)
    df = preprocess_dry_docks(df)
    polygons = dbscan_clusters(df)
    #polygons[1:].apply(lambda x: download_image(x), axis=1)
    df = add_clusters_to_data(df, polygons)
    ship_duration_analysis(df)
    ship_type_analysis(df)
    polygons.to_csv('data/results/clusters.csv')