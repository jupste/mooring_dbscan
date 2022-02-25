import os

CFG_BASEPATH = os.path.dirname(__file__)
CFG_CSV_OUTPUT_DIR = os.path.join(CFG_BASEPATH, 'data')
AIS_CSV_IN = os.path.join(CFG_CSV_OUTPUT_DIR, 'shipdata.rds')

MIN_SAMPLES = 3
MAX_EPS_KM = 0.05/6371.0088

MAPBOX_RESOLUTION = '300x200'
MAPBOX_TOKEN = os.environ['MAPBOX_TOKEN']
BUFFER_TO_CLUSTERS = 0.0005