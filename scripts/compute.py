"""Compute straight-line vs drive-time nearest hospital for test points in Duval County, FL.
Data: OpenStreetMap (c) OpenStreetMap contributors, ODbL, via Overpass API (osmnx)."""
import json, math, sys
import osmnx as ox, networkx as nx
from shapely.geometry import shape, LineString
RIVER = shape(json.load(open("data/st_johns_centerline.geojson"))["geometry"])
def crossings(coords):
    g = LineString(coords).intersection(RIVER)
    return 0 if g.is_empty else len(getattr(g, "geoms", [g]))
OUT = sys.argv[1] if len(sys.argv) > 1 else "data"

def hav(a, b):
    R = 3958.8; la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

# Road network: Geofabrik Florida extract clipped to Duval bbox by scripts/clip_geofabrik.py
G = ox.graph_from_xml(sys.argv[2] if len(sys.argv) > 2 else "/tmp/duval_drive.osm", simplify=True)
G = ox.add_edge_speeds(G); G = ox.add_edge_travel_times(G)
G = ox.truncate.largest_component(G, strongly=True)
# Hospitals: OSM amenity=hospital (named), limited to general acute-care inpatient hospitals.
EXCLUDE = ("Rehabilitation", "Wekiva", "Ten Broeck", "Nemours", "MD Anderson", "PAM Health", "Emergency", "Naval")
raw = json.load(open(f"{OUT}/hospitals_osm_raw.json")) + json.load(open(f"{OUT}/hospitals_manual.json"))  # manual: OSM relations
seen = {}
for x in raw:
    if not any(e in x["name"] for e in EXCLUDE): seen.setdefault(x["name"], x)
hosp = list(seen.values())
for x in hosp: x["node"] = ox.distance.nearest_nodes(G, x["lon"], x["lat"])
json.dump([{k: v for k, v in x.items() if k != "node"} for x in hosp], open(f"{OUT}/hospitals_used.json", "w"), indent=1)

def evaluate(lat, lon):
    o = ox.distance.nearest_nodes(G, lon, lat)
    tt = nx.single_source_dijkstra_path_length(G, o, weight="travel_time")
    sl = min(hosp, key=lambda x: hav((lat, lon), (x["lat"], x["lon"])))
    dr = min((x for x in hosp if x["node"] in tt), key=lambda x: tt[x["node"]])
    return o, tt, sl, dr

def route(o, d):
    p = nx.shortest_path(G, o, d, weight="travel_time")
    coords = [[G.nodes[n]["x"], G.nodes[n]["y"]] for n in p]
    rg = ox.routing.route_to_gdf(G, p, weight="travel_time")
    return coords, rg["length"].sum()/1609.344, rg["travel_time"].sum()/60

cands = json.load(open(f"{OUT}/candidates.json"))
results = []
for c in cands:
    o, tt, sl, dr = evaluate(c["lat"], c["lon"])
    if sl["name"] == dr["name"]:
        print("same:", c["label"], sl["name"]); continue
    sc, smi, smin = route(o, sl["node"]); dc, dmi, dmin = route(o, dr["node"])
    r = {"label": c["label"], "lat": c["lat"], "lon": c["lon"],
         "straight": {"hospital": sl["name"], "lat": sl["lat"], "lon": sl["lon"],
                      "crow_mi": round(hav((c["lat"], c["lon"]), (sl["lat"], sl["lon"])), 2),
                      "drive_mi": round(smi, 2), "drive_min": round(smin, 1), "route": sc,
                      "line_crosses_river": crossings([[c["lon"], c["lat"]], [sl["lon"], sl["lat"]]]), "route_crosses_river": crossings(sc)},
         "drive": {"hospital": dr["name"], "lat": dr["lat"], "lon": dr["lon"],
                   "crow_mi": round(hav((c["lat"], c["lon"]), (dr["lat"], dr["lon"])), 2),
                   "drive_mi": round(dmi, 2), "drive_min": round(dmin, 1), "route": dc,
                   "route_crosses_river": crossings(dc)}}
    if r["straight"]["line_crosses_river"] % 2 == 0 or r["drive"]["route_crosses_river"] != 0:
        print("not a river-trap case (straight line does not end on the other bank), skipped:", c["label"]); continue
    if r["straight"]["drive_min"] - r["drive"]["drive_min"] < 1.0:
        print("margin < 1 min, skipped:", c["label"]); continue
    print(r["label"], "| SL:", sl["name"], r["straight"]["crow_mi"], "mi crow,", r["straight"]["drive_min"], "min | DR:", dr["name"], r["drive"]["drive_mi"], "mi", r["drive"]["drive_min"], "min")
    results.append(r)
fc = {"type": "FeatureCollection", "features": []}
for i, r in enumerate(results):
    P = lambda g, **p: fc["features"].append({"type": "Feature", "geometry": g, "properties": {"case": i, **p}})
    P({"type": "Point", "coordinates": [r["lon"], r["lat"]]}, kind="origin", label=r["label"])
    P({"type": "LineString", "coordinates": [[r["lon"], r["lat"]], [r["straight"]["lon"], r["straight"]["lat"]]]}, kind="straight")
    P({"type": "LineString", "coordinates": r["drive"]["route"]}, kind="drive_route")
    P({"type": "LineString", "coordinates": r["straight"]["route"]}, kind="straight_hospital_route")
for x in hosp:
    fc["features"].append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [x["lon"], x["lat"]]}, "properties": {"kind": "hospital", "name": x["name"]}})
def r6(o):  # 6 decimals (~0.1 m) keeps files small
    if isinstance(o, float): return round(o, 6)
    if isinstance(o, list): return [r6(v) for v in o]
    if isinstance(o, dict): return {k: r6(v) for k, v in o.items()}
    return o
fc = r6(fc)
json.dump(fc, open(f"{OUT}/results.geojson", "w"))
json.dump([{k: v if k not in ("straight", "drive") else {kk: vv for kk, vv in v.items() if kk != "route"} for k, v in r.items()} for r in results], open(f"{OUT}/results.json", "w"), indent=1)
# Static bundle for the page (works from file:// without a server)
with open(f"{OUT}/results.js", "w") as f:
    f.write("window.DEMO_GEOJSON=" + json.dumps(fc) + ";\nwindow.DEMO_RESULTS=" + json.dumps(json.load(open(f"{OUT}/results.json"))) +
            ";\nwindow.DEMO_RIVER=" + json.dumps(json.load(open(f"{OUT}/st_johns_centerline.geojson"))) + ";\n")
