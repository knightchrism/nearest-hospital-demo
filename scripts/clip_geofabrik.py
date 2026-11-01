"""Clip the Geofabrik Florida extract to a Duval County bounding box.
Writes a small OSM XML of drivable highways (for osmnx.graph_from_xml) + named amenity=hospital points."""
import sys, json, osmium
from xml.sax.saxutils import quoteattr as q
S, W, N, E = 30.10, -82.06, 30.60, -81.31   # Duval County bbox (with small margin)
DRIVE = {"motorway","trunk","primary","secondary","tertiary","unclassified","residential","living_street",
         "motorway_link","trunk_link","primary_link","secondary_link","tertiary_link","road"}
inside = lambda lat, lon: S <= lat <= N and W <= lon <= E
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.nodes = {}; s.ways = []; s.hosp = []
    def node(s, n):
        if n.tags.get("amenity") == "hospital" and n.tags.get("name") and inside(n.location.lat, n.location.lon):
            s.hosp.append({"name": n.tags["name"], "lat": n.location.lat, "lon": n.location.lon, "osm": f"node/{n.id}"})
    def way(s, w):
        t = w.tags
        if t.get("amenity") == "hospital" and t.get("name"):
            pts = [(n.lat, n.lon) for n in w.nodes if n.location.valid()]
            if pts:
                la = sum(p[0] for p in pts)/len(pts); lo = sum(p[1] for p in pts)/len(pts)
                if inside(la, lo): s.hosp.append({"name": t["name"], "lat": la, "lon": lo, "osm": f"way/{w.id}"})
        hw = t.get("highway")
        if hw not in DRIVE or t.get("access") in ("private","no") or t.get("area") == "yes": return
        refs = [(n.ref, n.lat, n.lon) for n in w.nodes]
        if not any(inside(la, lo) for _, la, lo in refs): return
        for r, la, lo in refs: s.nodes[r] = (la, lo)
        keep = {k: t[k] for k in ("highway","name","oneway","maxspeed","ref","bridge","junction","lanes") if k in t}
        s.ways.append((w.id, [r for r, _, _ in refs], keep))
h = H(); h.apply_file(sys.argv[1], locations=True)
with open(sys.argv[2], "w") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="geoknight-clip">\n')
    for i, (la, lo) in h.nodes.items(): f.write(f'<node id="{i}" lat="{la:.7f}" lon="{lo:.7f}"/>\n')
    for i, refs, t in h.ways:
        f.write(f'<way id="{i}">' + "".join(f'<nd ref="{r}"/>' for r in refs) + "".join(f'<tag k={q(k)} v={q(v)}/>' for k, v in t.items()) + "</way>\n")
    f.write("</osm>\n")
json.dump(h.hosp, open(sys.argv[3], "w"), indent=1)
print(len(h.nodes), "nodes", len(h.ways), "ways", len(h.hosp), "hospitals")
