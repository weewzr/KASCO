"""Deterministic decision support.

No language model is involved. A question is matched to an intent by keywords, each
intent reads fields from a solver result, and what-if requests become Params changes
that run the real solver. Questions outside the model are declined.
"""
import re

from .baselines import airport_baseline, greedy_baseline
from .config import Params
from .data import Network
from .diagnostics import diagnose
from .model import solve


def _status_line(sol: dict) -> str:
    if sol["status"] == "optimal":
        return f"Solver status: optimal within tolerance, gap {100 * (sol['gap'] or 0):.2f}%."
    if sol["status"] == "feasible_gap":
        return f"Solver status: feasible, gap {100 * (sol['gap'] or 0):.2f}%. Better networks may exist within that margin."
    return f"Solver status: {sol['status']}."


def _usd(x: float) -> str:
    return f"USD {x:,.1f}M"


def _named_site(q: str, sol: dict) -> dict | None:
    m = re.search(r"kal[_ ]?sup[_ ]?(\d{1,2})", q, re.I)
    if m:
        target = f"KAL_SUP_{int(m.group(1)):02d}"
        return next((r for r in sol["refineries"] if r["id"] == target), None)
    m = re.search(r"\b(pnk|pkn|bpn|trk)\b", q, re.I)
    if m:
        return next((r for r in sol["refineries"] if r["id"] == m.group(1).upper()), None)
    return None


def why_refinery(q, sol, p, net):
    if not sol["refineries"]:
        return "No refinery is open in this result.", []
    r = _named_site(q, sol) or max(sol["refineries"], key=lambda x: x["throughput"])
    feeders = [f for f in sol["flows_dr"] if f["dst"] == r["id"]]
    served = [f for f in sol["flows_ra"] if f["src"] == r["id"]]
    site = net.sites.set_index("location_id")
    place = f"{site.at[r['id'], 'district']}, {site.at[r['id'], 'province']}" if r["id"] in site.index else "airport site"
    lines = [
        f"**{r['id']}** ({place}) is a {r['size']} refinery running at {100 * r['utilisation']:.1f}% of {r['capacity']:,.0f} kt/yr.",
        f"It takes {r['biomass_in']:,.1f} kt biomass from {len(feeders)} depots at a mean {sum(f['km'] * f['kt'] for f in feeders) / max(1e-9, sum(f['kt'] for f in feeders)):.0f} road km, "
        f"and ships {r['saf_kt']:,.1f} kt SAF to {', '.join(f['dst'] for f in served)}.",
    ]
    # Counterfactual: close this site, allow its five nearest alternatives.
    others = [x["id"] for x in sol["refineries"] if x["id"] != r["id"]]
    pool = [s for s in net.road.loc[r["id"]].sort_values().index if s != r["id"] and s not in others][:5]
    alt = solve(p.with_(allow_refinery_sites=tuple(others + pool), time_limit_s=min(30.0, p.time_limit_s), mip_gap=0.002), net)
    if alt.has_network and alt.objective is not None:
        delta = alt.objective - sol["objective"]
        lines.append(
            f"Counterfactual solve: closing it and allowing its 5 nearest alternatives gives {_usd(alt.objective)}/yr, "
            f"a change of {_usd(delta)}/yr. {'This site holds up against its neighbours.' if delta >= -1e-6 else 'A neighbour is slightly cheaper, which the reported gap allows for.'}"
        )
    else:
        lines.append("Counterfactual solve: with this site closed and only its 5 nearest alternatives allowed, no feasible network was found.")
    return "\n\n".join(lines), [f"refineries[{r['id']}]", "flows_dr", "flows_ra", "counterfactual MILP"]


def expensive_routes(q, sol, p, net):
    flows = [("farm to depot", f) for f in sol["flows_fd"]] + [("depot to refinery", f) for f in sol["flows_dr"]] + [("refinery to airport", f) for f in sol["flows_ra"]]
    flows.sort(key=lambda t: -t[1]["usd_m"])
    rows = "\n".join(f"{n}. {f['src']} to {f['dst']} ({leg}): {_usd(f['usd_m'])}/yr, {f['kt']:,.1f} kt over {f['km']:,.0f} km" for n, (leg, f) in enumerate(flows[:5], 1))
    c = sol["costs"]
    tail = f"All logistics total {_usd(c['logistics_total'])}/yr, which is {100 * c['logistics_total'] / c['total_annual']:.1f}% of annual cost."
    return f"Five most expensive routes:\n\n{rows}\n\n{tail}", ["flows_fd", "flows_dr", "flows_ra", "costs"]


