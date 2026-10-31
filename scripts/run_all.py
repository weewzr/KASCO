"""Solve every shipped scenario and write the results the app and documents read.

    python scripts/run_all.py [scenarios|baselines|ladder|sensitivity|all]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saf.baselines import airport_baseline, greedy_baseline, trip_counts  # noqa: E402
from saf.config import Params  # noqa: E402
from saf.data import load_network, validate_inputs  # noqa: E402
from saf.diagnostics import diagnose  # noqa: E402
from saf.model import airport_demand, max_saf_kt, solve  # noqa: E402
from saf.scenarios import HUB, SCENARIOS  # noqa: E402
from saf.validate import all_passed, check  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "results"
OUT.mkdir(parents=True, exist_ok=True)
net = load_network()


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def save(name, obj):
    (OUT / f"{name}.json").write_text(json.dumps(clean(obj), indent=0))


def run_scenarios():
    index = {}
    for key, p in SCENARIOS.items():
        t = time.time()
        s = solve(p, net).to_dict()
        rec = dict(key=key, name=p.name, status=s["status"], objective=s["objective"], gap=s["gap"], runtime_s=s["runtime_s"])
        if s["status"] in ("optimal", "feasible_gap"):
            s["validation"] = check(s, p, net)
            s["trips"] = trip_counts(s)
            rec["valid"] = all_passed(s["validation"])
        else:
            s["diagnostics"] = diagnose(p, net)
        save(key, s)
        index[key] = rec
        print(key, s["status"], s["objective"], s["gap"], f"{time.time() - t:.0f}s", flush=True)
    save("index", index)


def run_baselines():
    out = {}
    for key in ("policy_base", "high_demand", "hub_full"):
        p = SCENARIOS[key]
        s = json.loads((OUT / f"{key}.json").read_text())
        row = dict(optimised=s["objective"], unit=s["kpis"]["unit_cost_usd_t"], status=s["status"], gap=s["gap"], n_ref=s["kpis"]["n_refineries"], n_dep=s["kpis"]["n_depots"], logistics=s["costs"]["logistics_total"])
        for name, fn in (("greedy", greedy_baseline), ("airport_first", airport_baseline)):
            b = fn(p, net).to_dict()
            v = check(b, p, net)
            row[name] = dict(objective=b["objective"], valid=all_passed(v), n_ref=b["kpis"]["n_refineries"], n_dep=b["kpis"]["n_depots"], logistics=b["costs"]["logistics_total"], unit=b["kpis"]["unit_cost_usd_t"], saving_pct=100 * (b["objective"] - s["objective"]) / b["objective"], saving_usd_m=b["objective"] - s["objective"])
        out[key] = row
        print(key, json.dumps(clean(row))[:400], flush=True)
    save("baselines", out)


def run_ladder():
    """Unit cost as demand rises from the policy level to the full feedstock limit."""
    up = sum(Params().uplift_kt.values())
    pts = []
    for blend, label in [(0.01, "SG 2026, 1%"), (0.03, "SG 2030 low, 3%"), (0.05, "SG 2030 high, 5%"), (0.10, "10%"), (0.25, "25%"), (0.50, "ASTM limit, 50%"), (1.00, "100% of uplift")]:
        pts.append((Params(blend=blend), label))
    top = max_saf_kt(Params(), net)
    for kt in (200, 300, 400, 600, 800, 1000):
        share = {a: kt * v / up for a, v in Params().uplift_kt.items()}
        pts.append((Params(demand_mode="absolute", airport_kt=share, time_limit_s=150.0, mip_gap=0.02), f"{kt} kt"))
    out = []
    for p, label in pts:
        p = p.with_(time_limit_s=max(p.time_limit_s, 90.0))
        s = solve(p, net).to_dict()
        k = s["kpis"]
        out.append(dict(label=label, saf_kt=k["saf_kt"], unit=k["unit_cost_usd_t"], total=s["objective"], n_ref=k["n_refineries"], n_large=k["n_refineries_large"], n_small=k["n_refineries_small"], n_dep=k["n_depots"], biomass=k["biomass_used_kt"], util=k["mean_refinery_utilisation"], status=s["status"], gap=s["gap"]))
        print(label, s["status"], round(k["saf_kt"], 1), round(k["unit_cost_usd_t"]), k["n_refineries"], flush=True)
    hub = json.loads((OUT / "hub_full.json").read_text())
    k = hub["kpis"]
    out.append(dict(label="Full feedstock", saf_kt=k["saf_kt"], unit=k["unit_cost_usd_t"], total=hub["objective"], n_ref=k["n_refineries"], n_large=k["n_refineries_large"], n_small=k["n_refineries_small"], n_dep=k["n_depots"], biomass=k["biomass_used_kt"], util=k["mean_refinery_utilisation"], status=hub["status"], gap=hub["gap"]))
    save("ladder", out)


def run_sensitivity():
    """One-at-a-time +/-20% around the high-demand policy case and the hub."""
    cases = [
        ("Refinery CapEx", lambda p, f: p.with_(refinery_capex={k: v * f for k, v in p.refinery_capex.items()})),
        ("Transport tariffs", lambda p, f: p.with_(tariff_fd=p.tariff_fd * f, tariff_dr=p.tariff_dr * f, tariff_ra=p.tariff_ra * f)),
        ("SAF yield", lambda p, f: p.with_(yield_saf=p.yield_saf * f)),
        ("Road distance", lambda p, f: p.with_(distance_multiplier=f)),
        ("Fixed OpEx fraction", lambda p, f: p.with_(fixed_opex_frac=p.fixed_opex_frac * f)),
        ("Discount rate", lambda p, f: p.with_(discount_rate=p.discount_rate * f)),
    ]
    base = json.loads((OUT / "hub_full.json").read_text())
    p0 = HUB
    keep = tuple(r["id"] for r in base["refineries"])
    site_order = list(net.road.loc[list(keep)].min().sort_values().index)
    # Candidates are limited to sites near the base fleet, so each run stays comparable.
    pool = tuple(site_order[:30])
    out = []
    for name, fn in cases:
        row = dict(name=name)
        for tag, f in (("low", 0.8), ("high", 1.2)):
            p = fn(p0, f).with_(allow_refinery_sites=pool, time_limit_s=120.0, mip_gap=0.015)
            if name == "SAF yield":
                p = p.with_(demand_mode="hub")
            s = solve(p, net).to_dict()
            row[tag] = dict(objective=s["objective"], unit=s["kpis"].get("unit_cost_usd_t"), n_ref=s["kpis"].get("n_refineries"), status=s["status"], gap=s["gap"], saf=s["kpis"].get("saf_kt"))
        out.append(row)
        print(name, row["low"]["objective"], row["high"]["objective"], flush=True)
    save("sensitivity", dict(base=base["objective"], base_unit=base["kpis"]["unit_cost_usd_t"], rows=out, note="Refinery candidates limited to 30 sites near the base fleet."))


def run_meta():
    p = Params()
    save("meta", dict(inputs=validate_inputs(net), uplift=p.uplift_kt, demand_policy=airport_demand(p, net), max_saf=max_saf_kt(p, net), crf=p.annuity))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    run_meta()
    if what in ("scenarios", "all"):
        run_scenarios()
    if what in ("baselines", "all"):
        run_baselines()
    if what in ("ladder", "all"):
        run_ladder()
    if what in ("sensitivity", "all"):
        run_sensitivity()
