"""Independent check of a solution against the raw inputs.

Nothing here reads the solver's constraint matrix. It recomputes every balance and
the objective from the flow records, so a modelling slip cannot hide in both places.
"""
from collections import defaultdict

from .config import Params
from .data import Network
from .model import airport_demand

TOL = 1e-3


def check(sol: dict, p: Params, net: Network) -> list:
    """Return one record per constraint family: name, passed, worst value, limit."""
    out = []

    def rec(name, worst, limit, passed):
        out.append(dict(check=name, passed=bool(passed), worst=float(worst), limit=float(limit)))

    B = dict(zip(net.sites.location_id, net.sites.production_kilotons * p.biomass_multiplier))
    shipped = defaultdict(float)
    dep_in, dep_out, ref_in, ref_out, air_in = (defaultdict(float) for _ in range(5))
    for f in sol["flows_fd"]:
        shipped[f["src"]] += f["kt"]
        dep_in[f["dst"]] += f["kt"]
    for f in sol["flows_dr"]:
        dep_out[f["src"]] += f["kt"]
        ref_in[f["dst"]] += f["kt"]
    for f in sol["flows_ra"]:
        ref_out[f["src"]] += f["kt"]
        air_in[f["dst"]] += f["kt"]

    excess = max([shipped[i] - B[i] for i in shipped] or [0.0])
    rec("Biomass availability at each site (kt over)", excess, TOL, excess <= TOL)

    depots = {d["id"]: d for d in sol["depots"]}
    refs = {r["id"]: r for r in sol["refineries"]}
    unopened = [j for j in dep_in if j not in depots] + [k for k in ref_in if k not in refs]
    rec("Flows only through opened facilities (count)", len(unopened), 0, not unopened)

    over = max([dep_in[j] - p.depot_cap[d["size"]] for j, d in depots.items()] or [0.0])
    rec("Depot capacity (kt over)", over, TOL, over <= TOL)

    bal = max([abs(dep_out[j] - p.retention * dep_in[j]) for j in depots] or [0.0])
    rec("Depot mass balance (kt residual)", bal, TOL * 10, bal <= TOL * 10)

    used = ref_in if p.refinery_basis == "input" else ref_out
    over = max([used[k] - p.refinery_cap[r["size"]] for k, r in refs.items()] or [0.0])
    rec("Refinery capacity (kt over)", over, TOL, over <= TOL)

    bal = max([abs(ref_out[k] - p.yield_saf * ref_in[k]) for k in refs] or [0.0])
    rec("Refinery conversion balance (kt residual)", bal, TOL * 10, bal <= TOL * 10)

    D = airport_demand(p, net)
    short = max(D[a] - air_in[a] for a in D)
    rec("Airport demand met (kt short)", short, TOL * 10, short <= TOL * 10)

    per_site = max([sum(1 for d in sol["depots"] if d["id"] == j) for j in depots] or [0])
    rec("At most one depot per site (count)", per_site, 1, per_site <= 1)
    per_site = max([sum(1 for r in sol["refineries"] if r["id"] == k) for k in refs] or [0])
    rec("At most one refinery per site (count)", per_site, 1, per_site <= 1)

    d = net.road
    m = p.distance_multiplier
    log = (
        sum(f["kt"] * d.at[f["src"], f["dst"]] for f in sol["flows_fd"]) * p.tariff_fd
        + sum(f["kt"] * d.at[f["src"], f["dst"]] for f in sol["flows_dr"]) * p.tariff_dr
        + sum(f["kt"] * d.at[f["src"], f["dst"]] for f in sol["flows_ra"]) * p.tariff_ra
    ) * m / 1000
    capex = sum(p.depot_capex[x["size"]] for x in sol["depots"]) + sum(p.refinery_capex[x["size"]] for x in sol["refineries"])
    var = (sum(ref_in.values()) * p.refinery_opex_var + sum(dep_in.values()) * (p.depot_opex_var + p.biomass_price)) / 1000
    total = capex * (p.annuity + p.fixed_opex_frac) + var + log
    diff = abs(total - sol["objective"]) / max(1.0, abs(total))
    rec("Objective recomputed from flows (relative difference)", diff, 1e-4, diff <= 1e-4)
    return out


def all_passed(records: list) -> bool:
    return all(r["passed"] for r in records)
