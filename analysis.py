from contextlib import redirect_stderr
import pandas as pd
import geopandas as gpd
from sklearn.cluster import DBSCAN
import numpy as np
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
import config as cfg
from shapely import geometry, wkt
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import datetime
import plotly.express as px
import pandas as pd

# Parallelize with dask
def add_clusters_to_data(gdf, polygons):
    gdf['cluster'] = -999
    for i, cluster in polygons[1:].iterrows():
        geom = cluster.geometry
        sindex = gdf.sindex
        possible_matches_index = list(sindex.intersection(geom.bounds))
        possible_matches = gdf.iloc[possible_matches_index]
        precise_matches = possible_matches[possible_matches.intersects(geom)]
        gdf.loc[precise_matches.index, 'cluster'] = cluster.anchorage_id
    return gdf

def ship_visit_gantt_chart(gdf):
    gdf.sort_values(['sourcemmsi', 't'], inplace=True)
    stops = df_geo.groupby(['change_in_cluster'])
    a,b,c  = stops.Date.min(), stops.Date.max(), stops.cluster.max()
    stops_df = pd.DataFrame().from_dict({'cluster':c, 'date_min':a, 'date_max':b})
    stops_df['berth_num'] = stops_df.index
    fig = px.timeline(stops_df[stops_df.cluster>=0], x_start="date_min", x_end="date_max", y="cluster", color='berth_num')
    fig.write_html(str(cfg.FILE_PREFIX + '_gantt.html'))

# Parallellize?
def arrival_departing_analysis(gdf):
    gdf.sort_values(['sourcemmsi','t'], inplace=True)
    gdf['enters_cluster'] = gdf.groupby('sourcemmsi').cluster.diff()>0
    gdf['leaves_cluster'] = gdf.groupby('sourcemmsi').cluster.diff()<0
    gdf['leaves_cluster'] = gdf.leaves_cluster.shift(-1).fillna(False)
    gdf['change_in_cluster'] = (gdf['enters_cluster'] | gdf['leaves_cluster']).cumsum()
    arrivals = gdf[gdf.enters_cluster].groupby('cluster').hour.value_counts()
    departures = gdf[gdf.leaves_cluster].groupby('cluster').hour.value_counts()
    draw_hour_plot(arrivals, 'Arrival hours', str(cfg.FILE_PREFIX + '_arrival-plot.png'))
    draw_hour_plot(departures, 'Departure hours', str(cfg.FILE_PREFIX + '_departure-plot.png'))
    return gdf

def draw_hour_plot(hours, title, filename):
    fig, ax = plt.subplots()
    # clusters = [27,28,29, 8, 5, 10]
    hours = hours.rename('count').reset_index()
    #hours = hours[hours['cluster'].isin(clusters)]
    loc = plticker.MultipleLocator(base=1.0)
    ax.set_xlim(0,23)
    ax.set_ylim(0,max(hours['count'])+1)
    ax.set_ylabel('count')
    ax.set_xlabel('hour')
    ax.xaxis.set_major_locator(loc)
    for cluster in hours.cluster.unique():
        data = hours.loc[hours.cluster==cluster]
        data.sort_values('hour', inplace=True)
        line, = ax.plot(data.hour.values, data['count'].values)
        line.set_label(str('Cluster ' + str(cluster)))
    ax.set_title(title, size=32)
    
    box = ax.get_position()
    #ax.set_position([box.x0 + box.width, box.y0 + box.height * 0.1,
    #             box.width, box.height * 0.90])
    lgd = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1),
          fancybox=True, shadow=True, ncol=4)
    plt.savefig(filename, bbox_extra_artists=(lgd,), bbox_inches='tight')
    #plt.show()

def ship_dimension_analysis(gdf):
    clusters = gdf.groupby('cluster')
    result_df = pd.DataFrame(columns=['max_length', 'max_beam', 'max_draft'])
    result_df.max_length = clusters.length.quantile(0.99, interpolation='nearest')
    result_df.max_beam = clusters.beam.quantile(0.99, interpolation='nearest')
    result_df.max_draft = clusters.draft.quantile(0.99, interpolation='nearest')
    return result_df

def draft_change_analysis(gdf):
    gdf = gdf[gdf.draft!=0]
    gdf['draft_change'] = gdf.sort_values(['sourcemmsi','t']).groupby('sourcemmsi').draft.diff()
    gdf.draft_change.fillna(0, inplace=True)
    draft_rows = gdf[gdf.draft_change!=0].groupby('cluster')
    num_draft_change = draft_rows.size()
    av_draft_change = draft_rows.draft_change.describe()['mean']
    return num_draft_change, av_draft_change

def ship_duration_analysis(gdf):
    gdf.sort_values(['sourcemmsi','t'], inplace=True)
    visits = gdf[gdf.cluster>-1].groupby('change_in_cluster')
    times = visits.t.max()-visits.t.min()
    times = times.apply(lambda x: datetime.timedelta(seconds=x))
    clusters = visits.cluster.describe()['max']
    visits_df = pd.DataFrame().from_dict({'time': times.values, 'cluster': clusters.values})
    visits_df = visits_df[visits_df.time>datetime.timedelta(hours=12)]
    return visits_df.groupby('cluster').time.mean()

def ship_type_analysis(gdf):
    ship_percentage = (gdf.groupby('cluster').shiptype.value_counts()/gdf.groupby('cluster').size()*100).drop(index=-999).reset_index(level=[1])
    ship_percentage.rename(columns= {0:'percentage'},inplace=True)
    ship_percentage.to_html('ship_types.html')

def analysis_dataframe(gdf):
    dimensions = ship_dimension_analysis(gdf)
    duration = ship_duration_analysis(gdf)
    num_draft_change, av_draft_change = draft_change_analysis(gdf)
    result_df = pd.DataFrame()
    result_df['Unique ships'] = gdf.groupby('cluster').sourcemmsi.nunique()
    result_df['Number of visits'] = gdf.groupby('cluster').change_in_cluster.nunique()
    result_df[['Max length', 'Max beam', 'Max draft']] = dimensions
    result_df['Median time in cluster'] =  duration
    result_df['Number of draft changes'] = num_draft_change
    result_df['Average draft change'] = av_draft_change
    result_df.to_html(str(cfg.FILE_PREFIX + '_results.html'))

if __name__ == "__main__":
    df = pd.read_csv('processed_ais.csv')
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, crs='epsg:4326')
    gdf.Date = gdf.Date.apply(pd.to_datetime)
    polygons = pd.read_csv(cfg.POLYGON_CSV_OUT)
    polygons['geometry'] = polygons['geometry'].apply(wkt.loads)
    
    polygons = gpd.GeoDataFrame(polygons, crs='epsg:4326')
    polygons.geometry = polygons.geometry.buffer(0.0002)
   
    gdf = add_clusters_to_data(gdf, polygons)
    arrival_departing_analysis(gdf)
    dimensions = ship_dimension_analysis(gdf)
    #types = ship_type_analysis(gdf)
    duration = ship_duration_analysis(gdf)
    result_df = pd.DataFrame()
    result_df['Unique ships'] = gdf.groupby('cluster').sourcemmsi.nunique()
    result_df['Number of visits'] = gdf.groupby('cluster').change_in_cluster.nunique()
    result_df[['Max length', 'Max beam', 'Max draft']] = dimensions
    result_df['Median time in cluster'] =  duration
    #types.to_html(str(cfg.FILE_PREFIX + '_types.html'))
    result_df.to_html(str(cfg.FILE_PREFIX + '_results.html'))