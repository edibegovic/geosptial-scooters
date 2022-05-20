
# Execute all cells (lines) of 'eda.py' in an iPython environment
# Below code relies on the pre-processing state

# Read sqlite query results into a pandas DataFrame
# -------------------------------------------------------
con = sqlite3.connect("/Users/edibegovic/Dropbox/tier_data/tier_data.db")
vehicles = pd.read_sql_query("SELECT * from vehicles", con)
locations = pd.read_sql_query("SELECT * from log", con)
con.close()

# Verify that result of query is stored in the dataframe
print(vehicles)

# Explore
# -------------------------------------------------------

vehicles[vehicles.licencePlate == '210006'].iloc[0]
l = locations[locations.internal_id == 1489]

keep = []
curr_loc = (0,0)
for idx, loc in l.iterrows():
    p = (loc['lat'], loc['lng'])
    if GD(curr_loc, p).m > 30.0:
        curr_loc = p
        keep.append([loc['timestamp'][5:10], loc['lat'], loc['lng'], loc['isRentable']])


df = pd.DataFrame(keep, columns=['date', 'lat', 'lon']) 
df.to_csv('test.csv')


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


# Analysis: parking zone usage
# -------------------------------------------------------

rides_SWEREF = rides.to_crs('epsg:3006')
parking_sweref = parking_centroids.to_crs('epsg:3006')
bss_sweref = bike_rentals.to_crs('epsg:3006')

def dist_to_parking(p):
    distances = parking_sweref.apply(lambda row: p.distance(row.geometry), 1)
    return distances.min()

rides_SWEREF['nearest_parking'] = rides_SWEREF.apply(lambda x: dist_to_parking(Point(x.geometry.coords[1])), 1)
sum(rides_SWEREF.nearest_parking < 100)/len(rides_SWEREF)

def dist_to_bss(p):
    distances = bss_sweref.apply(lambda row: p.distance(row.geometry), 1)
    return distances.min()

rides_SWEREF['bss_from'] = rides_SWEREF.apply(lambda x: dist_to_bss(Point(x.geometry.coords[0])), 1)
rides_SWEREF['bss_to'] = rides_SWEREF.apply(lambda x: dist_to_bss(Point(x.geometry.coords[1])), 1)
  
def proportion(threshold):
    t = threshold/2
    share = sum(rides_SWEREF.bss_to < t)/len(rides_SWEREF)
    return share

x = [x*10 for x in range(100)]
y = [proportion(a)*100 for a in x]
plt.plot(x, y, linewidth=2)
plt.gca().xaxis.set_major_formatter(FormatStrFormatter('%d m'))
plt.xlabel('Total distance to bike-sharing docking station from destination')
plt.ylabel('Percentage of all rides')
plt.title('')
plt.show()

