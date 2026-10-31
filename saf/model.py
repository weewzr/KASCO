"""Multi-echelon capacitated facility location MILP.

Biomass site -> depot -> refinery -> airport. All masses are kt/yr and all costs
are USD M/yr, so one kt moved one km at 1 USD/t/km costs 0.001 USD M.

Solved with HiGHS through scipy.optimize.milp, which keeps the same code path on a
laptop and inside the browser build.
"""
import time
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .config import SIZES, Params
from .data import Network, load_network

TOL = 1e-6


def airport_demand(p: Params, net: Network) -> dict:
    """SAF demand in kt/yr per airport for this scenario."""
    if p.demand_mode == "absolute":
        base = dict(p.airport_kt)
    elif p.demand_mode == "blend":
        base = {a: p.blend * p.uplift_kt[a] for a in net.airport_ids}
    elif p.demand_mode == "hub":
        total = max_saf_kt(p, net)
        up = sum(p.uplift_kt[a] for a in net.airport_ids)
        base = {a: total * p.uplift_kt[a] / up for a in net.airport_ids}
    else:
        raise ValueError(p.demand_mode)
    return {a: v * p.demand_multiplier for a, v in base.items()}


def max_saf_kt(p: Params, net: Network) -> float:
    return float(net.sites.production_kilotons.sum() * p.biomass_multiplier * p.retention * p.yield_saf)


def required_biomass_kt(p: Params, net: Network) -> float:
    return sum(airport_demand(p, net).values()) / (p.retention * p.yield_saf)


@dataclass
class Solution:
    params: dict
    status: str  # optimal, feasible_gap, infeasible, time_limit_no_solution, error
    message: str
    objective: float | None
    bound: float | None
    gap: float | None
    runtime_s: float
    n_vars: int
    n_binaries: int
    n_cons: int
    arcs: dict
    depots: list
    refineries: list
    flows_fd: list
    flows_dr: list
    flows_ra: list
    costs: dict
    kpis: dict

    @property
    def has_network(self) -> bool:
        return self.status in ("optimal", "feasible_gap")

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def candidate_arcs(p: Params, net: Network, k_fd: int | None, k_dr: int | None):
    """Arc lists. Pruning keeps each site's k nearest depots, as in Ng et al. 2018."""
    sites = net.site_ids
    depots = [s for s in sites if s not in set(p.forbid_depots)]
    if p.allow_depot_sites:
        depots = [s for s in depots if s in set(p.allow_depot_sites)]
    refs = [s for s in sites + net.airport_ids if s not in set(p.forbid_refineries)]
    if p.allow_refinery_sites:
        refs = [s for s in refs if s in set(p.allow_refinery_sites)]
    d = net.road
    arcs_fd = []
    for i in sites:
        row = d.loc[i, depots].sort_values()
        keep = row.index if k_fd is None else row.index[: k_fd]
        arcs_fd += [(i, j) for j in keep]
    arcs_dr = []
    for j in depots:
        row = d.loc[j, refs].sort_values()
        keep = row.index if k_dr is None else row.index[: k_dr]
        arcs_dr += [(j, k) for k in keep]
    arcs_ra = [(k, a) for k in refs for a in net.airport_ids]
    return depots, refs, arcs_fd, arcs_dr, arcs_ra


class Builder:
    """Collects sparse rows, so the constraint list reads like the formulation."""

    def __init__(self, n):
        self.n = n
        self.r, self.c, self.v, self.lo, self.hi = [], [], [], [], []
        self.m = 0

    def add(self, cols, vals, lo, hi):
        self.r += [self.m] * len(cols)
        self.c += list(cols)
        self.v += list(vals)
        self.lo.append(lo)
        self.hi.append(hi)
        self.m += 1

    def constraint(self):
        A = coo_matrix((self.v, (self.r, self.c)), shape=(self.m, self.n)).tocsr()
        return LinearConstraint(A, np.array(self.lo), np.array(self.hi))


