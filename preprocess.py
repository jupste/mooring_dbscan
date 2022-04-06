import pandas as pd
import geopandas as gpd
import numpy as np
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
import config as cfg
from shapely import geometry

def preprocess_data(df):
    #df.drop_duplicates(['sourcemmsi', 't'], inplace=True).compute()
    # Filter out points outside port area
    #df = df.copy()
    df = df.sort_values('t')
    # Time preprocessing
    df['Date'] = pd.to_datetime(df.t, unit='s')
    df['hours'] = df.Date.apply(lambda x: x.hour)
    df['weekday'] = df.Date.apply(lambda x: x.weekday())
    
    def calculate_speed(df):
        dt = df.groupby('sourcemmsi')['t'].diff().values
        lon_prev = np.radians((df.groupby('sourcemmsi')['lon'].shift()).values)
        lat_prev = np.radians((df.groupby('sourcemmsi')['lat'].shift()).values)
        lonrad = np.radians(df['lon'])
        latrad = np.radians(df['lat'])
        dlon = lon_prev - lonrad 
        dlat = lat_prev - latrad
        a = np.sin(dlat/2)**2 + np.cos(latrad) * np.cos(lat_prev) * np.sin(dlon/2)**2
        dist_m = (2 * np.arctan2(np.sqrt(a), np.sqrt(1-a)))*6371000
        return dist_m/dt
    df['speed'] = calculate_speed(df)
    # Drop values where speed is significant and nav status 5
    df.drop(df[(df.speed>1) & (df.navigationalstatus==5)].index, inplace=True)
    df.reset_index(inplace=True)
    return df

def include_static_data(df):
    # include dimensions
    #df = df.copy()
    dtypes = {'sourcemmsi': 'str', 'imonumber': 'float32', 'callsign':'str', 'shipname':'str', 
        'shiptype': 'float32','tobow': 'float32', 'tostern': 'float32', 'tostarboard': 'float32', 'toport': 'float32', 'eta': 'str', 'draught': 'float32',
        'destination': 'str', 'mothershipmmsi': 'str', 't': 'int64'}
    static = pd.read_csv('lib/data/csv/static_data.csv', dtype=dtypes)
    dfs = []
    df = df.sort_values('t')
    static = static.sort_values('t')
    intersection = list(set(df.sourcemmsi.unique()) & set(static.sourcemmsi.unique()))
    static_groups = static.groupby('sourcemmsi')
    dynamic_groups = df.groupby('sourcemmsi')
    for mmsi in intersection:
        a = dynamic_groups.get_group(mmsi)
        b = static_groups.get_group(mmsi)
        c = pd.merge_asof(a, b, on='t', direction='nearest')
        dfs.append(c)
    df = pd.concat(dfs)
    df.drop(columns = 'sourcemmsi_y', inplace=True)
    df.rename(columns = {'sourcemmsi_x': 'sourcemmsi'}, inplace = True)
    df.shiptype.fillna(0, inplace=True)
    df['length'] = df.tobow + df.tostern
    df['beam'] = df.tostarboard + df.toport
    df = df.rename(columns = {'draught':'draft'})
    df.sort_values('t', inplace=True)
    # Remove columns with m ore than 80% missing values
    limitPer = len(df) * .80
    df = df.dropna(thresh=limitPer, axis=1)
    df = df.drop_duplicates(['sourcemmsi', 't'])
    df = df.sort_values(['sourcemmsi', 't'])
    df['prev_mmsi'] = df.sourcemmsi.shift()
    df['new_berth'] = ((df.navigationalstatus.diff()!=0) | (df.sourcemmsi!=df.prev_mmsi))
    df['berth_num'] = df.new_berth.cumsum()
    df.reset_index(inplace=True)
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs='epsg:4326')
    ports = gpd.read_file(cfg.PORT_FILE)
    port_point = ports[ports.PORT_NAME.isin(cfg.PORT_NAME)].geometry.values[0]
    # Create circle buffer from port points
    distance = cfg.INCLUSION_ZONE
    circle_buffer = port_point.buffer(distance)
    xmin, ymin, xmax, ymax = circle_buffer.envelope.bounds
    gdf = gdf.cx[xmin:xmax, ymin:ymax]
    return gdf
    
if __name__ == "__main__":
    print('[Stage 1 - Load/preprocess data] Preprocessing Input AIS...')
    dtypes={'sourcemmsi': 'str', 'navigationalstatus': 'float32', 'rateofturn': 'float32', 'speedoverground': 'float32', 'courseoverground': 'float32', 
                'trueheading': 'float32', 'lon':'float32', 'lat': 'float32', 't':'int64'}

    df = pd.read_csv(cfg.AIS_CSV_IN, dtype=dtypes)
    #df = df[df[' SHIPTYPE'] == 'CONTAINER SHIP']
    #df.rename(columns={' LON':'lon', ' LAT':'lat', 'MMSI':'sourcemmsi', ' TIMESTAMP_UTC': 't', ' STATUS': 'navigationalstatus'}, inplace=True)
    #df.t = df.t.astype('int')/(10**9)
    df = preprocess_data(df)
    df = include_static_data(df)
    df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs='epsg:4326')
    
    #df.to_csv('processed_ais.csv')
