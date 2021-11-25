import pandas as pd
from sklearn.cluster import DBSCAN
import numpy as np
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
import config as cfg


if __name__ == "__main__":
    print('filtering data...')
    df = pd.read_csv('port_data6km_ct.csv')
    df = df[df.navigationalstatus==5]
    coords = df[['lat', 'lon']].values
    kms_per_radian = 6371.0088
    epsilon = 0.1 / kms_per_radian
    print('starting clustering...')
    db = DBSCAN(eps=epsilon, min_samples=3, algorithm='ball_tree', metric='haversine').fit(np.radians(coords))
    print(db.labels_)