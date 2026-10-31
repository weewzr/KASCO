"""Preliminary screening of refinery sites against public map data.

This is context for a planner. It adds no constraint to the optimiser, and OpenStreetMap
coverage in Kalimantan is uneven, so a missing feature proves nothing.

    python scripts/screen_sites.py
"""
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = json.loads((ROOT / "docs" / "data" / "official_base.json").read_text())
net = json.loads((ROOT / "docs" / "data" / "network.json").read_text())
land = json.loads((ROOT / "data" / "borneo_land.json").read_text())
AGENT = {"User-Agent": "airbustrack3ray-screening"}
SERVERS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]


def hav(a1, o1, a2, o2):
    a1, o1, a2, o2 = map(math.radians, (a1, o1, a2, o2))
    h = math.sin((a2 - a1) / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin((o2 - o1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def road(r):
    u = f"http://router.project-osrm.org/nearest/v1/driving/{r['lon']:.5f},{r['lat']:.5f}?number=1"
    try:
        return round(json.load(urllib.request.urlopen(urllib.request.Request(u, headers=AGENT), timeout=25))["waypoints"][0]["distance"])
    except Exception:
        return None


def overpass(r):
    a = f"(around:25000,{r['lat']:.4f},{r['lon']:.4f})"
    q = f'[out:json][timeout:50];(way{a}[highway~"^(trunk|primary)$"];way{a}[waterway=river][name];nwr{a}[landuse=industrial];nwr{a}[harbour];nwr{a}[man_made=pier];nwr{a}[boundary=protected_area];nwr{a}[boundary=national_park];);out tags center 500;'
    for attempt in range(6):
        url = SERVERS[attempt % len(SERVERS)]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(), headers=AGENT)
            return json.load(urllib.request.urlopen(req, timeout=75)), url
        except Exception:
            time.sleep(6)
    return None, None


rows = []
for r in base["refineries"]:
    j, src = overpass(r)
    row = {"id": r["id"], "lat": r["lat"], "lon": r["lon"], "near": r["near"], "road_m": road(r), "screened": j is not None}
    if j:
        t = [e.get("tags", {}) for e in j["elements"]]
        river = [x.get("name") for x in t if x.get("waterway") == "river" and x.get("name", "").lower().startswith("sungai") and len(x["name"]) > 7]
        row.update(
            trunk_primary=sum(x.get("highway") in ("trunk", "primary") for x in t),
            rivers=sorted(set(river))[:4],
            ports=sum("harbour" in x or x.get("man_made") == "pier" for x in t),
            industrial=sum(x.get("landuse") == "industrial" for x in t),
            protected=sorted({x.get("name", "unnamed") for x in t if x.get("boundary") in ("protected_area", "national_park")})[:3],
            source=src,
        )
    rows.append(row)
    print(row, flush=True)
    time.sleep(4)

pts = [p for ring in land for p in ring]
off = []
for s in net["sites"]:
    if not s["on_land"]:
        near = min(hav(s["lat"], s["lon"], p[1], p[0]) for p in pts if abs(p[0] - s["lon"]) < 1.0)
        off.append({"id": s["id"], "district": s["district"], "kt": s["kt"], "lat": s["lat"], "lon": s["lon"], "km_to_land": round(near, 1)})
out = {"radius_km": 25, "date": time.strftime("%Y-%m-%d"), "note": "Preliminary. OpenStreetMap coverage is uneven, so a missing feature proves nothing. No site is shown to be buildable.", "sites": rows, "offshore_points": off}
(ROOT / "docs" / "data" / "site_screen.json").write_text(json.dumps(out, indent=1))
print("screened", sum(r["screened"] for r in rows), "of", len(rows), "| offshore points", len(off))
