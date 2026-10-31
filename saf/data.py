"""Load the official datasets and the road matrix."""
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
EARTH_KM = 6371.0


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    h = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(h))


@dataclass(frozen=True)
class Network:
    sites: pd.DataFrame
    airports: pd.DataFrame
    road: pd.DataFrame

    @property
    def site_ids(self) -> list:
        return list(self.sites.location_id)

    @property
    def airport_ids(self) -> list:
        return list(self.airports.iata)

    def coord(self, node: str) -> tuple:
        if node in self.airport_ids:
            r = self.airports.set_index("iata").loc[node]
        else:
            r = self.sites.set_index("location_id").loc[node]
        return float(r.latitude), float(r.longitude)


@lru_cache(maxsize=1)
def load_network() -> Network:
    sites = pd.read_csv(DATA / "biomass_sites.csv")
    airports = pd.read_csv(DATA / "airports.csv")
    road = pd.read_csv(DATA / "road_km.csv", index_col=0)
    ids = list(sites.location_id) + list(airports.iata)
    lat = np.r_[sites.latitude.values, airports.latitude.values]
    lon = np.r_[sites.longitude.values, airports.longitude.values]
    gc = haversine(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    d = road.loc[ids, ids].values.astype(float)
    # Symmetrise the small one-way differences and close any gaps at the sampled ratio.
    d = np.where(np.isfinite(d), d, gc * 1.9)
    d = np.minimum(d, d.T)
    np.fill_diagonal(d, 0.0)
    # OSRM snaps to the nearest road, so a very short pair can read below straight line.
    d = np.maximum(d, gc)
    road = pd.DataFrame(d, index=ids, columns=ids)
    return Network(sites=sites, airports=airports, road=road)


@lru_cache(maxsize=1)
def land_rings() -> list:
    return [np.array(r) for r in json.loads((DATA / "borneo_land.json").read_text())]


def on_land(lat: float, lon: float) -> bool:
    for ring in land_rings():
        x, y = ring[:, 0], ring[:, 1]
        x2, y2 = np.roll(x, -1), np.roll(y, -1)
        cross = ((y > lat) != (y2 > lat)) & (lon < (x2 - x) * (lat - y) / (y2 - y + 1e-12) + x)
        if int(cross.sum()) % 2:
            return True
    return False


def validate_inputs(net: Network) -> dict:
    s = net.sites
    return {
        "n_sites": int(len(s)),
        "total_kt": float(round(s.production_kilotons.sum(), 2)),
        "min_kt": float(s.production_kilotons.min()),
        "max_kt": float(s.production_kilotons.max()),
        "tonnes_match": bool(math.isclose((s.production_kilotons * 1000 - s.production_tonnes).abs().max(), 0, abs_tol=1e-6)),
        "n_airports": int(len(net.airports)),
        "null_cells": int(s.isna().sum().sum()),
        "duplicate_ids": int(s.location_id.duplicated().sum()),
    }
