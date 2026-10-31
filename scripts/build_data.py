"""Fetch and prepare the data files the engine compiles in. Run once with network access.

    python scripts/build_data.py <folder holding the official Airbus files>

Outputs are committed, so neither the app nor the engine needs the network.
"""
import json
import shutil
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OSRM = "http://router.project-osrm.org/table/v1/driving/"
LAND = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson"


def road_matrix(points: list) -> np.ndarray:
    """All-pairs road km from OSRM on OpenStreetMap. The demo server takes 100 points."""
    coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in points)
    req = urllib.request.Request(f"{OSRM}{coords}?annotations=distance", headers={"User-Agent": "airbustrack3ray-hackathon"})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.load(r)
    if j.get("code") != "Ok":
        raise RuntimeError(j)
    return np.array([[np.nan if v is None else v / 1000 for v in row] for row in j["distances"]], dtype=float)


def land_mask() -> list:
    """Natural Earth 10 m land rings around Borneo, lightly thinned."""
    with urllib.request.urlopen(LAND, timeout=150) as r:
        gj = json.load(r)
    out = []
    for feat in gj["features"]:
        g = feat["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ring = np.array(poly[0])[:, :2]
            if ring[:, 0].max() < 108 or ring[:, 0].min() > 120 or ring[:, 1].max() < -5 or ring[:, 1].min() > 8:
                continue
            step = 2 if len(ring) > 3000 else 1
            out.append(np.round(ring[::step], 3).tolist())
    return out


def main(official: Path) -> None:
    DATA.mkdir(exist_ok=True)
    shutil.copy(official / "kalimantan_80_locations_6800kt_full_range.csv", DATA / "biomass_sites.csv")
    shutil.copy(official / "challenge3_airports_4.csv", DATA / "airports.csv")
    shutil.copy(official / "challenge3_parameters.xlsx", DATA / "challenge3_parameters.xlsx")
    sites = pd.read_csv(DATA / "biomass_sites.csv")
    air = pd.read_csv(DATA / "airports.csv")
    ids = list(sites.location_id) + list(air.iata)
    pts = list(zip(sites.latitude, sites.longitude)) + list(zip(air.latitude, air.longitude))
    pd.DataFrame(np.round(road_matrix(pts), 2), index=ids, columns=ids).to_csv(DATA / "road_km.csv")
    (DATA / "borneo_land.json").write_text(json.dumps(land_mask(), separators=(",", ":")))
    print("done:", len(ids), "nodes")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
