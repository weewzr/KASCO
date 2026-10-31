"""Explain why a scenario has no feasible network.

Each test is arithmetic on the inputs, so the reason stated is checkable by hand.
"""
import math

from .config import Params
from .data import Network
from .model import airport_demand, max_saf_kt


def diagnose(p: Params, net: Network) -> dict:
    """List every binding limit, ordered as material flows through the chain."""
    demand = sum(airport_demand(p, net).values())
    need_gate = demand / p.yield_saf
    need_raw = need_gate / p.retention
    avail = float(net.sites.production_kilotons.sum() * p.biomass_multiplier)
    findings = []

    def add(kind, have, need, unit, text, fix):
        findings.append(dict(limit=kind, available=have, required=need, unit=unit, reason=text, fix=fix))

    if need_raw > avail + 1e-6:
        add(
            "Biomass supply", avail, need_raw, "kt/yr",
            f"Demand of {demand:,.1f} kt SAF needs {need_raw:,.0f} kt raw biomass at yield {p.yield_saf:.2f} and retention {p.retention:.2f}, "
            f"but only {avail:,.0f} kt exists. The most this feedstock can make is {max_saf_kt(p, net):,.1f} kt SAF.",
            f"Reduce demand by {100 * (1 - avail / need_raw):.1f}%, or raise yield to at least {demand / (avail * p.retention):.3f}.",
        )
    if p.max_refineries:
        cap = p.max_refineries * p.refinery_cap["large"]
        need = need_gate if p.refinery_basis == "input" else demand
        if need > cap + 1e-6:
            add(
                "Refinery count", cap, need, "kt/yr",
                f"{p.max_refineries} large refineries handle {cap:,.0f} kt but the scenario needs {need:,.0f} kt.",
                f"Allow at least {math.ceil(need / p.refinery_cap['large'])} refineries.",
            )
    if p.max_depots:
        cap = p.max_depots * p.depot_cap["large"]
        if need_raw > cap + 1e-6:
            add(
                "Depot count", cap, need_raw, "kt/yr",
                f"{p.max_depots} large depots handle {cap:,.0f} kt but the scenario needs {need_raw:,.0f} kt.",
                f"Allow at least {math.ceil(need_raw / p.depot_cap['large'])} depots.",
            )
    n_sites = len(net.sites)
    if need_raw > n_sites * p.depot_cap["large"] + 1e-6:
        add(
            "Depot sites", n_sites * p.depot_cap["large"], need_raw, "kt/yr",
            f"With one depot per candidate site the network tops out at {n_sites * p.depot_cap['large']:,.0f} kt.",
            "Raise depot capacity or add candidate sites.",
        )
    return dict(demand_kt=demand, need_raw_kt=need_raw, available_kt=avail, findings=findings)
