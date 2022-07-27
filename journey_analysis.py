
# Execute all cells (lines) of 'eda.py' in an iPython environment
# Below code relies on the pre-processing state

# Read sqlite query results into a pandas DataFrame
# -------------------------------------------------------
con = sqlite3.connect("/Users/edibegovic/Dropbox/tier_data/tier_data.db")
vehicles = pd.read_sql_query("SELECT * from vehicles", con)
locations = pd.read_sql_query("SELECT * from log", con)
con.close()

# Verify that result of query is stored in the dataframe :)
print(vehicles)

# Explore / Playground
# -------------------------------------------------------
# vehicles[vehicles.licencePlate == '210006'].iloc[0]
# l = locations[locations.internal_id == 1489]

# keep = []
# curr_loc = (0,0)
# for idx, loc in l.iterrows():
#     p = (loc['lat'], loc['lng'])
#     if GD(curr_loc, p).m > 30.0:
#         curr_loc = p
#         keep.append([loc['timestamp'][5:10], loc['lat'], loc['lng'], loc['isRentable']])


# df = pd.DataFrame(keep, columns=['date', 'lat', 'lon']) 
# df.to_csv('test.csv')


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


# Preprocess: extract journeys
# -------------------------------------------------------

records = gpd.GeoDataFrame(locations, geometry=gpd.points_from_xy(locations.lng, locations.lat), crs='epsg:4326')
ids = list(set(records.internal_id))

def extrapolate_rides(recs):
    recs = recs.sort_values(by="timestamp")
    recs = recs.to_crs('epsg:3006')
    test_shifted = recs.shift() #We shift the dataframe by 1 to align pnt1 with pnt2
    recs['dist'] = recs.distance(test_shifted)
    if recs['dist'].sum() < 170:
        return [None]
    recs = recs.to_crs('EPSG:4326')
    recs = recs[(recs.dist > 100) | (recs.dist.isna())]
    recs['from'] = recs.geometry
    recs['to'] = recs.geometry.shift(-1)
    recs = recs[:-1]
    recs['geometry'] = recs.apply(lambda x: LineString([x['from'], x['to']]), 1)
    features = ['internal_id', 'timestamp', 'batteryLevel', 'geometry', 'from', 'to']
    return recs[features]

rides = pd.DataFrame()
for i in ids:
    print(i)
    rides_segment = records[records.internal_id == i]
    rides_segment = extrapolate_rides(rides_segment)
    if len(rides_segment) < 3:
        continue
    rides = pd.concat([rides, rides_segment])

rides



# Applying Swedish reference system
# -------------------------------------------------------
rides_SWEREF = rides.to_crs('epsg:3006')
parking_sweref = parking_centroids.to_crs('epsg:3006')
bss_sweref = bike_rentals.to_crs('epsg:3006')
bss_sweref = bike_rentals.to_crs('epsg:3006')
pbuffer_sweref = parking_buffer.to_crs('epsg:3006')
transit_sweref = transit_hubs.to_crs('epsg:3006')

# Analysis: parking zone usage
# -------------------------------------------------------
def dist_to_parking(p):
    distances = parking_sweref.apply(lambda row: p.distance(row.geometry), 1)
    return distances.min()

rides_within_buffer = rides_SWEREF[rides_SWEREF.apply(lambda x: pbuffer_sweref.contains(x.geometry), 1).iloc[:, 0]]

rides_within_buffer['nearest_parking'] = rides_within_buffer.apply(lambda x: dist_to_parking(Point(x.geometry.coords[1])), 1)
sum(rides_within_buffer.nearest_parking < 300)/len(rides_within_buffer)


#  Density of parking zones
# -----------------------------------------------------
parking_buffer['geometry'].to_crs({'init': 'epsg:3857'})\
               .map(lambda p: p.area / 10**6)

len(parking_centroids)/13

# BSS docking station proximity
# -----------------------------------------------------

def dist_to_bss(p):
    distances = bss_sweref.apply(lambda row: p.distance(row.geometry), 1)
    return distances.min()

rides_SWEREF['bss_from'] = rides_SWEREF.apply(lambda x: dist_to_bss(Point(x.geometry.coords[0])), 1)
rides_SWEREF['bss_to'] = rides_SWEREF.apply(lambda x: dist_to_bss(Point(x.geometry.coords[1])), 1)
  
def proportion(threshold):
    t = threshold/2
    share = sum((rides_SWEREF.bss_to < t) & (rides_SWEREF.bss_from < t))/len(rides_SWEREF)
    return share

# Plot
x = [x*10 for x in range(100)]
y = [proportion(a)*100 for a in x]
x_l = [x*200+200 for x in range(5)]
y_l = [proportion(a)*100 for a in x_l]
plt.plot(x, y, linewidth=2, zorder=2)
plt.vlines(x_l, 0, y_l, linestyle="dashed", alpha=0.5)
plt.hlines(y_l, 0, x_l, linestyle="dashed", alpha=0.5)
plt.gca().xaxis.set_major_formatter(FormatStrFormatter('%d m'))
plt.gca().yaxis.set_major_formatter(FormatStrFormatter('%.1f%%'))
plt.xlim(0,None)
plt.ylim(0, 100)
plt.xlabel('Total distance to nearest bike-share docking station')
plt.ylabel('Percentage of all e-scooter rides')
plt.title('')
plt.show()

# Public transit
# -----------------------------------------------------

def dist_to_transit(p):
    distances = transit_sweref.apply(lambda row: p.distance(row.geometry), 1)
    return distances.min()

rides_SWEREF['nearest_transit'] = rides_SWEREF.apply(lambda x: dist_to_transit(Point(x.geometry.coords[1])), 1)
sum(rides_SWEREF.nearest_transit < 150)/len(rides_SWEREF)

# Add timestamt and interval
rides_SWEREF['timestamp'] = pd.to_datetime(rides_SWEREF.timestamp)
rides_SWEREF['20m'] = rides_SWEREF.apply(lambda x: x.timestamp.hour*60 + x.timestamp.minute, 1)

# Plot
rides_SWEREF = rides_SWEREF[rides_SWEREF['20m'] != 1218] # discard - error for timestamp
rides_SWEREF[rides_SWEREF.nearest_transit < 50]['20m'].hist(bins=72)
plt.show()

# Share of rides within peak hours
tt = rides_SWEREF[rides_SWEREF.nearest_transit < 150].groupby('20m').count()
t1 = tt[(tt.index >= 300) & ((tt.index) <= 500)].sum()
t2 = tt[(tt.index >= 830) & ((tt.index) <= 1021)].sum()
(t1+t2).iloc[0]/tt.sum().iloc[0]*100

# Mean ride length T.O.D
# -----------------------------------------------------

def dist_to_transit(p):
    distances = transit_sweref.apply(lambda row: p.distance(row.geometry), 1)
    return distances.min()

rides_SWEREF['distance'] = rides_SWEREF.apply(lambda x: x.geometry.length, 1)

mean_dist = rides_SWEREF[~rides_SWEREF['20m'].between(1217, 1235)].groupby('20m').mean()['distance']
plt.bar(list(mean_dist.index), list(mean_dist), width=8.4)
plt.show()

mean_dist.mean()
mean_dist.std()

# Rides ending at zone boundary
# -----------------------------------------------------
root_edge_pol = root_edge.iloc[0].geometry

for _, scooter in rides.iterrows():
    if root_edge_pol.contains(scooter.to):
        print("yay")

rides['boundary'] = rides.apply(lambda x: root_edge_pol.contains(x.to), 1)
sum(rides['boundary'])/len(rides)

rides_SWEREF[rides['boundary']].mean()

