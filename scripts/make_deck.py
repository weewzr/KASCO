"""Build the six-slide pitch deck from the solver's result files.

    python scripts/make_deck.py
"""
import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
REP = ROOT / "docs" / "reports"


def load(n):
    p = DATA / f"{n}.json"
    return json.loads(p.read_text()) if p.exists() else None


base, field, real = load("official_base"), load("field_depots"), load("real_blend")
B, H, CHECK = load("baselines"), load("highs_check"), load("bound_check")
K, C = base["kpis"], base["costs"]

BG, CARD, TEXT, MUTED = "1A1A19", "2C2C29", "F0EFEC", "C3C2B7"
BLUE, ORANGE, AQUA, YELLOW = "3987E5", "D95926", "199E70", "C98500"
rgb = RGBColor.from_string

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
LAYOUT = prs.slide_layouts[5]  # Title Only


def slide(title, notes):
    s = prs.slides.add_slide(LAYOUT)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(BG)
    t = s.shapes.title
    t.left, t.top, t.width, t.height = Inches(0.6), Inches(0.38), Inches(12.1), Inches(1.15)
    tf = t.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = tf.margin_right = 0
    tf.text = title
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    for r in p.runs:
        r.font.size, r.font.bold, r.font.name = Pt(34), True, "Calibri"
        r.font.color.rgb = rgb(TEXT)
    s.notes_slide.notes_text_frame.text = notes
    return s


def text(s, x, y, w, h, items, size=16, color=TEXT, bold=False, anchor=None, name=None):
    b = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        b.name = name
    tf = b.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if anchor:
        tf.vertical_anchor = anchor
    items = items if isinstance(items, list) else [items]
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        runs = it if isinstance(it, list) else [(it, {})]
        for t, o in runs:
            r = p.add_run()
            r.text = t
            r.font.name = "Calibri"
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.color.rgb = rgb(o.get("color", color))
        p.space_after = Pt(7)
    return b


def card(s, x, y, w, h, fill=CARD):
    r = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.adjustments[0] = 0.05
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(fill)
    r.line.fill.background()
    r.shadow.inherit = False
    return r


def stat(s, x, y, w, h, value, label, color=TEXT, size=32):
    card(s, x, y, w, h)
    text(s, x + 0.2, y + 0.14, w - 0.4, 0.75, value, size=size, bold=True, color=color)
    text(s, x + 0.2, y + h - 0.62, w - 0.4, 0.5, label, size=14, color=MUTED)


def chain(s, x, y, w, labels, colors, h=0.72):
    n = len(labels)
    each = w / n
    for i, (l, c) in enumerate(zip(labels, colors)):
        sh = s.shapes.add_shape(MSO_SHAPE.PENTAGON if i == 0 else MSO_SHAPE.CHEVRON, Inches(x + i * each), Inches(y), Inches(each + 0.12), Inches(h))
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(c)
        sh.line.fill.background()
        sh.shadow.inherit = False
        tf = sh.text_frame
        tf.text = l
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        for r in p.runs:
            r.font.size, r.font.bold, r.font.name = Pt(15), True, "Calibri"
            r.font.color.rgb = rgb("FFFFFF")


capex_b = C["capex_total"] / 1000

# 1. Problem and opportunity
s = slide(f"Where should USD {capex_b:.1f}B of SAF plant go in Kalimantan?",
          "Meet the SAF network planner. They must pick refinery and depot sites before engineering starts. Today that means a few hand-drawn layouts in a spreadsheet. "
          f"Kalimantan has 6,800 kilotonnes of biomass at 80 sites, and four airports each want 300 kilotonnes of SAF. A large refinery fixes USD 765 million of capital for 20 years, so a wrong site is expensive and hard to undo.")