def depot_sizes(q, sol, p, net):
    k = sol["kpis"]
    unit_s = p.depot_capex["small"] / p.depot_cap["small"]
    unit_l = p.depot_capex["large"] / p.depot_cap["large"]
    txt = (
        f"This network opens {k['n_depots_large']} large and {k['n_depots_small']} small depots. "
        f"Capital per kt is USD {1000 * unit_s:,.0f}k for small and USD {1000 * unit_l:,.0f}k for large, "
    )
    if abs(unit_s - unit_l) < 1e-9:
        txt += (
            "so the brief's prices give neither size a scale advantage. Large appears where a site gathers more than "
            f"{p.depot_cap['small']:.0f} kt, because each site holds one depot. A large depot therefore saves sites, and it saves no money."
        )
    else:
        txt += "so scale now plays a part in the size choice."
    return txt, ["kpis.n_depots_large", "kpis.n_depots_small", "params.depot_capex"]


def near_capacity(q, sol, p, net):
    th = 0.90
    m = re.search(r"(\d{1,3})\s*%", q)
    if m:
        th = int(m.group(1)) / 100
    hits = [("refinery", r) for r in sol["refineries"] if r["utilisation"] >= th] + [("depot", d) for d in sol["depots"] if d["utilisation"] >= th]
    hits.sort(key=lambda t: -t[1]["utilisation"])
    if not hits:
        low = sorted(sol["refineries"], key=lambda r: r["utilisation"])
        extra = f" The least used refinery is {low[0]['id']} at {100 * low[0]['utilisation']:.1f}%." if low else ""
        return f"No facility is at or above {100 * th:.0f}% utilisation.{extra}", ["refineries", "depots"]
    rows = "\n".join(f"- {kind} {x['id']} ({x['size']}): {100 * x['utilisation']:.1f}%" for kind, x in hits[:12])
    more = f"\n\n{len(hits) - 12} more not shown." if len(hits) > 12 else ""
    return f"{len(hits)} facilities are at or above {100 * th:.0f}%:\n\n{rows}{more}", ["refineries.utilisation", "depots.utilisation"]


def infeasible(q, sol, p, net):
    d = diagnose(p, net)
    if sol["status"] == "infeasible" or d["findings"]:
        rows = "\n".join(f"- **{f['limit']}**: {f['reason']} Fix: {f['fix']}" for f in d["findings"])
        return f"This scenario has no feasible network.\n\n{rows or 'No single arithmetic limit is broken, so the conflict lies between constraints. Relax one and rerun.'}", ["diagnostics"]
    return f"This scenario is feasible. {_status_line(sol)}", ["status"]


def baseline(q, sol, p, net):
    rows = []
    for fn, label in ((greedy_baseline, "Greedy heuristic"), (airport_baseline, "Airport-first")):
        b = fn(p, net)
        cost = b.costs["total_annual"]
        rows.append(f"- {label}: {_usd(cost)}/yr. The optimised network saves {_usd(cost - sol['objective'])}/yr ({100 * (cost - sol['objective']) / cost:.1f}%).")
    return f"Optimised network: {_usd(sol['objective'])}/yr on the same demand and cost basis.\n\n" + "\n".join(rows), ["baselines", "objective"]


def cost_breakdown(q, sol, p, net):
    c = sol["costs"]
    k = sol["kpis"]
    return (
        f"Total {_usd(c['total_annual'])}/yr, or USD {k['unit_cost_usd_t']:,.0f}/t SAF delivered.\n\n"
        f"- Capital charge: {_usd(c['annual_capital'])}/yr on {_usd(c['capex_total'])} CapEx at CRF {p.annuity:.4f}\n"
        f"- Fixed OpEx: {_usd(c['opex_fixed'])}/yr\n"
        f"- Variable OpEx: {_usd(c['opex_variable'])}/yr\n"
        f"- Logistics: {_usd(c['logistics_total'])}/yr"
    ), ["costs", "kpis.unit_cost_usd_t"]


PCT = r"([+-]?\d+(?:\.\d+)?)\s*%"


def parse_change(q: str, p: Params) -> tuple:
    """Turn a what-if sentence into a Params change. Returns (params, description)."""
    ql = q.lower()
    sign = -1 if re.search(r"\b(falls?|drops?|decreases?|reduces?|cut|lower|down|less)\b", ql) else 1
    m = re.search(PCT, ql)
    pct = abs(float(m.group(1))) / 100 * (-1 if m and m.group(1).startswith("-") else sign) if m else None
    y = re.search(r"yield[^0-9]*(0?\.\d+)", ql)
    if y:
        v = float(y.group(1))
        return p.with_(yield_saf=v), f"yield set to {v:.2f}"
    if "blend" in ql and m:
        v = abs(float(m.group(1))) / 100
        return p.with_(demand_mode="blend", blend=v), f"blend set to {100 * v:.1f}% of uplift"
    if pct is None:
        return None, None
    f = 1 + pct
    if re.search(r"transport|tariff|logistic|truck|freight", ql):
        return p.with_(tariff_fd=p.tariff_fd * f, tariff_dr=p.tariff_dr * f, tariff_ra=p.tariff_ra * f), f"all tariffs changed by {100 * pct:+.0f}%"
    if re.search(r"biomass|feedstock|supply", ql):
        return p.with_(biomass_multiplier=p.biomass_multiplier * f), f"biomass availability changed by {100 * pct:+.0f}%"
    if re.search(r"refinery.*(cost|capex)|capex.*refinery", ql):
        return p.with_(refinery_capex={k: v * f for k, v in p.refinery_capex.items()}), f"refinery CapEx changed by {100 * pct:+.0f}%"
    if re.search(r"depot.*(cost|capex)", ql):
        return p.with_(depot_capex={k: v * f for k, v in p.depot_capex.items()}), f"depot CapEx changed by {100 * pct:+.0f}%"
    if re.search(r"demand", ql):
        return p.with_(demand_multiplier=p.demand_multiplier * f), f"demand changed by {100 * pct:+.0f}%"
    return None, None


