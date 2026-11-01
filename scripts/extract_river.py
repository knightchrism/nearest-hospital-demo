"""Extract the St. Johns River centerline (OSM waterway=river) inside the Duval bbox from the Geofabrik extract."""
import sys, json, osmium
S, W, N, E = 30.05, -82.06, 30.60, -81.31
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.lines = []
    def way(s, w):
        if w.tags.get("waterway") == "river" and "johns" in w.tags.get("name", "").lower() and "creek" not in w.tags.get("name","").lower():
            c = [[n.lon, n.lat] for n in w.nodes if n.location.valid()]
            if any(S <= y <= N and W <= x <= E for x, y in c): s.lines.append(c)
h = H(); h.apply_file(sys.argv[1], locations=True)
json.dump({"type": "Feature", "properties": {"name": "St. Johns River (OSM centerline)"},
           "geometry": {"type": "MultiLineString", "coordinates": h.lines}}, open(sys.argv[2], "w"))
print(len(h.lines), sum(map(len, h.lines)))