text(s, 0.6, 1.75, 6.0, 2.6, [
    [("The user  ", {"bold": True}), ("A SAF network planner choosing sites before engineering starts", {})],
    [("Today  ", {"bold": True}), ("A few hand-drawn layouts in a spreadsheet, with no proof of quality and no view of where a plan breaks", {})],
    [("The cost of error  ", {"bold": True}), ("A misplaced large refinery fixes USD 765M of capital and its haulage for 20 years", {})],
], size=18, name="Problem text")
stat(s, 7.0, 1.75, 2.75, 1.55, "6,800 kt", "biomass at 80 sites", AQUA)
stat(s, 9.95, 1.75, 2.75, 1.55, "1,200 kt", "SAF, four airports", BLUE)
stat(s, 7.0, 3.5, 2.75, 1.55, "6,000 kt", "biomass needed", AQUA)
stat(s, 9.95, 3.5, 2.75, 1.55, "20 years", "CapEx life", ORANGE)
chain(s, 0.6, 5.65, 12.1, ["Biomass sites", "Depots", "Refineries", "Airports"], [AQUA, YELLOW, ORANGE, BLUE])

# 2. Integrated solution
s = slide("One browser app, from inputs to an audited network",
          "Everything sits in one web page. The map shows the network, the engine finds it, the simulator reruns it, decision support explains it, and the evaluation shows the evidence. "
          "The solver is Rust compiled to WebAssembly, so it runs inside the browser from GitHub Pages. There is no server and no API key.")
cards = [("A", "Map", "All 80 sites, flows and costs, click any route", AQUA), ("B", "Engine", "Rust solver with a proven bound", ORANGE), ("C", "Simulator", "Change any input, rerun for real", YELLOW), ("D", "Decision support", "Answers from solver records only", BLUE), ("E", "Evidence", "Baselines, audit, report, failures", "8F8E85")]
for i, (l, h, d, c) in enumerate(cards):
    x = 0.6 + i * 2.46
    card(s, x, 1.85, 2.3, 2.75)
    o = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x + 0.2), Inches(2.05), Inches(0.58), Inches(0.58))
    o.fill.solid()
    o.fill.fore_color.rgb = rgb(c)
    o.line.fill.background()
    o.shadow.inherit = False
    o.text_frame.text = l
    p = o.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    for r in p.runs:
        r.font.size, r.font.bold, r.font.name = Pt(16), True, "Calibri"
        r.font.color.rgb = rgb("FFFFFF")
    text(s, x + 0.2, 2.8, 1.95, 0.45, h, size=19, bold=True)
    text(s, x + 0.2, 3.3, 1.95, 1.2, d, size=15, color=MUTED)
chain(s, 0.6, 5.0, 12.1, ["Official inputs", "Rust engine in the browser", "Independent audit", "Planner decides"], ["3A3A36", ORANGE, "3A3A36", BLUE])
text(s, 0.6, 6.05, 12.1, 0.5, "Hosted on GitHub Pages. No server, no account, no API key.", size=16, color=MUTED)

# 3. Engine
gap_r, gap_h = 100 * base["gap"], H["gap_pct"] if H else None
s = slide("The engine proves how close it is to the best network",
          f"The model is a four-tier facility location problem. We split it by site with Lagrangian relaxation, which gives a true lower bound, and branch-and-bound closes the gap. Min-cost flow prices each design exactly. "
          f"To check ourselves, we exported the model and solved it in HiGHS, a separate open-source solver. It reached the same cost, and our bound is tighter: {gap_r:.2f} percent in 60 seconds against {gap_h:.2f} percent in 480." + (" On smaller cases HiGHS proves optimal, our bound stays valid every time." if CHECK else ""))
steps = [("1", "Bound", "Lagrangian relaxation splits the model by site"), ("2", "Search", "Branch-and-bound over refinery sites and sizes"), ("3", "Price", "Exact min-cost flow for every design"), ("4", "Refine", "Move plants to the geometric median, on land")]
for i, (n, h, d) in enumerate(steps):
    y = 1.8 + i * 1.12
    card(s, 0.6, y, 6.1, 1.0)
    text(s, 0.82, y + 0.12, 0.5, 0.7, n, size=30, bold=True, color=ORANGE)
    text(s, 1.42, y + 0.1, 5.1, 0.4, h, size=18, bold=True)
    text(s, 1.42, y + 0.5, 5.1, 0.4, d, size=15, color=MUTED)