def what_if(q, sol, p, net):
    new, desc = parse_change(q, p)
    if new is None:
        return "I could not map that to a solver input. Try: demand up 20%, transport up 30%, biomass down 10%, yield 0.12, blend 3%, refinery cost up 15%.", []
    s = solve(new.with_(time_limit_s=min(p.time_limit_s, 90.0)), net)
    if not s.has_network:
        d = diagnose(new, net)
        rows = "\n".join(f"- **{f['limit']}**: {f['reason']} Fix: {f['fix']}" for f in d["findings"])
        return f"Change applied: {desc}. The solver reports **{s.status}**.\n\n{rows}", ["solver rerun", "diagnostics"]
    k0, k1 = sol["kpis"], s.kpis
    return (
        f"Change applied: {desc}. The solver reran with this input.\n\n"
        f"- Total cost: {_usd(sol['objective'])} to {_usd(s.objective)}/yr ({100 * (s.objective / sol['objective'] - 1):+.1f}%)\n"
        f"- Unit cost: USD {k0['unit_cost_usd_t']:,.0f}/t to USD {k1['unit_cost_usd_t']:,.0f}/t\n"
        f"- Refineries: {k0['n_refineries']} to {k1['n_refineries']}\n"
        f"- Depots: {k0['n_depots']} to {k1['n_depots']}\n"
        f"- SAF delivered: {k0['saf_kt']:,.1f} kt to {k1['saf_kt']:,.1f} kt\n\n"
        f"{_status_line(s.to_dict())}"
    ), ["solver rerun", "objective", "kpis"]


OUT_OF_SCOPE = r"carbon|co2|ghg|emission|lifecycle|price of|selling price|profit|npv|irr|revenue|weather|flood|land use|deforest|permit|law|legal|politic|safety"

INTENTS = [
    ("infeasible", r"infeasib|why.*(fail|no solution)|not feasible", infeasible),
    ("what_if", r"what happens|what if|suppose|if .*(increase|decrease|rise|fall|drop|up|down)|rerun|re-run|\d\s*%.*(demand|transport|biomass|yield|blend|cost)", what_if),
    ("refinery", r"why.*(refiner|site|located|selected|chosen)|refiner.*(why|selected|chosen)", why_refinery),
    ("routes", r"expensive|costly|route|costliest", expensive_routes),
    ("depots", r"depot.*(large|small|size)|(large|small).*depot", depot_sizes),
    ("capacity", r"near capacity|utili[sz]ation|bottleneck|capacity|full", near_capacity),
    ("baseline", r"baseline|improve|saving|better than|compared", baseline),
    ("cost", r"cost|breakdown|total|unit|how much", cost_breakdown),
]


def answer(question: str, sol: dict, p: Params, net: Network) -> dict:
    """Route a question. Every reply lists the fields it read."""
    q = question.strip()
    if not q:
        return dict(intent="empty", text="Type a question.", sources=[], declined=False)
    if re.search(OUT_OF_SCOPE, q, re.I) and not re.search(r"what if|what happens", q, re.I):
        return dict(
            intent="declined", declined=True, sources=[],
            text="I can't answer that. The model holds cost, mass flow and capacity only, so any figure here would be invented. "
                 "A qualified reviewer needs a separate lifecycle, commercial or regulatory assessment.",
        )
    has_network = bool(sol.get("depots") or sol.get("refineries"))
    for name, pat, fn in INTENTS:
        if re.search(pat, q, re.I):
            if not has_network and name not in ("infeasible", "what_if"):
                text, src = infeasible(q, sol, p, net)
            elif name == "what_if" and not has_network:
                text, src = "The current scenario has no network to compare with. Switch to a feasible scenario first.", []
            else:
                text, src = fn(q, sol, p, net)
            return dict(intent=name, text=text, sources=src, declined=False)
    return dict(
        intent="unmatched", declined=True, sources=[],
        text="That question is outside what I can trace to solver output. I can explain refinery choices, route costs, depot sizes, "
             "capacity use, infeasibility, baseline savings and what-if changes.",
    )
