import pandas as pd
import numpy as np
import geopandas as gpd
from preprocess import preprocess_data, include_static_data
import config as cfg
from dbscan import dbscan_clusters
from analysis import add_clusters_to_data, arrival_departing_analysis, analysis_dataframe, ship_type_analysis
from datetime import datetime
import dask.dataframe as dd


class mooring_dbscan:
    def __init__(self, filepath, proj='epsg:3857'):
        """
        Constructor for creating a mooring DBSCAN Instance.
        Parameters

        geodf: GeoPandas dataframe
        ----------
        """
        dtypes={'sourcemmsi': 'str', 'navigationalstatus': 'float32', 'rateofturn': 'float32', 'speedoverground': 'float32', 'courseoverground': 'float32', 
                'trueheading': 'float32', 'lon':'float32', 'lat': 'float32', 't':'int64'}

        df = pd.read_csv(filepath, dtype=dtypes)
        #df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs='epsg:4326')
        self.proj = proj
        self.data = df
        self.data_dd = None
        self.clusters = None


    def set_data(self, data):
        self.data = data

    def set_clusters(self, clusters):
        self.clusters = clusters

    def make_gdf(self):
        df = self.data
        self.set_data(gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs='epsg:4326'))

if __name__ == "__main__":
    start = datetime.now()
    print('[Stage 1 - Load data] Loading Input AIS...')
    moor = mooring_dbscan(cfg.AIS_CSV_IN)
    interval1 = datetime.now()
    print('[Time taken]:'+str(interval1-start))
    print('[Stage 2 - Preprocess data] Preprocessing Input AIS...')
    moor.set_data(preprocess_data(moor.data))
    print('preprocess done...')
    moor.set_data(include_static_data(moor.data))
    interval2 = datetime.now()
    print('[Time taken]:'+str(interval2-interval1))
    print('[Stage 3 - Data Clustering] Clustering with DBSCAN...')
    moor.set_clusters(dbscan_clusters(moor.data))
    interval3 = datetime.now()
    print('[Time taken]:'+str(interval3-interval2))
    print('[Stage 4 - Adding cluster labels to AIS data] Adding cluster labels...')
    moor.set_data(add_clusters_to_data(moor.data, moor.clusters))
    interval4 = datetime.now()
    print('[Time taken]:'+str(interval4-interval3))
    print('[Stage 5 - Analysis of AIS data] Running analysis steps on AIS data...')
    moor.make_gdf()
    arrival_departing_analysis(moor.data)
    ship_type_analysis(moor.data)
    analysis_dataframe(moor.data)
    interval5 = datetime.now()
    print('[Time taken]:'+str(interval5-interval4))
    print('[Total time]:'+str(interval5-start))