import os

CFG_BASEPATH = os.path.dirname(__file__)
CFG_CSV_OUTPUT_DIR = os.path.join(CFG_BASEPATH, 'data')
AIS_CSV_IN = os.path.join(CFG_CSV_OUTPUT_DIR,'csv', 'test_ais.csv')
STATIC_CSV_IN = os.path.join(CFG_CSV_OUTPUT_DIR, 'csv', 'static_data.csv')
AIS_CSV_OUT = 'dbscan_clusters.csv'
POLYGON_CSV_OUT = 'brest_all_small.csv'
FILE_PREFIX = 'all_small'
### DBSCAN PARAMETERS
MIN_SAMPLES = 3
MAX_EPS_KM = 0.05
MAX_EPS_KM = MAX_EPS_KM/6371.0088

### DATA WRANGLING
USE_NAVIGATIONAL_STATUS = True
USE_MEDIAN_VALUES = True
PORT_FILE = os.path.join(CFG_CSV_OUTPUT_DIR, 'shape' ,'WPI.shp')
PORT_NAME = 'RADE DE BREST'
# Include shiptypes between values
VESSEL_TYPES = [(70,79)]
# Inclusion zone in degrees (0.01 degree is about 1.1 km)
INCLUSION_ZONE = 0.1

### CLUSTER PARAMETERS

BUFFER_TO_CLUSTERS = 0.0005
VALIDATION_DATA = os.path.join(CFG_CSV_OUTPUT_DIR, 'test', 'test.shp')


CSV_FILE_FOR_READ_anchs = os.path.join(CFG_CSV_OUTPUT_DIR, 'ports-to-csv.csv')
