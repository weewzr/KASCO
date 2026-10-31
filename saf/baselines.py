"""Reference networks a planner could draw without an optimiser.

Both use the same demand, conversion, distances and cost basis as the MILP, so the
saving reported is a like-for-like figure.
"""
import math

import numpy as np

from .config import Params
from .data import Network, load_network
from .model import Solution, airport_demand, required_biomass_kt, summarise


def _fleet(need: float, p: Params) -> list:
    """Cheapest refinery size list covering `need`."""
    best = None
    top = int(need // p.refinery_cap["small"]) + 2
    for nl in range(top + 1):
        for ns in range(top + 1):
            if nl * p.refinery_cap["large"] + ns * p.refinery_cap["small"] >= need - 1e-6:
                c = nl * p.refinery_capex["large"] + ns * p.refinery_capex["small"]
                if best is None or c < best[0]:
                    best = (c, nl, ns)
    return ["large"] * best[1] + ["small"] * best[2]


def _depot_clusters(p: Params, net: Network, need_raw: float, seed_order: list) -> tuple:
    """Open a depot on the next unserved site and pull in its nearest sites."""
    d = net.road
    left = dict(zip(net.sites.location_id, net.sites.production_kilotons * p.biomass_multiplier))
    open_d, flows, gathered = {}, [], 0.0
    for seed in seed_order:
        if gathered >= need_raw - 1e-9:
            break
        if left[seed] <= 1e-9:
            continue
        room = min(p.depot_cap["large"], need_raw - gathered)
        size = "small" if room <= p.depot_cap["small"] else "large"
        got = 0.0
        for i in d.loc[seed, list(left)].sort_values().index:
            if left[i] <= 1e-9 or got >= room - 1e-9:
                continue
            q = min(left[i], room - got)
            flows.append((i, seed, q))
            left[i] -= q
            got += q
        open_d[seed] = size
        gathered += got
    return open_d, flows


def _serve(p, net, open_d, flows, refinery_sites, name, t0=0.0) -> Solution:
    """Send each depot to its nearest refinery with room, then fill airports nearest first."""
    d = net.road
    dep_out = {}
    for _, j, q in flows:
        dep_out[j] = dep_out.get(j, 0) + q * p.retention
    room = {k: p.refinery_cap[s] for k, s in refinery_sites.items()}
    fr = []
    for j in sorted(dep_out, key=lambda x: -dep_out[x]):
        q = dep_out[j]
        for k in d.loc[j, list(room)].sort_values().index:
            if q <= 1e-9:
                break
            take = min(q, room[k])
            if take > 1e-9:
                fr.append((j, k, take))
                room[k] -= take
                q -= take
        if q > 1e-6:
            raise ValueError("refinery capacity exhausted")
    made = {}
    for _, k, q in fr:
        made[k] = made.get(k, 0) + q * p.yield_saf
    D = dict(airport_demand(p, net))
    fa = []
    pairs = sorted(((d.at[k, a], k, a) for k in made for a in D))
    for _, k, a in pairs:
        q = min(made[k], D[a])
        if q > 1e-9:
            fa.append((k, a, q))
            made[k] -= q
            D[a] -= q
    size = dict(n_vars=0, n_binaries=0, n_cons=0, arcs={})
    sol = summarise(p, net, open_d, refinery_sites, flows, fr, fa, "heuristic", name, 0.0, None, None, 0.0, size)
    sol.objective = sol.costs["total_annual"]
    return sol


def greedy_baseline(p: Params, net: Network | None = None) -> Solution:
    """Depots on the richest sites, refineries spread farthest-first across them."""
    net = net or load_network()
    need_raw = required_biomass_kt(p, net)
    order = list(net.sites.sort_values("production_kilotons", ascending=False).location_id)
    open_d, flows = _depot_clusters(p, net, need_raw, order)
    fleet = _fleet(need_raw * p.retention, p)
    gate = {}
    for _, j, q in flows:
        gate[j] = gate.get(j, 0) + q
    cand = sorted(gate, key=lambda x: -gate[x])
    chosen = [cand[0]]
    while len(chosen) < len(fleet) and len(chosen) < len(cand):
        chosen.append(max((c for c in cand if c not in chosen), key=lambda c: min(net.road.at[c, r] for r in chosen)))
    return _serve(p, net, open_d, flows, dict(zip(chosen, fleet)), "Greedy heuristic: richest depots, farthest-first refineries")


def airport_baseline(p: Params, net: Network | None = None) -> Solution:
    """Refineries at the busiest airports first, as a fuel planner might default to."""
    net = net or load_network()
    need_raw = required_biomass_kt(p, net)
    fleet = _fleet(need_raw * p.retention, p)
    up = sorted(net.airport_ids, key=lambda a: -p.uplift_kt[a])
    order = list(net.sites.sort_values("production_kilotons", ascending=False).location_id)
    chosen = up[: len(fleet)]
    # When the fleet outnumbers the airports the rest go to the richest sites.
    chosen += [s for s in order if s not in chosen][: max(0, len(fleet) - len(chosen))]
    d = net.road
    seeds = sorted(net.site_ids, key=lambda s: min(d.at[s, k] for k in chosen))
    open_d, flows = _depot_clusters(p, net, need_raw, seeds)
    return _serve(p, net, open_d, flows, dict(zip(chosen, fleet)), "Airport-first: refineries at the busiest airports")


def trip_counts(sol: dict) -> dict:
    """Truck loads per year. Size cannot change cost, so it only changes traffic."""
    from .config import TRUCK_T

    out = {}
    for key, flows in (("farm_depot", sol["flows_fd"]), ("depot_refinery", sol["flows_dr"]), ("refinery_airport", sol["flows_ra"])):
        t = sum(f["kt"] for f in flows) * 1000
        small, large = TRUCK_T[key]
        out[key] = dict(tonnes=t, small_truck_t=small, large_truck_t=large, trips_small=math.ceil(t / small), trips_large=math.ceil(t / large))
    return out
