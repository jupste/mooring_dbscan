# Detecting and analyzing mooring clusters with DBSCAN

This program finds areas from AIS data that are used primarily for mooring ship i.e. berths and quays. This is done by generating clusters of the AIS with the DBSCAN algorithm. The clusters are then analyzed to gather insights on the infrastructure of the port area. 

The program consist of three stages that can be run individually or in concecutive fashion. The first stage does all the necessary preprocessing for the AIS data set, the second stage handles the clustering of the data with the DBSCAN algorithm and the final stage combines the AIS data and cluster data and analyzes the created clusters. 

To run all the steps use command 
`python mooring.py`


## Configurable parameters

The parameters for this program are set in the `lib/config.py` file. The program reads the AIS file path from `lib/data/csv/` 

For most uses the configuration of the epsilon parameter `MAX_EPS_KM`,`PORT_NAME` and `VESSEL_TYPES` should be enough. The `MAX_EPS_KM` is the DBSCAN epsilon parameter in kilometers, the `PORT_NAME` is the port name from `WPI.shp` file and the `VESSEL_TYPES` parameter contains all the vessel types used in the clustering.

## Preprocessing

The preprocessing stage filters the data and combines information from the static AIS messages to the dynamic messages. First, all the (ship-id, timestamp) duplicates are removed from the data. Second, new columns are created by parsing the time stamp to its components such as the time of day and the day of the week. Third, all the points outside a certain radius of the port to be analyzed are removed from the data. This radius is centred on the port coordinates from the World Port Index data set. And finally, the speed between sequential points is calculated. If a point has navigational status set as "moored" and a speed above a certain threshold, these points are removed from the data. 

To run just the preprocessing step use command

`python preprocess.py`

## DBSCAN clustering

The clustering points are derived from the median coordinates of each mooring visit. A mooring visit is a continuous timeframe when a ship is transmitting status code 5 (moored). This stage also converts the clusters to polygons.

To run the clustering step use command

`python dbscan.py`


## Analysis

The analysis uses the clusters created in the previous steps and combines them with the original AIS data. Using this combined data several metrics are analyzed to get a better picture of the port area. 

The following things are analyzed:

- Arrival and departing hours by cluster
- Maximum ship dimension per cluster
- Average duration within each cluster
- Distribution of ship types per cluster

To run the analysis step use command

`python analysis.py`


