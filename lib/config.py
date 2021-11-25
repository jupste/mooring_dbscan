import os

CFG_BASEPATH = os.path.dirname(__file__)
CFG_CSV_OUTPUT_DIR = os.path.join(CFG_BASEPATH, '..', 'data', 'csv')
AIS_CSV_IN = os.path.join(CFG_CSV_OUTPUT_DIR, 'test_ais.csv')
AIS_CSV_OUT = 'optics_clusters'
POLYGON_CSV_OUT = 'cluster_polygons'

### DBSCAN PARAMETERS
MIN_SAMPLES = 3
MAX_EPS_KM = 0.1
MAX_EPS_KM = MAX_EPS_KM/6371.0088

### DATA WRANGLING
USE_NAVIGATIONAL_STATUS = True
USE_MEDIAN_VALUES = True

### CLUSTER PARAMETERS

BUFFER_TO_CLUSTERS = 0.0005
VALIDATION_DATA = os.path.join(CFG_CSV_OUTPUT_DIR, 'test_ais.shp')


CSV_FILE_FOR_READ_anchs = os.path.join(CFG_CSV_OUTPUT_DIR, 'ports-to-csv.csv')
