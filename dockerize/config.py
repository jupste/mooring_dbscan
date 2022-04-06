import os
import logging
CFG_BASEPATH = os.path.dirname(__file__)
CFG_CSV_OUTPUT_DIR = os.path.join(CFG_BASEPATH, 'data')
AIS_CSV_IN = os.path.join(CFG_CSV_OUTPUT_DIR, 'shipdata.rds')

PORT_FILE = os.path.join(CFG_CSV_OUTPUT_DIR, 'shape' ,'WPI.shp')
PORT_NAMES = []
INCLUSION_ZONE = 0.1

MIN_SAMPLES = 5
MAX_EPS_KM = 0.1/6371.0088

MAPBOX_RESOLUTION = '300x200'
#MAPBOX_TOKEN = os.environ['MAPBOX_TOKEN']
BUFFER_TO_CLUSTERS = 0.0005
LOGGING_LEVEL = logging.DEBUG