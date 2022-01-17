import pandas as pd
import numpy as np
import geopandas as gpd
from preprocess import preprocess_data, include_static_data
import config as cfg
from dbscan import dbscan_clusters


class mooring_dbscan:
    def __init__(self, filepath, proj='epsg:3857'):
        """
        Constructor for creating a mooring DBSCAN Instance.
        Parameters

        geodf: GeoPandas dataframe
        ----------
        """
        df = pd.read_csv(filepath)
        df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs='epsg:4326')
        self.proj = proj
        self.data = df
        self.clusters = None


    def set_data(self, data):
        self.data = data

    def set_clusters(self, clusters):
        self.clusters = clusters


if __name__ == "__main__":
    moor = mooring_dbscan(cfg.AIS_CSV_IN)
    moor.set_data(preprocess_data(moor.data))
    moor.set_data(include_static_data(moor.data))
    moor.set_clusters(dbscan_clusters(moor.data))