def min_refinery_fleet(need: float, caps: dict, costs: dict) -> tuple:
    """Cheapest integer mix of sizes covering `need`. Gives a valid CapEx lower bound."""
    n_max = int(need // min(caps.values())) + 2
    best = (np.inf, 0)
    for nl in range(n_max + 1):
        for ns in range(n_max + 1):
            if nl * caps["large"] + ns * caps["small"] >= need - TOL:
                best = min(best, (nl * costs["large"] + ns * costs["small"], nl + ns))
    return best


def solve(p: Params, net: Network | None = None, k_fd: int | None = 18, k_dr: int | None = 24) -> Solution:
    """Solve one scenario and return the best network with a proven lower bound.

    Stage 1 keeps refinery binaries and relaxes depot binaries. Depot cost is linear
    in capacity, so this loses little, and its dual bound is valid for the full model.
    Stage 2 fixes the chosen refineries and restores depot binaries, which gives a
    true feasible network. The gap reported compares stage 2 cost with stage 1 bound.
    """
    net = net or load_network()
    t0 = time.perf_counter()
    if required_biomass_kt(p, net) < 1000:
        sol = _solve_once(p, net, k_fd, k_dr, relax_depots=False)
        if sol.status == "infeasible":
            sol = _solve_once(p, net, None, None, relax_depots=False)
            sol.message += " Confirmed on the unpruned arc set."
        return sol

    budget = p.time_limit_s
    s1 = _solve_once(p.with_(time_limit_s=budget * 0.7), net, k_fd, k_dr, relax_depots=True)
    if s1.status == "infeasible":
        s1 = _solve_once(p.with_(time_limit_s=budget), net, None, None, relax_depots=True)
        s1.message += " Confirmed on the unpruned arc set."
    if s1.status not in ("optimal", "feasible_gap"):
        s1.runtime_s = time.perf_counter() - t0
        return s1
    keep = tuple(r["id"] for r in s1.refineries)
    sizes = {r["id"]: r["size"] for r in s1.refineries}
    s2 = _solve_once(
        p.with_(allow_refinery_sites=keep, time_limit_s=max(10.0, budget * 0.3), mip_gap=min(p.mip_gap, 0.002)),
        net, k_fd, None, relax_depots=False, fix_sizes=sizes,
    )
    s2.runtime_s = time.perf_counter() - t0
    if not s2.has_network:
        return s2
    lb = s1.bound if s1.bound is not None else s1.objective
    s2.bound = lb
    s2.gap = max(0.0, (s2.objective - lb) / s2.objective)
    s2.status = "optimal" if s2.gap <= p.mip_gap + 1e-9 else "feasible_gap"
    s2.message = f"Two-stage solve. Stage 1 bound {lb:.2f}, stage 2 cost {s2.objective:.2f} USD M/yr."
    s2.params["allow_refinery_sites"] = p.allow_refinery_sites
    s2.params["time_limit_s"] = p.time_limit_s
    s2.params["mip_gap"] = p.mip_gap
    return s2


def _solve_once(p: Params, net: Network, k_fd, k_dr, relax_depots: bool = False, fix_sizes: dict | None = None) -> Solution:
    t0 = time.perf_counter()
    d = net.road
    B = dict(zip(net.sites.location_id, net.sites.production_kilotons * p.biomass_multiplier))
    D = airport_demand(p, net)
    depots, refs, arcs_fd, arcs_dr, arcs_ra = candidate_arcs(p, net, k_fd, k_dr)
    dist = p.distance_multiplier

    # Variable layout: y[j,s], z[k,s], x[i,j], u[j,k], v[k,a]
    iy = {(j, s): n for n, (j, s) in enumerate((j, s) for j in depots for s in SIZES)}
    off = len(iy)
    iz = {(k, s): off + n for n, (k, s) in enumerate((k, s) for k in refs for s in SIZES)}
    off += len(iz)
    ix = {a: off + n for n, a in enumerate(arcs_fd)}
    off += len(ix)
    iu = {a: off + n for n, a in enumerate(arcs_dr)}
    off += len(iu)
    iv = {a: off + n for n, a in enumerate(arcs_ra)}
    nv = off + len(iv)

    ann = p.annuity + p.fixed_opex_frac
    c = np.zeros(nv)
    for (j, s), n in iy.items():
        c[n] = ann * p.depot_capex[s]
    for (k, s), n in iz.items():
        c[n] = ann * p.refinery_capex[s]
    for (i, j), n in ix.items():
        c[n] = (p.tariff_fd * d.at[i, j] * dist + p.depot_opex_var + p.biomass_price) / 1000
    for (j, k), n in iu.items():
        c[n] = (p.tariff_dr * d.at[j, k] * dist + p.refinery_opex_var) / 1000
    for (k, a), n in iv.items():
        c[n] = p.tariff_ra * d.at[k, a] * dist / 1000

    b = Builder(nv)
    out_of_site = {i: [] for i in B}
    into_depot = {j: [] for j in depots}
    out_of_depot = {j: [] for j in depots}
    into_ref = {k: [] for k in refs}
    out_of_ref = {k: [] for k in refs}
    into_air = {a: [] for a in net.airport_ids}
    for (i, j), n in ix.items():
        out_of_site[i].append(n)
        into_depot[j].append(n)
    for (j, k), n in iu.items():
        out_of_depot[j].append(n)
        into_ref[k].append(n)
    for (k, a), n in iv.items():
        out_of_ref[k].append(n)
        into_air[a].append(n)

    for i, cols in out_of_site.items():  # biomass availability
        b.add(cols, [1.0] * len(cols), -np.inf, B[i])
    for j in depots:
        cols_in, cols_out = into_depot[j], out_of_depot[j]
        # mass balance across the depot
        b.add(cols_out + cols_in, [1.0] * len(cols_out) + [-p.retention] * len(cols_in), 0.0, 0.0)
        # depot capacity on inbound biomass, only if opened
        ys = [iy[(j, s)] for s in SIZES]
        b.add(cols_in + ys, [1.0] * len(cols_in) + [-p.depot_cap[s] for s in SIZES], -np.inf, 0.0)
        b.add(ys, [1.0, 1.0], -np.inf, 1.0)  # at most one size per site
    for k in refs:
        cols_in, cols_out = into_ref[k], out_of_ref[k]
        # conversion across the refinery
        b.add(cols_out + cols_in, [1.0] * len(cols_out) + [-p.yield_saf] * len(cols_in), 0.0, 0.0)
        zs = [iz[(k, s)] for s in SIZES]
        throughput = cols_in if p.refinery_basis == "input" else cols_out
        b.add(throughput + zs, [1.0] * len(throughput) + [-p.refinery_cap[s] for s in SIZES], -np.inf, 0.0)
        b.add(zs, [1.0, 1.0], -np.inf, 1.0)
    for a, cols in into_air.items():  # airport demand
        b.add(cols, [1.0] * len(cols), D[a], np.inf)

    # Tightening rows. They cut no integer solution and lift the LP bound.
    for (i, j), n in ix.items():
        cap = min(B[i], max(p.depot_cap.values()))
        ys = [iy[(j, s)] for s in SIZES]
        b.add([n] + ys, [1.0, -cap, -cap], -np.inf, 0.0)
    for (j, k), n in iu.items():
        zs = [iz[(k, s)] for s in SIZES]
        cap = p.retention * max(p.depot_cap.values())
        if p.refinery_basis == "input":
            b.add([n] + zs, [1.0, -min(cap, p.refinery_cap["small"]), -min(cap, p.refinery_cap["large"])], -np.inf, 0.0)
        else:
            b.add([n] + zs, [1.0, -cap, -cap], -np.inf, 0.0)
    for (k, a), n in iv.items():
        zs = [iz[(k, s)] for s in SIZES]
        b.add([n] + zs, [1.0, -D[a], -D[a]], -np.inf, 0.0)
    need_b = sum(D.values()) / p.yield_saf
    need_cap = need_b if p.refinery_basis == "input" else sum(D.values())
    cols = list(iz.values())
    b.add(cols, [p.refinery_cap[s] for (_, s) in iz], need_cap, np.inf)
    fleet_cost, fleet_n = min_refinery_fleet(need_cap, p.refinery_cap, p.refinery_capex)
    if np.isfinite(fleet_cost):
        b.add(cols, [p.refinery_capex[s] for (_, s) in iz], fleet_cost, np.inf)
        b.add(cols, [1.0] * len(cols), np.ceil(need_cap / max(p.refinery_cap.values()) - 1e-9), np.inf)
    cols = list(iy.values())
    b.add(cols, [p.depot_cap[s] for (_, s) in iy], need_b / p.retention, np.inf)

    if p.max_refineries:
        cols = list(iz.values())
        b.add(cols, [1.0] * len(cols), -np.inf, p.max_refineries)
    if p.max_depots:
        cols = list(iy.values())
        b.add(cols, [1.0] * len(cols), -np.inf, p.max_depots)

    integrality = np.zeros(nv)
    integrality[len(iy) if relax_depots else 0: len(iy) + len(iz)] = 1
    lb = np.zeros(nv)
    ub = np.full(nv, np.inf)
    ub[: len(iy) + len(iz)] = 1.0
    if fix_sizes:
        for (k, s), n in iz.items():
            lb[n] = ub[n] = 1.0 if fix_sizes.get(k) == s else 0.0

    res = milp(
        c,
        constraints=b.constraint(),
        integrality=integrality,
        bounds=Bounds(lb, ub),
        options={"time_limit": p.time_limit_s, "mip_rel_gap": p.mip_gap, "presolve": True},
    )
    runtime = time.perf_counter() - t0
    size = dict(n_vars=nv, n_binaries=len(iy) + len(iz), n_cons=b.m, arcs={"farm_depot": len(ix), "depot_refinery": len(iu), "refinery_airport": len(iv)})
    pd_ = p.to_dict()
    if res.x is None:
        status = "infeasible" if res.status == 2 else "time_limit_no_solution" if res.status == 1 else "error"
        return Solution(pd_, status, str(res.message), None, None, None, runtime, depots=[], refineries=[], flows_fd=[], flows_dr=[], flows_ra=[], costs={}, kpis={}, **size)

    x = res.x
    gap = float(res.mip_gap) if res.mip_gap is not None else 0.0
    bound = float(res.mip_dual_bound) if res.mip_dual_bound is not None else None
    status = "optimal" if res.status == 0 else "feasible_gap"
    open_d = {j: s for (j, s), n in iy.items() if x[n] > (1e-6 if relax_depots else 0.5)}
    open_r = {k: s for (k, s), n in iz.items() if x[n] > 0.5}
    ff = [(i, j, x[n]) for (i, j), n in ix.items() if x[n] > TOL]
    fr = [(j, k, x[n]) for (j, k), n in iu.items() if x[n] > TOL]
    fa = [(k, a, x[n]) for (k, a), n in iv.items() if x[n] > TOL]
    return summarise(p, net, open_d, open_r, ff, fr, fa, status, str(res.message), float(res.fun), bound, gap, runtime, size)


def summarise(p, net, open_d, open_r, ff, fr, fa, status, message, objective, bound, gap, runtime, size) -> Solution:
    """Turn raw decisions into the records every other module reads."""
    d = net.road
    dist = p.distance_multiplier
    flows_fd = [dict(src=i, dst=j, kt=round(q, 4), km=round(d.at[i, j] * dist, 1), usd_m=q * p.tariff_fd * d.at[i, j] * dist / 1000) for i, j, q in ff]
    flows_dr = [dict(src=j, dst=k, kt=round(q, 4), km=round(d.at[j, k] * dist, 1), usd_m=q * p.tariff_dr * d.at[j, k] * dist / 1000) for j, k, q in fr]
    flows_ra = [dict(src=k, dst=a, kt=round(q, 4), km=round(d.at[k, a] * dist, 1), usd_m=q * p.tariff_ra * d.at[k, a] * dist / 1000) for k, a, q in fa]
    in_d = {j: 0.0 for j in open_d}
    for f in flows_fd:
        in_d[f["dst"]] = in_d.get(f["dst"], 0) + f["kt"]
    in_r = {k: 0.0 for k in open_r}
    for f in flows_dr:
        in_r[f["dst"]] = in_r.get(f["dst"], 0) + f["kt"]
    out_r = {k: 0.0 for k in open_r}
    for f in flows_ra:
        out_r[f["src"]] = out_r.get(f["src"], 0) + f["kt"]
    depots = []
    for j, s in sorted(open_d.items()):
        lat, lon = net.coord(j)
        depots.append(dict(id=j, size=s, lat=lat, lon=lon, capacity=p.depot_cap[s], throughput=round(in_d.get(j, 0), 4), utilisation=in_d.get(j, 0) / p.depot_cap[s]))
    refineries = []
    for k, s in sorted(open_r.items()):
        lat, lon = net.coord(k)
        used = in_r.get(k, 0) if p.refinery_basis == "input" else out_r.get(k, 0)
        refineries.append(dict(id=k, size=s, lat=lat, lon=lon, capacity=p.refinery_cap[s], throughput=round(used, 4), saf_kt=round(out_r.get(k, 0), 4), biomass_in=round(in_r.get(k, 0), 4), utilisation=used / p.refinery_cap[s]))

    capex_d = sum(p.depot_capex[s] for s in open_d.values())
    capex_r = sum(p.refinery_capex[s] for s in open_r.values())
    capex = capex_d + capex_r
    biomass = sum(f["kt"] for f in flows_fd)
    gate = sum(f["kt"] for f in flows_dr)
    saf = sum(f["kt"] for f in flows_ra)
    log_fd = sum(f["usd_m"] for f in flows_fd)
    log_dr = sum(f["usd_m"] for f in flows_dr)
    log_ra = sum(f["usd_m"] for f in flows_ra)
    capital = capex * p.annuity
    fixed = capex * p.fixed_opex_frac
    var = (gate * p.refinery_opex_var + biomass * (p.depot_opex_var + p.biomass_price)) / 1000
    total = capital + fixed + var + log_fd + log_dr + log_ra
    costs = dict(
        capex_depots=capex_d, capex_refineries=capex_r, capex_total=capex, annual_capital=capital,
        opex_fixed=fixed, opex_variable=var, logistics_farm_depot=log_fd, logistics_depot_refinery=log_dr,
        logistics_refinery_airport=log_ra, logistics_total=log_fd + log_dr + log_ra, total_annual=total,
    )
    demand = airport_demand(p, net)
    deliv = {a: sum(f["kt"] for f in flows_ra if f["dst"] == a) for a in net.airport_ids}
    tkm = {
        "farm_depot": sum(f["kt"] * f["km"] for f in flows_fd),
        "depot_refinery": sum(f["kt"] * f["km"] for f in flows_dr),
        "refinery_airport": sum(f["kt"] * f["km"] for f in flows_ra),
    }
    kpis = dict(
        biomass_used_kt=biomass, biomass_available_kt=float(net.sites.production_kilotons.sum() * p.biomass_multiplier),
        biomass_used_share=biomass / float(net.sites.production_kilotons.sum() * p.biomass_multiplier),
        gate_biomass_kt=gate, saf_kt=saf, demand_kt=sum(demand.values()), demand_by_airport=demand, delivered_by_airport=deliv,
        fill_rate=min(1.0, saf / sum(demand.values())) if sum(demand.values()) else 1.0,
        n_depots=len(open_d), n_depots_small=sum(s == "small" for s in open_d.values()), n_depots_large=sum(s == "large" for s in open_d.values()),
        n_refineries=len(open_r), n_refineries_small=sum(s == "small" for s in open_r.values()), n_refineries_large=sum(s == "large" for s in open_r.values()),
        unit_cost_usd_t=total / saf * 1000 if saf else None,
        mean_refinery_utilisation=float(np.mean([r["utilisation"] for r in refineries])) if refineries else 0.0,
        mean_depot_utilisation=float(np.mean([r["utilisation"] for r in depots])) if depots else 0.0,
        mean_km_farm_depot=tkm["farm_depot"] / biomass if biomass else 0.0,
        mean_km_depot_refinery=tkm["depot_refinery"] / gate if gate else 0.0,
        mean_km_refinery_airport=tkm["refinery_airport"] / saf if saf else 0.0,
    )
    return Solution(p.to_dict(), status, message, objective, bound, gap, runtime, depots=depots, refineries=refineries, flows_fd=flows_fd, flows_dr=flows_dr, flows_ra=flows_ra, costs=costs, kpis=kpis, **size)
