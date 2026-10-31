"""Tests co-located depots on the full three-tier model with HiGHS.

Refineries stay at the base-case candidate sites. Depots may go at any biomass site,
may feed several refineries and come in integer modules. A cheaper result would show
that co-location is not optimal for this fleet.

    python scripts/verify_depots.py [seconds]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

ROOT = Path(__file__).resolve().parents[1]
limit = float(sys.argv[1]) if len(sys.argv) > 1 else 240.0
sites = pd.read_csv(ROOT / "data" / "biomass_sites.csv")
air = pd.read_csv(ROOT / "data" / "airports.csv")
base = json.loads((ROOT / "docs" / "data" / "official_base.json").read_text())
refs = base["discrete_sites"]


def hav(a1, o1, a2, o2):
    a1, o1, a2, o2 = map(np.radians, (a1, o1, a2, o2))
    h = np.sin((a2 - a1) / 2) ** 2 + np.cos(a1) * np.cos(a2) * np.sin((o2 - o1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(h))


ids = list(sites.location_id)
lat, lon, B = sites.latitude.values, sites.longitude.values, sites.production_kilotons.values
d_ff = hav(lat[:, None], lon[:, None], lat[None, :], lon[None, :]) * 1.3
rid = [ids.index(r) for r in refs]
d_jr = d_ff[:, rid]
d_ra = hav(lat[rid][:, None], lon[rid][:, None], air.latitude.values[None, :], air.longitude.values[None, :]) * 1.3
nI, nR, nA = len(ids), len(refs), 4

ix = lambda i, j: i * nI + j
nx = nI * nI
iu = lambda j, k: nx + j * nR + k
nu = nI * nR
iw = lambda k, a: nx + nu + k * nA + a
nw = nR * nA
iy = lambda j, s: nx + nu + nw + j * 2 + s
ny = nI * 2
it = lambda j, s: nx + nu + nw + ny + j * 2 + s
n = nx + nu + nw + ny + nI * 2

c = np.zeros(n)
for i in range(nI):
    for j in range(nI):
        c[ix(i, j)] = 0.10 * d_ff[i, j] / 1000
for j in range(nI):
    for k in range(nR):
        c[iu(j, k)] = 0.12 * d_jr[j, k] / 1000 + 55.0 / 1000
    for s, (capex, var) in enumerate([(2.25, 5.0), (4.5, 4.0)]):
        c[iy(j, s)] = 0.10 * capex
        c[it(j, s)] = var / 1000
for k in range(nR):
    for a in range(nA):
        c[iw(k, a)] = 0.08 * d_ra[k, a] / 1000
fixed = nR * 0.10 * 765.0

R, C, V, lo, hi = [], [], [], [], []


def row(cols, vals, low, high):
    R.extend([len(lo)] * len(cols))
    C.extend(cols)
    V.extend(vals)
    lo.append(low)
    hi.append(high)


for i in range(nI):
    row([ix(i, j) for j in range(nI)], [1.0] * nI, -np.inf, B[i])
for j in range(nI):
    row([ix(i, j) for i in range(nI)] + [it(j, 0), it(j, 1)], [1.0] * nI + [-1.0, -1.0], 0, 0)
    row([iu(j, k) for k in range(nR)] + [it(j, 0), it(j, 1)], [1.0] * nR + [-1.0, -1.0], 0, 0)
    row([it(j, 0), iy(j, 0)], [1.0, -150.0], -np.inf, 0)
    row([it(j, 1), iy(j, 1)], [1.0, -300.0], -np.inf, 0)
for k in range(nR):
    row([iu(j, k) for j in range(nI)], [1.0] * nI, -np.inf, 1087.0)
    row([iw(k, a) for a in range(nA)] + [iu(j, k) for j in range(nI)], [1.0] * nA + [-0.2] * nI, 0, 0)
for a in range(nA):
    row([iw(k, a) for k in range(nR)], [1.0] * nR, 300.0, np.inf)

A = coo_matrix((V, (R, C)), shape=(len(lo), n)).tocsr()
integrality = np.zeros(n)
ub = np.full(n, np.inf)
for j in range(nI):
    for s in range(2):
        integrality[iy(j, s)] = 1
        ub[iy(j, s)] = 6
t0 = time.time()
res = milp(c, constraints=LinearConstraint(A, lo, hi), integrality=integrality, bounds=Bounds(np.zeros(n), ub), options={"time_limit": limit, "mip_rel_gap": 1e-6})
x = res.x
out = {
    "fleet": refs,
    "status": res.message,
    "free_depot_cost": res.fun + fixed,
    "free_depot_bound": res.mip_dual_bound + fixed,
    "gap_pct": 100 * res.mip_gap,
    "colocated_cost": base["discrete_objective"],
    "difference_usd_m": res.fun + fixed - base["discrete_objective"],
    "shared_depots": [ids[j] for j in range(nI) if sum(x[iu(j, k)] > 1e-6 for k in range(nR)) > 1],
    "remote_depots": [ids[j] for j in range(nI) if j not in rid and sum(x[iu(j, k)] for k in range(nR)) > 1e-6],
    "seconds": round(time.time() - t0, 1),
}
(ROOT / "docs" / "data" / "depot_check.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
