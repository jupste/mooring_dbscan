import pandas as pd
import geopandas as gpd
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
    # Create circle buffer from port points
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
    return df

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

if __name__ == "__main__":
    print('[Stage 1 - Load/preprocess data] Preprocessing Input AIS...')
    df = pd.read_csv(cfg.AIS_CSV_IN)
    #df = df[df[' SHIPTYPE'] == 'CONTAINER SHIP']
    #df.rename(columns={' LON':'lon', ' LAT':'lat', 'MMSI':'sourcemmsi', ' TIMESTAMP_UTC': 't', ' STATUS': 'navigationalstatus'}, inplace=True)
    #df.t = df.t.astype('int')/(10**9)
    df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs='epsg:4326')
    df = include_static_data(df)
    df = preprocess_data(df)
    df.to_csv('processed_ais.csv')
