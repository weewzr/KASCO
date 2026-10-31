"""Build the static data files the optimiser reads.

Run once with network access. Outputs are committed so the app never needs the
network at run time.

    python scripts/build_data.py <folder holding the official Airbus files>
"""
import csv
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
CHUNK = 40

AIRPORTS = {
    "PNK": 3284,  # Supadio, Pontianak
    "PKN": 3910,  # Iskandar, Pangkalan Bun. Not 3294 Sultan Iskandar Muda (Banda Aceh)
    "BPN": 3919,  # Sultan Aji Muhammad Sulaiman Sepinggan, Balikpapan
    "TRK": 3920,  # Juwata, Tarakan
}
BRIEF_NAMES = {
    "PNK": "Supadio Intl",
    "PKN": "Iskandar Intl",
    "BPN": "Sultan Aji Muhammad Sulaiman Sepinggan Intl",
    "TRK": "Juwata Intl",
}


def extract_airports(src: Path) -> pd.DataFrame:
    cols = ["id", "name", "city", "country", "iata", "icao", "lat", "lon", "alt", "tz", "dst", "tzdb", "type", "source"]
    air = pd.read_csv(src, header=None, names=cols, na_values="\\N", encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
    rows = []
    for code, oid in AIRPORTS.items():
        r = air[air.id == oid].iloc[0]
        assert r.iata == code, (code, r.iata)
        rows.append(
            {
                "iata": code,
                "brief_name": BRIEF_NAMES[code],
                "dat_name": r["name"],
                "city": r.city,
                "openflights_id": oid,
                "latitude": float(r.lat),
                "longitude": float(r.lon),
            }
        )
    return pd.DataFrame(rows)


def osrm_block(points: list, sources: list, dests: list) -> np.ndarray:
    coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in points)
    s = ";".join(map(str, sources))
    d = ";".join(map(str, dests))
    url = f"{OSRM}{coords}?annotations=distance&sources={s}&destinations={d}"
    req = urllib.request.Request(url, headers={"User-Agent": "airbustrack3ray-hackathon"})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.load(r)
    if j.get("code") != "Ok":
        raise RuntimeError(j)
    return np.array([[np.nan if v is None else v / 1000 for v in row] for row in j["distances"]], dtype=float)


def road_matrix(points: list) -> np.ndarray:
    n = len(points)
    D = np.full((n, n), np.nan)
    if n <= 100:
        idx = list(range(n))
        return osrm_block(points, idx, idx)
    for a in range(0, n, CHUNK):
        ia = list(range(a, min(a + CHUNK, n)))
        for b in range(0, n, CHUNK):
            ib = list(range(b, min(b + CHUNK, n)))
            pts = [points[i] for i in ia] + [points[i] for i in ib]
            D[np.ix_(ia, ib)] = osrm_block(pts, list(range(len(ia))), list(range(len(ia), len(pts))))
    return D


def main(official: Path) -> None:
    DATA.mkdir(exist_ok=True)
    shutil.copy(official / "kalimantan_80_locations_6800kt_full_range.csv", DATA / "biomass_sites.csv")
    air = extract_airports(official / "airports.dat")
    air.to_csv(DATA / "airports.csv", index=False)
    sites = pd.read_csv(DATA / "biomass_sites.csv")
    ids = list(sites.location_id) + list(air.iata)
    pts = list(zip(sites.latitude, sites.longitude)) + list(zip(air.latitude, air.longitude))
    D = road_matrix(pts)
    pd.DataFrame(np.round(D, 2), index=ids, columns=ids).to_csv(DATA / "road_km.csv")
    print("nodes", len(ids), "missing", int(np.isnan(D).sum()))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