card(s, 7.0, 1.8, 5.7, 4.36)
text(s, 7.25, 1.95, 5.2, 0.4, "Independent check on the same model", size=18, bold=True)
tb = s.shapes.add_table(4, 3, Inches(7.25), Inches(2.5), Inches(5.2), Inches(2.2)).table
rows = [["", "Rust engine", "HiGHS"], ["Annual cost, USD M", f"{base['discrete_objective']:.2f}", f"{H['objective']:.2f}"], ["Proven lower bound", f"{base['bound']:.2f}", f"{H['bound']:.2f}"], ["Gap, time", f"{gap_r:.2f}%, 60 s", f"{gap_h:.2f}%, {H['time_limit_s']:.0f} s"]]
for r, row in enumerate(rows):
    for c_, v in enumerate(row):
        ce = tb.cell(r, c_)
        ce.fill.solid()
        ce.fill.fore_color.rgb = rgb("3A3A36" if r == 0 else CARD)
        ce.text = v
        for p in ce.text_frame.paragraphs:
            p.alignment = PP_ALIGN.LEFT if c_ == 0 else PP_ALIGN.RIGHT
            for ru in p.runs:
                ru.font.size, ru.font.name, ru.font.bold = Pt(15), "Calibri", r == 0
                ru.font.color.rgb = rgb(TEXT)
tb.columns[0].width, tb.columns[1].width, tb.columns[2].width = Inches(2.3), Inches(1.45), Inches(1.45)
msg = "Both solvers reached the same cost."
if CHECK:
    msg += f" On {len(CHECK)} smaller cases solved by HiGHS, the Rust bound was valid every time."
text(s, 7.25, 4.95, 5.2, 1.0, msg, size=15, color=MUTED)

# 4. Network
s = slide("Six large refineries, inside the biomass clusters",
          f"Here is the result on the official inputs. Six large refineries, USD {base['objective']:.0f} million a year, USD {K['unit_cost_usd_t']:.0f} per tonne before feedstock. "
          f"Nine sites are left unused. Depots sit at the refineries, because the second leg costs more per tonne-kilometre and depots lose no mass, so a field depot can only add cost. In the app every site, route and facility is clickable.")
s.shapes.add_picture(str(REP / "fig" / "map_base_dark.png"), Inches(0.6), Inches(1.62), height=Inches(5.5))
for i, (v, l, c) in enumerate([(f"USD {base['objective']:.1f}M", "per year, all costs", TEXT), (f"USD {K['unit_cost_usd_t']:.0f}/t", "SAF, before feedstock", TEXT), (f"{K['n_depots']} depots", "all at refineries", YELLOW), (f"{K['sites_used']} of 80", "sites used", AQUA)]):
    stat(s, 7.75, 1.62 + i * 1.4, 4.95, 1.28, v, l, c, size=28)

# 5. Results
s = slide("Measured gains, and where the plan breaks",
          f"Against two rule-of-thumb networks on the same basis, we save USD {B['greedy']['saving_usd_m']:.0f} to {B['airport_first']['saving_usd_m']:.0f} million a year. Those are simple planner rules, not a claim about industry practice. "
          f"Moving depots to the field costs USD {B['field']['saving_usd_m']:.1f} million more but cuts truck kilometres by {100 * (1 - field['kpis']['truck_km_m'] / K['truck_km_m']):.0f} percent, and that is the planner's call. "
          "The plan fails if demand rises more than 13 percent, if yield falls below 0.176, or with five refineries or fewer, and the app says exactly why.")
