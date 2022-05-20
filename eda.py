
import pandas as pd
import sqlite3
from matplotlib import pyplot as plt
from matplotlib.ticker import FormatStrFormatter
from geopy.distance import geodesic as GD
import geopandas as gpd
import json
from shapely.geometry import Polygon, Point, LineString
from shapely.geometry.multipolygon import MultiPolygon
import folium
import contextily as cx
from OSMPythonTools.overpass import Overpass
import pickle


# TIER Zone data
# -------------------------------------------------------
def get_zones(filename): 
    f = open(filename)
    res = json.load(f)
    atts = [x['attributes'] for x in res['data']]
    locs = pd.DataFrame(atts)

    locs['geometry'] = locs.apply(lambda x: Polygon([(c['lng'], c['lat']) for c in x.polygon]), 1)
    zones = gpd.GeoDataFrame(locs, geometry="geometry", crs='epsg:4326')
    return zones

constrained = get_zones('./data/constrained_malmo_tier.json')
singles = constrained[constrained.zoneConstraints.map(len) == 1]

noParkingSlow = constrained[constrained.zoneConstraints.map(len) == 2]
slowZone = singles[singles.zoneConstraints.map(lambda x: x[0]) == 'speedReduction']
noParking = singles[singles.zoneConstraints.map(lambda x: x[0]) == 'noParking']
parking = get_zones('./data/parking_malmo_tier.json')
root_zone = get_zones('./data/root_malmo_tier.json')
parking_centroids = gpd.GeoDataFrame(parking, geometry=gpd.points_from_xy(parking.lng, parking.lat), crs='epsg:4326')

ax = root_zone.plot()
plt.show()

mp = MultiPolygon(list(noParkingSlow.to_crs(epsg=3857).geometry))
# Save shape as SVG
with open('noParkingSlow.svg', 'w') as f:
    f.write(mp._repr_svg_())

# Plot restricted zones
# -------------------------------------------------------
constrained.iloc[0]

# Malmö SCB (DeSO) boundaries
# -------------------------------------------------------
reso = gpd.read_file('./data/SE_deso_boundaries.gpkg')
malmo = reso[reso.kommunnamn == 'Malmö']
malmo = malmo.set_crs(epsg=3006).to_crs(epsg=4326)

# Plot matplotlib
cols = ['r', 'g', 'b', 'y', 'k']
color = [cols[x%4] for x in range(len(malmo))]
malmo.plot(color=color)
plt.show()

# Plot folium
m = folium.Map([55.58791, 13.00081], zoom_start=12, tiles='cartodbpositron')
folium.GeoJson(test['from']).add_to(m)
m.save("map.html")


# Overlap between TIER operational area and DeSO areas
overlap = gpd.overlay(malmo, root_zone, how='intersection')
tier_deso = malmo[malmo.deso.isin(overlap.deso)]
non_tier_deso = malmo[~malmo.deso.isin(overlap.deso)]

# Population data
# -------------------------------------------------------
f = open('./data/population_age_deso.json')
population_json = json.load(f)

df_dict = {}
for row in population_json['data']:
    deso_id = row['key'][0]
    category = row['key'][1]
    if deso_id not in df_dict:
        df_dict[deso_id] = {}
    df_dict[deso_id][category] = int(row['values'][0])

population_deso = pd.DataFrame.from_dict(df_dict, orient='index')
population_deso.index.name = 'deso'

# Population covered by TIER
cov = sum(population_deso.merge(tier_deso, on='deso').totalt)
not_cov = sum(population_deso.merge(non_tier_deso, on='deso').totalt)
malmo_population = cov+not_cov
cov/malmo_population

# Plotting using basemaps
# -------------------------------------------------------
fig, ax = plt.subplots(figsize=(15, 15))
tier_deso.to_crs(epsg=3857).plot(ax=ax, alpha=0.15, facecolor='teal', edgecolor='darkslategrey')
non_tier_deso.to_crs(epsg=3857).plot(ax=ax, alpha=0.25, facecolor='maroon', edgecolor='tomato', label="test")
root_zone.to_crs(epsg=3857).plot(ax=ax, facecolor='none', edgecolor='teal', linewidth=4, label="Missing values")
cx.add_basemap(ax, zoom=12, source=cx.providers.CartoDB.Positron)
ax.set_axis_off()
ax.legend(['First line', 'Second line'])
plt.show()

# Plotting restricted zones
# -------------------------------------------------------
fig, ax = plt.subplots(figsize=(15, 15))
# alpha = 0.15
root_zone.to_crs(epsg=3857).plot(ax=ax, facecolor='none', edgecolor='teal', linewidth=2, label="Missing values")
# noParking.to_crs(epsg=3857).plot(ax=ax, alpha=alpha, facecolor='r', edgecolor='tomato', linewidth=0)
# slowZone.to_crs(epsg=3857).plot(ax=ax, alpha=alpha, facecolor='gold', edgecolor='gold', linewidth=0)
# noParkingSlow.to_crs(epsg=3857).plot(ax=ax, alpha=alpha, facecolor='gold', edgecolor='r', linewidth=0, hatch="//////")
parking_centroids.to_crs(epsg=3857).plot(ax=ax, color='dodgerblue', edgecolor='steelblue', marker='o', markersize=150)
bike_rentals.to_crs(epsg=3857).plot(ax=ax, color='orange', edgecolor='darkorange', marker='X', markersize=150)
cx.add_basemap(ax, zoom=12, source=cx.providers.CartoDB.Positron)
ax.set_axis_off()
plt.show()

# Get MalmöByBike docking stations
# -------------------------------------------------------
# overpass = Overpass()
# result = overpass.query('node["amenity"="bicycle_rental"](area::malmo); out;')
bike_rentals = gpd.read_file('./data/bike_rentals_greater_cph.geojson', crs='epsg:4326')
bike_rentals = bike_rentals[['description','name', 'network','geometry']]
bike_rentals = bike_rentals[bike_rentals.network == 'Malmö by bike']

# Parking spot analysis
# -------------------------------------------------------

parking_centroids
closed_noparking = constrained.apply(lambda x: x.geometry.convex_hull, 1)

overlapping_parking = []
for pol in closed_noparking:
    for idx, parking in parking_centroids.iterrows():
        if pol.contains(parking.geometry):
            overlapping_parking.append(parking['name'])

blocked_names = ['scooterzon Posthusplatsen', 'Malmostad Parking Zone Central Station', 'Triangeln E', 'Södra Triangeln', 'Parkering Stadion', 'Parkering Stadionområdet', 'Varnhem parking', 'E5 Värnhemstorget Resecentrum']

no_parking_parking = parking_centroids[parking_centroids['name'].isin(blocked_names)]
parking_centroids['encapsulated'] = parking_centroids['name'].isin(blocked_names)

