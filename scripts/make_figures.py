"""Draw the report and deck figures from the solver's result files.

    python scripts/make_figures.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "docs" / "reports" / "fig"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
THEMES = {
    "light": dict(bg="#ffffff", land="#eeeeea", coast="#c9c8c0", text="#0b0b0b", muted="#52514e", grid="#e6e5e0", ring="#ffffff"),
    "dark": dict(bg="#1a1a19", land="#2b2b29", coast="#46453f", text="#f0efec", muted="#c3c2b7", grid="#34332f", ring="#1a1a19"),
}


def load(name):
    return json.loads((DATA / f"{name}.json").read_text())


NET = load("network")
LAND = json.loads((ROOT / "data" / "borneo_land.json").read_text())


def style(ax, t):
    ax.set_facecolor(t["bg"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(t["grid"])
    ax.tick_params(colors=t["muted"], labelsize=9)
    ax.grid(color=t["grid"], linewidth=0.7)
    ax.set_axisbelow(True)


def network_map(key, theme, name, title=None):
    t = THEMES[theme]
    s = load(key)
    fig, ax = plt.subplots(figsize=(9.2, 7.4), dpi=170, facecolor=t["bg"])
    ax.set_facecolor(t["bg"] if theme == "light" else "#141413")
    for ring in LAND:
        xs, ys = zip(*ring)
        ax.fill(xs, ys, color=t["land"], ec=t["coast"], lw=0.5, zorder=1)
    pos = s["node_coords"]
    top = max(f["kt"] for f in s["flows_fd"])
    for f in s["flows_fd"]:
        a, b = pos[f["src"]], pos[f["dst"]]
        ax.plot([a[1], b[1]], [a[0], b[0]], color=AQUA, lw=0.5 + 2.2 * (f["kt"] / top) ** 0.5, alpha=0.7, zorder=3)
    for f in s["flows_dr"]:
        if f["km"] > 0:
            a, b = pos[f["src"]], pos[f["dst"]]
            ax.plot([a[1], b[1]], [a[0], b[0]], color=YELLOW, lw=0.6 + 2.0 * (f["kt"] / top) ** 0.5, alpha=0.8, zorder=3)
    tops = max(f["kt"] for f in s["flows_ra"])
    for f in s["flows_ra"]:
        a, b = pos[f["src"]], pos[f["dst"]]
        ax.plot([a[1], b[1]], [a[0], b[0]], color=BLUE, lw=0.8 + 3.4 * (f["kt"] / tops) ** 0.5, alpha=0.8, zorder=4, solid_capstyle="round")
    used = {f["src"] for f in s["flows_fd"]}
    for x in NET["sites"]:
        on = x["id"] in used
        ax.scatter(x["lon"], x["lat"], s=4 + x["kt"] / 3.2, c=AQUA if on else "none", edgecolors=AQUA, linewidths=0.8, alpha=0.95 if on else 0.75, zorder=5)
    if not any(d["colocated"] for d in s["depots"]):
        for d in s["depots"]:
            ax.scatter(d["lon"], d["lat"], s=62, marker="D", c=YELLOW, edgecolors=t["ring"], linewidths=0.8, zorder=6)
    for r in s["refineries"]:
        ax.scatter(r["lon"], r["lat"], s=175, marker="s", c=ORANGE, edgecolors=t["ring"], linewidths=1.3, zorder=7)
        ax.annotate(r["id"] if r["id"].startswith("R") else "", (r["lon"], r["lat"]), textcoords="offset points", xytext=(9, 8), color=t["text"], fontsize=9, fontweight="bold", zorder=9)
    for a in NET["airports"]:
        ax.scatter(a["lon"], a["lat"], s=230, marker="o", c=BLUE, edgecolors=t["ring"], linewidths=1.4, zorder=8)
        ax.annotate(a["iata"], (a["lon"], a["lat"]), ha="center", va="center", color="white", fontsize=7, fontweight="bold", zorder=10)
    ax.set_xlim(108.4, 119.4)
    ax.set_ylim(-4.6, 4.5)
    ax.set_aspect("equal")
    ax.tick_params(colors=t["muted"], labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(t["grid"])
    items = [
        Line2D([], [], marker="o", ls="", color=AQUA, label="Biomass site"),
        Line2D([], [], marker="o", ls="", markerfacecolor="none", color=AQUA, label="Site not used"),
        Line2D([], [], marker="s", ls="", color=ORANGE, markersize=9, label="Refinery with depots" if any(d["colocated"] for d in s["depots"]) else "Refinery"),
        Line2D([], [], marker="o", ls="", color=BLUE, markersize=9, label="Airport"),
        Line2D([], [], color=AQUA, label="Biomass flow"),
        Line2D([], [], color=BLUE, lw=2.4, label="SAF flow"),
    ]
    if not any(d["colocated"] for d in s["depots"]):
        items.insert(2, Line2D([], [], marker="D", ls="", color=YELLOW, label="Field depot"))
    leg = ax.legend(handles=items, loc="upper left", fontsize=8.5, facecolor=t["bg"], edgecolor=t["grid"], labelcolor=t["text"], framealpha=0.95)
    leg.get_frame().set_linewidth(0.6)
    if title:
        ax.set_title(title, color=t["text"], fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / name, facecolor=t["bg"])
    plt.close(fig)


def cost_stack(theme, name):
    t = THEMES[theme]
    c = load("official_base")["costs"]
    parts = [("Annualised CapEx", c["annual_capex"], BLUE), ("Fixed OpEx", c["opex_fixed"], ORANGE), ("Variable OpEx", c["opex_variable"], AQUA), ("Transport", c["logistics_total"], YELLOW)]
    fig, ax = plt.subplots(figsize=(7.2, 1.7), dpi=170, facecolor=t["bg"])
    x = 0
    for label, v, col in parts:
        ax.barh(0, v, left=x, color=col, edgecolor=t["bg"], linewidth=2, height=0.55, label=f"{label}, {v:.1f}")
        x += v
    style(ax, t)
    ax.grid(False)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("USD M per year", color=t["muted"], fontsize=9)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.5), frameon=False, fontsize=8.5, labelcolor=t["text"])
    fig.tight_layout()
    fig.savefig(OUT / name, facecolor=t["bg"])
    plt.close(fig)


def baseline(theme, name):
    t = THEMES[theme]
    b = load("baselines")
    rows = [("Optimised", b["optimised"], BLUE), ("Field depots", b["field"], "#8f8e85"), ("Greedy heuristic", b["greedy"], "#8f8e85"), ("Airport-first", b["airport_first"], "#8f8e85")]
    fig, ax = plt.subplots(figsize=(6.6, 2.5), dpi=170, facecolor=t["bg"])
    ys = range(len(rows))[::-1]
    for y, (label, r, col) in zip(ys, rows):
        ax.barh(y, r["objective"], color=col, height=0.5)
        ax.text(r["objective"] + 6, y, f"{r['objective']:.1f}", va="center", color=t["text"], fontsize=9)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([r[0] for r in rows], color=t["text"], fontsize=9)
    style(ax, t)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 1100)
    ax.set_xlabel("USD M per year", color=t["muted"], fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / name, facecolor=t["bg"])
    plt.close(fig)


def tornado(theme, name):
    t = THEMES[theme]
    s = load("sensitivity")
    base = s["base"]
    rows = sorted(s["rows"], key=lambda r: max(abs((r[k]["objective"] or base) - base) for k in ("low", "high")))
    fig, ax = plt.subplots(figsize=(6.6, 3.1), dpi=170, facecolor=t["bg"])
    for i, r in enumerate(rows):
        for k, col in (("low", BLUE), ("high", ORANGE)):
            o = r[k]["objective"]
            if o is None:
                ax.text(4 if k == "low" else -4, i, "-20% infeasible", va="center", ha="left" if k == "low" else "right", color=t["muted"], fontsize=8)
            else:
                ax.barh(i, o - base, color=col, height=0.5)
    ax.axvline(0, color=t["muted"], lw=0.8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["name"] for r in rows], color=t["text"], fontsize=9)
    style(ax, t)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in annual cost, USD M", color=t["muted"], fontsize=9)
    h = [Line2D([], [], color=BLUE, lw=6, label="Input -20%"), Line2D([], [], color=ORANGE, lw=6, label="Input +20%")]
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.4, 1.14), ncol=2, frameon=False, fontsize=8.5, labelcolor=t["text"])
    fig.tight_layout()
    fig.savefig(OUT / name, facecolor=t["bg"])
    plt.close(fig)


def ladder(theme, name):
    t = THEMES[theme]
    pts = [p for p in load("ladder") if p["objective"]]
    fig, ax = plt.subplots(figsize=(6.6, 3.0), dpi=170, facecolor=t["bg"])
    ax.plot([p["level"] for p in pts], [p["unit"] for p in pts], color=BLUE, lw=2, marker="o", ms=5)
    ax.set_yscale("log")
    ax.set_yticks([500, 1000, 2000, 5000, 10000])
    ax.set_yticklabels(["500", "1,000", "2,000", "5,000", "10,000"])
    ax.minorticks_off()
    style(ax, t)
    ax.set_xlabel("Total SAF demand, kt per year", color=t["muted"], fontsize=9)
    ax.set_ylabel("USD per tonne SAF", color=t["muted"], fontsize=9)
    last = pts[-2]
    ax.annotate(f"Official demand: USD {last['unit']:,.0f}/t", (last["level"], last["unit"]), textcoords="offset points", xytext=(-108, 22), color=t["text"], fontsize=9)
    first = pts[0]
    ax.annotate(f"Real uplift at 5% blend: about USD {first['unit']:,.0f}/t", (first["level"], first["unit"]), textcoords="offset points", xytext=(12, -3), color=t["text"], fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / name, facecolor=t["bg"])
    plt.close(fig)


if __name__ == "__main__":
    network_map("official_base", "light", "map_base.png")
    network_map("field_depots", "light", "map_field.png")
    network_map("official_base", "dark", "map_base_dark.png")
    for th in ("light",):
        cost_stack(th, "cost.png")
        baseline(th, "baseline.png")
        tornado(th, "tornado.png")
        ladder(th, "ladder.png")
    print("figures in", OUT)