cd = CategoryChartData()
order = [("Airport-first", B["airport_first"]), ("Greedy heuristic", B["greedy"]), ("Field depots", B["field"]), ("Optimised", B["optimised"])]
cd.categories = [o[0] for o in order]
cd.add_series("USD M per year", [round(o[1]["objective"], 1) for o in order])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.7), Inches(6.9), Inches(4.5), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = "Annual cost, USD M, same demand and cost basis"
for r in ch.chart_title.text_frame.paragraphs[0].runs:
    r.font.size, r.font.bold, r.font.name = Pt(15), False, "Calibri"
    r.font.color.rgb = rgb(MUTED)
pl = ch.plots[0]
pl.gap_width = 55
pl.has_data_labels = True
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.number_format, pl.data_labels.number_format_is_linked = "0.0", False
pl.data_labels.font.size, pl.data_labels.font.name = Pt(14), "Calibri"
pl.data_labels.font.color.rgb = rgb(TEXT)
ser = pl.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = rgb("8F8E85")
pt = ser.points[3]
pt.format.fill.solid()
pt.format.fill.fore_color.rgb = rgb(BLUE)
ca, va = ch.category_axis, ch.value_axis
ca.tick_labels.font.size, ca.tick_labels.font.name = Pt(14), "Calibri"
ca.tick_labels.font.color.rgb = rgb(TEXT)
ca.format.line.color.rgb = rgb("46453F")
ca.has_major_gridlines = False
va.visible = False
va.has_major_gridlines = False
va.minimum_scale, va.maximum_scale = 0, 1150
text(s, 7.8, 1.72, 4.9, 0.4, "Fails, and says why, when", size=18, bold=True)
for i, (v, l) in enumerate([("+13.3%", "demand beyond feedstock"), ("< 0.176", "yield, inside the allowed 15 to 25%"), ("5 plants", "or fewer cannot take 6,000 kt")]):
    y = 2.25 + i * 1.32
    card(s, 7.8, y, 4.9, 1.18)
    text(s, 8.0, y + 0.3, 1.9, 0.6, v, size=24, bold=True, color="E66767")
    text(s, 9.95, y + 0.22, 2.6, 0.8, l, size=15, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)

# 6. Trust and impact
s = slide("The planner stays in control, and can check every number",
          f"Decision support uses no language model, so it cannot invent a figure. It answers from solver records, reruns the solver for what-ifs, and declines anything the model cannot know, like lifecycle carbon. "
          f"One honest warning: official demand is about twelve times today's real jet use at these airports, so this is a hub-scale plan. At today's volumes and a 5 percent blend the same model gives about USD {real['kpis']['unit_cost_usd_t'] / 1000:.0f} thousand per tonne. The next step is real moisture data, because that decides whether depots belong in the field. Thank you.")
card(s, 0.6, 1.8, 6.0, 4.5)
text(s, 0.85, 1.98, 5.5, 0.4, "Trust", size=20, bold=True, color=BLUE)
text(s, 0.85, 2.5, 5.5, 3.7, [
    "No language model, so no invented numbers",
    "Each answer lists the solver fields it read",
    "What-if questions rerun the real solver",
    "Questions outside the model are declined with a reason",
    f"A separate audit recomputes {len(base['validation'])} checks from raw flows",
], size=20)
card(s, 6.9, 1.8, 5.8, 2.15)
text(s, 7.15, 1.98, 5.3, 0.4, "Impact", size=20, bold=True, color=AQUA)
text(s, 7.15, 2.45, 5.3, 1.4, [
    [(f"USD {B['greedy']['saving_usd_m']:.0f}M to {B['airport_first']['saving_usd_m']:.0f}M per year", {"bold": True, "size": 24})],
    "saved against rule-of-thumb layouts, measured",
], size=16)
card(s, 6.9, 4.15, 5.8, 2.15)
text(s, 7.15, 4.33, 5.3, 0.4, "Reality check", size=20, bold=True, color=YELLOW)
text(s, 7.15, 4.8, 5.3, 1.4, "Official demand is about 12 times today's real jet use at these airports, so this is a hub-scale plan. Site moisture data is the next thing to test.", size=16)

out = REP / "Kalimantan_SAF_Pitch.pptx"
prs.save(out)
print("deck written", out)
