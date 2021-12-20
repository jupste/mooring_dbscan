import pandas as pd
import geopandas as gpd
from sklearn.cluster import DBSCAN
import numpy as np
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
import config as cfg
from shapely import geometry


def preprocess_data(df):
    df.drop_duplicates(['sourcemmsi', 't'], inplace=True)
    # Filter out points outside port area
    df.sort_values(['sourcemmsi', 't'], inplace=True)

    # Time preprocessing
    df.loc[:,'Date'] = pd.to_datetime(df.t,unit='s')
    df.loc[:,'Date'] = df['Date'].apply(lambda x: x.tz_localize('UTC').tz_convert('Europe/Paris'))
    df.loc[:,'clock'] = df.Date.apply(lambda x: x.time())
    df.loc[:,'hour'] = df.Date.apply(lambda x: x.hour)
    df.loc[:,'weekday'] = df.Date.apply(lambda x: x.weekday())
    # Filter out points that are outside port area 
    ports = gpd.read_file(cfg.PORT_FILE)
    port_point = ports[ports.PORT_NAME==cfg.PORT_NAME].geometry.values[0]
    # Create circle buffer from port point
    distance = cfg.INCLUSION_ZONE
    circle_buffer = port_point.buffer(distance)
    df = df[df.geometry.apply(lambda x: x.within(circle_buffer))]
    # Calculate speed 
    df.loc[:,'dt'] = (df.groupby('sourcemmsi')['t'].diff()).values  # Diff Time in seconds
    df.loc[:,'lon_prev'] = np.radians((df.groupby('sourcemmsi')['lon'].shift()).values)  
    df.loc[:,'lat_prev'] = np.radians((df.groupby('sourcemmsi')['lat'].shift()).values)
    df.loc[:,'lonrad'] = np.radians(df['lon'])
    df.loc[:,'latrad'] = np.radians(df['lat'])
    dlon = df.lon_prev - df.lonrad 
    dlat = df.lat_prev - df.latrad
    a = np.sin(dlat/2)**2 + np.cos(df.latrad) * np.cos(df.lat_prev) * np.sin(dlon/2)**2
    df.loc[:,'dist_m'] = (2 * np.arctan2(np.sqrt(a), np.sqrt(1-a)))*6371000
    df.loc[:,'calculated_speed'] = df.dist_m/df.dt
    # Drop values where speed is significant and nav status 5
    df.drop(df[(df.calculated_speed>1) & (df.navigationalstatus==5)].index, inplace=True)
    '''
    vessel_types = cfg.VESSEL_TYPES
    df_filtered = pd.DataFrame()
    # Include selected vesseltypes
    for num_tuple in vessel_types:
        df_filtered = pd.concat([df_filtered, df[(df.vessel_type_num>=num_tuple[0]) & (df.vessel_type_num<=num_tuple[1])]])
    
    '''
    return df#_filtered

def include_static_data(df):
    # include dimensions
    static = pd.read_csv(cfg.STATIC_CSV_IN)
    static['length'] = static.tobow + static.tostern
    static['beam'] = static.tostarboard + static.toport
    

    # include shiptype
    ships = static.groupby('sourcemmsi')
    types = ships.shiptype.describe()
    lengths = ships.length.describe()
    beams = ships.beam.describe()
    drafts = ships.draught.describe()

    shiptype_dict = dict(zip(types.index, types['50%'].replace(0, np.nan).values))
    length_dict = dict(zip(lengths.index, lengths['50%'].replace(0, np.nan).values))
    beam_dict = dict(zip(beams.index, beams['50%'].replace(0, np.nan).values))
    draft_dict = dict(zip(drafts.index, drafts['50%'].replace(0, np.nan).values))
    df['vessel_type_num'] = df.sourcemmsi.apply(lambda x: shiptype_dict[x] if x in shiptype_dict.keys() else np.nan)
    df['length'] = df.sourcemmsi.apply(lambda x: length_dict[x] if x in length_dict.keys() else np.nan)
    df['beam'] = df.sourcemmsi.apply(lambda x: beam_dict[x] if x in beam_dict.keys() else np.nan)
    df['draft'] = df.sourcemmsi.apply(lambda x: draft_dict[x] if x in draft_dict.keys() else np.nan)

    return df

def calculate_centers(df):
    df['new_berth'] = df.sort_values('t').groupby('sourcemmsi').navigationalstatus.diff()>0

    df['berth_num'] = df.new_berth.cumsum()
    df.sort_values(['sourcemmsi', 't'], inplace=True)
    berth_visits = df[df.navigationalstatus==5].groupby('berth_num')

    lon = berth_visits.lon.describe()['50%'].values
    lat = berth_visits.lat.describe()['50%'].values
    center_coords = list(zip(lat,lon))
    return center_coords

def dbscan_clusters(coords):
    epsilon = cfg.MAX_EPS_KM
    db = DBSCAN(eps=epsilon, min_samples=3, algorithm='ball_tree', metric='haversine').fit(np.radians(coords))
    clusters = pd.DataFrame.from_dict({'lat':  [c[0] for c in coords], 'lon':[c[1] for c in coords], 'cluster': db.labels_})
    return clusters

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

def validate_polygons(polygons):
    validation_data = cfg.VALIDATION_DATA
    print(polygons)
    polygons.geometry = polygons.geometry.buffer(0.0005)
    for poly in polygons.geometry:
        intersect = False
        for line in validation_data.geometry:
            if poly.intersects(line):
                intersect= True
        assert intersect

def enrich_ais_data():
    pass

if __name__ == "__main__":
    print('[Stage 1 - Load/preprocess data] Preprocessing Input AIS...')
    df = pd.read_csv(cfg.AIS_CSV_IN)
    df = df[df[' SHIPTYPE'] == 'CONTAINER SHIP']
    df.rename(columns={' LON':'lon', ' LAT':'lat', 'MMSI':'sourcemmsi', ' TIMESTAMP_UTC': 't', ' STATUS': 'navigationalstatus'}, inplace=True)
    df.t = pd.to_datetime(df.t)
    df.t = df.t.astype('int')/(10**9)
    print('loading geodf...')
    df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs='epsg:4326')

    print('preprocessing...')
    #df = include_static_data(df)
    df = preprocess_data(df)
    
    print(df)
    print('[Stage 2 - Data Clustering] Clustering with DBSCAN...')

    centroids = calculate_centers(df)
    clusters = dbscan_clusters(centroids)
    print('[Stage 3 - Cluster polygon creation] Create Polygons from Convex Hulls of DBSCAN Clusters...')

    polygons = make_polygons(clusters)
    #validate_polygons(polygons)
    polygons.to_csv(cfg.POLYGON_CSV_OUT)


    '''
    print('convex'); anchs_clusters, anchs_clusters_gdf = fun_convex_hull(df)

    df = df[df.navigationalstatus==5]
    coords = df[['lat', 'lon']].values
    kms_per_radian = 6371.0088
    epsilon = 0.1 / kms_per_radian
    print('starting clustering...')
    db = DBSCAN(eps=epsilon, min_samples=3, algorithm='ball_tree', metric='haversine').fit(np.radians(coords))
    print(db.labels_)
    '''