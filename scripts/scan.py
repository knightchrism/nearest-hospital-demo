"""Scan road intersections near the St. Johns River for cases where the straight-line-nearest
hospital differs from the drive-time-nearest one, and the straight-line pick needs a river bridge
while the drive-time pick does not. Prints candidates; picks are copied into data/candidates.json."""
import json, math, sys, random
import osmnx as ox, networkx as nx
from shapely.geometry import shape, LineString
RIVER = shape(json.load(open("data/st_johns_centerline.geojson"))["geometry"])
def crosses(coords):
    g = LineString(coords).intersection(RIVER)
    return 0 if g.is_empty else len(getattr(g, "geoms", [g]))
G = ox.graph_from_xml("/tmp/duval_drive.osm"); G = ox.add_edge_speeds(G); G = ox.add_edge_travel_times(G)
G = ox.truncate.largest_component(G, strongly=True)
def hav(a, b):
    R=3958.8; la1,lo1,la2,lo2=map(math.radians,(a[0],a[1],b[0],b[1]))
    return 2*R*math.asin(math.sqrt(math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2))
EX=("Rehabilitation","Wekiva","Ten Broeck","Nemours","MD Anderson","PAM Health","Emergency","Naval")
H={}; [H.setdefault(x["name"],x) for x in json.load(open("data/hospitals_osm_raw.json")) if not any(e in x["name"] for e in EX)]
H=list(H.values())
for x in H: x["node"]=ox.distance.nearest_nodes(G,x["lon"],x["lat"])
R=G.reverse(copy=False); dist={}
for x in H: dist[x["name"]]=nx.single_source_dijkstra_path_length(R,x["node"],weight="travel_time")
def path_xy(p): return [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in p]
random.seed(1)
nodes=[n for n,d in G.nodes(data=True) if 30.10<d["y"]<30.42 and -81.76<d["x"]<-81.55]
res=[]
DBG=0
for n in nodes:
    y,x=G.nodes[n]["y"],G.nodes[n]["x"]
    sl=min(H,key=lambda h:hav((y,x),(h["lat"],h["lon"])))
    dr=min(H,key=lambda h:dist[h["name"]].get(n,1e9))
    if sl is dr: continue
    m=(dist[sl["name"]][n]-dist[dr["name"]][n])/60
    if m<1: continue
    seg=crosses([(x,y),(sl["lon"],sl["lat"])])
    rs=crosses(path_xy(nx.shortest_path(G,n,sl["node"],weight="travel_time"))); rd=crosses(path_xy(nx.shortest_path(G,n,dr["node"],weight="travel_time")))
    if seg and rs and not rd: res.append((round(m,1),n,round(y,5),round(x,5),sl["name"],dr["name"],seg,rs))
res.sort(reverse=True)
for r in res[:60]: print(r)
print(len(res))
