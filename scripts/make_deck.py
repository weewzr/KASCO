"""Build the KASCO pitch deck from the solver's result files.

    python scripts/make_deck.py

Screenshots come from scripts/capture_site.ps1. Authentic logos are used if they exist
in C:\\Hackathon\\Branding, otherwise organisation names appear as plain text.
"""
import io
import json
from pathlib import Path

import qrcode
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from pitch import SCRIPT, plain

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
REP = ROOT / "docs" / "reports"
BRAND = Path("C:/Hackathon/Branding")
PORTRAITS = [BRAND / "profile.jpg", Path.home() / "Downloads" / "Images" / "Wee Zhern Ray Portrait.png"]
LIVE = "https://weewzr.github.io/airbustrack3ray/"
LINKEDIN = "https://www.linkedin.com/in/wee-zhern-ray/"
PARTNERS = ["Acacia Hackathon Society", "NUS Product Club", "Airbus", "Five Degrees", "NUS Hackers", "National University of Singapore"]


def load(n):
    p = DATA / f"{n}.json"
    return json.loads(p.read_text()) if p.exists() else None


base, field = load("official_base"), load("field_depots")
B, H, CHECK, M = load("baselines"), load("highs_check"), load("bound_check"), load("marginal")
K, C = base["kpis"], base["costs"]
KM = B["kmeans"]
TK = 100 * (field["kpis"]["tonne_km_bn"] / K["tonne_km_bn"] - 1)
VK = 100 * (1 - field["kpis"]["truck_km_m"] / K["truck_km_m"])
step = next(r for r in M["rows"] if r["label"] == "Demand +105 kt")["delta"] - next(r for r in M["rows"] if r["label"] == "Demand +104 kt")["delta"]
capex_b = C["capex_total"] / 1000

NAVY, CARD, CARD2, TEXT, MUTED = "0A1626", "13283F", "1B3A52", "FFFFFF", "CFDBE3"
FOREST, TEAL, BLUE, ORANGE, YELLOW, AQUA = "1F7A4D", "19B5A5", "3987E5", "D95926", "C98500", "199E70"
rgb = RGBColor.from_string

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
TITLE_ONLY, BLANK = prs.slide_layouts[5], prs.slide_layouts[6]


def bg(s):
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(NAVY)


def slide(title, notes):
    s = prs.slides.add_slide(TITLE_ONLY)
    bg(s)
    t = s.shapes.title
    t.left, t.top, t.width, t.height = Inches(0.6), Inches(0.38), Inches(12.1), Inches(1.05)
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


def text(s, x, y, w, h, items, size=16, color=TEXT, bold=False, anchor=None, align=None, gap=7):
    b = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = b.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if anchor:
        tf.vertical_anchor = anchor
    items = items if isinstance(items, list) else [items]
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        if align:
            p.alignment = align
        for t, o in (it if isinstance(it, list) else [(it, {})]):
            r = p.add_run()
            r.text = t
            r.font.name = "Calibri"
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.color.rgb = rgb(o.get("color", color))
        p.space_after = Pt(gap)
    return b


def card(s, x, y, w, h, fill=CARD):
    r = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.adjustments[0] = 0.05
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(fill)
    r.line.fill.background()
    r.shadow.inherit = False
    return r


def stat(s, x, y, w, h, value, label, color=TEXT, size=30):
    card(s, x, y, w, h)
    text(s, x + 0.2, y + 0.13, w - 0.4, 0.7, value, size=size, bold=True, color=color)
    text(s, x + 0.2, y + h - 0.58, w - 0.4, 0.48, label, size=14, color=MUTED)


def chain(s, x, y, w, labels, colors, h=0.72, size=15):
    each = w / len(labels)
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
            r.font.size, r.font.bold, r.font.name = Pt(size), True, "Calibri"
            r.font.color.rgb = rgb("FFFFFF")


def source(s, t):
    text(s, 0.6, 6.92, 12.1, 0.35, t, size=11, color=MUTED)


# 1. Cover, in the style of the user's reference with real logos and the solved network
ART = REP / "fig" / "brand"
s = prs.slides.add_slide(BLANK)
bg(s)
s.shapes.add_picture(str(ART / "cover_bg.jpg"), 0, 0, width=prs.slide_width, height=prs.slide_height)


def logo(s, name, x, y, h):
    w, h_px = Image.open(ART / f"logo_{name}.png").size
    width = h * w / h_px
    s.shapes.add_picture(str(ART / f"logo_{name}.png"), Inches(x), Inches(y), height=Inches(h))
    return x + width


x = 0.42
groups = [("Organised by", [("acacia", 0.52), ("product_club", 0.52)]), ("Supported by", [("claude", 0.36)]), ("Powered by", [("airbus", 0.3), ("five_degrees", 0.3), ("nus_hackers", 0.5)])]
for label, items in groups:
    text(s, x, 0.1, 3, 0.2, label, size=10, color=MUTED)
    for name, h in items:
        x = logo(s, name, x, 0.36 + (0.52 - h) / 2, h) + 0.24
    x += 0.2
text(s, x, 0.1, 2, 0.2, "Hosted at", size=10, color=MUTED)
text(s, x, 0.34, 13.2 - x, 0.56, ["National University", "of Singapore"], size=13, bold=True, gap=0)

text(s, 0.55, 1.2, 8, 0.32, "A U T O N O M O U S   S G   H A C K A T H O N   2 0 2 6", size=15, bold=True)
text(s, 0.55, 1.53, 8, 0.28, "AI & AEROSPACE TRACK   |   AIRBUS CHALLENGE #3", size=12, color=MUTED)
s.shapes.add_picture(str(ART / "wordmark.png"), Inches(0.5), Inches(1.9), height=Inches(1.5))
text(s, 0.55, 3.42, 8, 0.55, "Kalimantan SAF Supply Chain Optimiser", size=30, bold=True)
text(s, 0.55, 3.98, 7.2, 0.4, "AI-Driven Optimisation for a More Sustainable Aviation Future", size=17, color=MUTED)

labels = ["LOCAL BIOMASS", "OPTIMAL FACILITIES", "EFFICIENT LOGISTICS", "SUSTAINABLE AVIATION"]
for i, l in enumerate(labels):
    cx = 1.05 + i * 1.82
    s.shapes.add_picture(str(ART / f"flow_{i}.png"), Inches(cx - 0.42), Inches(4.5), height=Inches(0.84))
    text(s, cx - 0.82, 5.38, 1.64, 0.5, l, size=11, bold=True, align=PP_ALIGN.CENTER, gap=0)
    if i < 3:
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(cx + 0.58), Inches(4.83), Inches(0.62), Inches(0.18))
        a.fill.solid()
        a.fill.fore_color.rgb = rgb(TEAL)
        a.line.fill.background()
        a.shadow.inherit = False

m = card(s, 8.15, 3.95, 4.8, 2.25)
m.fill.fore_color.rgb = rgb("%02X%02X%02X" % Image.open(REP / "fig" / "map_clean_dark.png").convert("RGB").getpixel((3, 3)))
s.shapes.add_picture(str(REP / "fig" / "map_clean_dark.png"), Inches(8.2), Inches(4.0), height=Inches(2.15))
text(s, 10.55, 4.12, 2.3, 0.3, "Solved base case", size=12, bold=True, color=TEAL)
text(s, 10.55, 4.46, 2.3, 1.6, ["Pontianak (PNK)", "Pangkalan Bun (PKN)", "Balikpapan (BPN)", "Tarakan (TRK)"], size=13, gap=5)

band = card(s, 0.35, 6.3, 12.63, 0.86)
band.fill.fore_color.rgb = rgb(NAVY)
cells = [(f"{K['n_refineries']} refineries", f"{K['n_depots']} depot modules"), ("1,200 kt SAF", "demand met at four airports"), (f"USD {base['objective']:.1f}M a year", "modelled network cost"), ("Wee Zhern Ray", "Presenter")]
for i, (a, b_) in enumerate(cells):
    x = 0.55 + i * 3.13
    s.shapes.add_picture(str(ART / f"band_{i}.png"), Inches(x), Inches(6.45), height=Inches(0.56))
    text(s, x + 0.68, 6.4, 2.4, 0.34, a, size=16, bold=True)
    text(s, x + 0.68, 6.72, 2.4, 0.3, b_, size=12, color=MUTED)
text(s, 0.4, 7.2, 12.6, 0.22, "Illustrative background image, not a modelled location. Map shows KASCO's solved network. Logos from the event poster, shown for event context, with no endorsement implied.", size=9, color=MUTED)

# 2. Problem
s = slide("Scaling SAF is a siting problem as much as a fuel problem",
          f"Sustainable aviation fuel was only about 0.6 percent of jet fuel in 2025. In Kalimantan the challenge inputs give biomass spread over 80 sites and four airports needing 300 kilotonnes each. A large refinery costs USD 765 million, so a network planner must decide where capital goes before engineering starts. Airbus itself was reported studying biomass logistics and factory siting in Indonesia with IPB University.")
stat(s, 0.6, 1.7, 2.9, 1.5, "0.6%", "SAF share of jet fuel, 2025", TEAL)
stat(s, 3.65, 1.7, 2.9, 1.5, "80 sites", "6,800 kt biomass, challenge data", AQUA)
stat(s, 6.7, 1.7, 2.9, 1.5, "USD 765M", "one large refinery", ORANGE)
stat(s, 9.75, 1.7, 2.95, 1.5, "4 airports", "1,200 kt SAF demand", BLUE)
text(s, 0.6, 3.6, 12.1, 2.4, [
    [("Decarbonisation  ", {"bold": True, "color": TEAL}), ("Aviation needs far more SAF than it has today", {})],
    [("Dispersed feedstock  ", {"bold": True, "color": TEAL}), ("Biomass is scattered, and hauling it costs money", {})],
    [("Fixed capital  ", {"bold": True, "color": TEAL}), ("A plant locks in site, scale and routes for 20 years", {})],
    [("Real interest  ", {"bold": True, "color": TEAL}), ("Airbus and IPB University were reported studying Indonesian biomass logistics and factory siting", {})],
], size=20, gap=10)
source(s, "Sources: IATA, 9 Dec 2025; QC Intelligence and Biofuels Digest, Aug 2025 (secondary reports); Airbus official update, 31 Oct 2026.")

# 3. Solution
s = slide("KASCO turns one planning question into an audited network",
          "KASCO follows material from biomass to depots, refineries and airports. A Rust solver compiled to WebAssembly picks sites and sizes in the browser and routes flows exactly. Planners can change assumptions, rerun the solver, and get explanations drawn from solver records. The solver uses no language model, and every result passes an independent audit.")
chain(s, 0.6, 1.75, 12.1, ["Biomass", "Depots", "Refineries", "Airports"], [AQUA, YELLOW, ORANGE, BLUE], h=0.85, size=20)
items = [("Mathematical optimisation", "Rust solver with a proven lower bound"), ("Geospatial analysis", "Interactive map of every site and route"), ("Scenario simulation", "Change inputs and rerun the real solver"), ("Explainable decision support", "Answers from solver records, or a refusal")]
for i, (h, d) in enumerate(items):
    x = 0.6 + i * 3.07
    card(s, x, 3.0, 2.9, 2.6)
    text(s, x + 0.2, 3.2, 2.5, 1.0, h, size=21, bold=True, color=TEAL)
    text(s, x + 0.2, 4.3, 2.5, 1.2, d, size=17, color=MUTED)
text(s, 0.6, 5.95, 12.1, 0.5, "Runs in the browser from GitHub Pages with no server. The optional Claude Opus 5.5 analyst uses the viewer's own API key.", size=18, color=MUTED)

# 4. MVP
s = slide("A working prototype, live now",
          "This is a real screenshot of the working site, not a mock-up. You can click any site or route, switch scenarios, run the solver in the browser, and ask why a refinery was chosen. If a question is unclear or outside the model, it refuses rather than guesses.")
shot = REP / "fig" / "site_map.png"
s.shapes.add_picture(str(shot), Inches(0.6), Inches(1.5), width=Inches(8.3))
for i, t in enumerate(["Interactive map", "Facility selection", "Scenario controls", "Solver outputs", "Explainable answers"]):
    card(s, 9.15, 1.5 + i * 0.86, 3.55, 0.74)
    text(s, 9.35, 1.5 + i * 0.86, 3.2, 0.74, t, size=18, bold=True, anchor=MSO_ANCHOR.MIDDLE)
text(s, 9.15, 5.85, 3.6, 0.7, [[("weewzr.github.io/airbustrack3ray", {"bold": True, "color": TEAL})]], size=16).click_action.hyperlink.address = LIVE
source(s, "Genuine screenshot of the KASCO website, official base case.")

# 5. Impact
s = slide("Modelled impact on the official inputs",
          f"The base case costs USD {base['objective']:.0f} million a year with six large refineries and {K['n_depots']} depot modules, meeting all 1,200 kilotonnes. That is USD {B['greedy']['saving_usd_m']:.0f} to {B['airport_first']['saving_usd_m']:.0f} million a year below two simple heuristics. Honest caveat: a strong k-means benchmark given the same fleet reaches our network, so the real value is the proof, the fleet choice in each scenario, and the limits. "
          f"HiGHS, a separate solver, reached the same cost, and we prove the gap at {100 * base['gap']:.2f} percent on candidate sites.")
for i, (v, l, c) in enumerate([(f"USD {base['objective']:.1f}M", "annual cost, modelled", TEXT), (f"{K['n_refineries']} + {K['n_depots']}", "refineries + depot modules", TEAL), ("1,200 kt", "SAF demand met, 100%", BLUE), (f"{100 * base['gap']:.2f}%", "proven gap, candidate sites", AQUA)]):
    stat(s, 0.6, 1.6 + i * 1.25, 3.7, 1.13, v, l, c, size=26)
cd = CategoryChartData()
order = [("Airport-first heuristic", B["airport_first"]["objective"]), ("Greedy heuristic", B["greedy"]["objective"]), ("Field depots", B["field"]["objective"]), ("K-means, same fleet, median", KM["median"]), ("KASCO", B["optimised"]["objective"])]
cd.categories = [o[0] for o in order]
cd.add_series("USD M per year", [round(o[1], 1) for o in order])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(4.55), Inches(1.55), Inches(8.15), Inches(3.6), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = "Annual cost, USD M, same demand and cost basis"
for r in ch.chart_title.text_frame.paragraphs[0].runs:
    r.font.size, r.font.bold, r.font.name = Pt(15), False, "Calibri"
    r.font.color.rgb = rgb(MUTED)
pl = ch.plots[0]
pl.gap_width = 50
pl.has_data_labels = True
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.number_format, pl.data_labels.number_format_is_linked = "0.0", False
pl.data_labels.font.size, pl.data_labels.font.name = Pt(14), "Calibri"
pl.data_labels.font.color.rgb = rgb(TEXT)
ser = pl.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = rgb("6F8497")
pt = ser.points[len(order) - 1]
pt.format.fill.solid()
pt.format.fill.fore_color.rgb = rgb(TEAL)
ca, va = ch.category_axis, ch.value_axis
ca.tick_labels.font.size, ca.tick_labels.font.name = Pt(14), "Calibri"
ca.tick_labels.font.color.rgb = rgb(TEXT)
ca.format.line.color.rgb = rgb("27445F")
ca.has_major_gridlines = False
va.visible = False
va.has_major_gridlines = False
va.minimum_scale, va.maximum_scale = 0, 1200
text(s, 4.55, 5.25, 8.15, 1.3, [
    [(f"USD {B['greedy']['saving_usd_m']:.0f}M to {B['airport_first']['saving_usd_m']:.0f}M a year", {"bold": True, "color": TEAL}), (" below two simple heuristics, modelled", {})],
    [("Same cost from HiGHS", {"bold": True, "color": TEAL}), (f", {len(base['validation'])} of {len(base['validation'])} audit checks pass", {})],
    [("K-means given our fleet also reaches this network", {"bold": True, "color": TEAL}), (", so value lies in the proof and limits", {})],
], size=16, gap=4)

# 6. Relevance
s = slide("Real-world relevance, and its limits",
          f"Regional studies support residues as a SAF feedstock, and palm residues are named for Kalimantan. Indonesia's first mandate covers Jakarta and Bali departures only. Two honest limits: official demand is about twelve times today's real jet use here, so this is a hub-scale plan, and the 80 sites are modelling inputs. KASCO also exposes decision limits: past 1,304 kilotonnes a seventh plant is needed, and one more kilotonne adds about USD {step:.0f} million.")
card(s, 0.6, 1.65, 5.95, 4.95)
text(s, 0.85, 1.82, 5.5, 0.4, "Why it matters", size=21, bold=True, color=TEAL)
text(s, 0.85, 2.35, 5.45, 4.1, [
    "Southeast Asian feedstock could yield about 45.7 Mt of SAF a year by 2050",
    "Fischer-Tropsch ranks among the most viable routes for regional wastes",
    "Indonesia's 1% from 2027 covers Jakarta and Bali departures",
    f"Decision limit: past {6 * 1087 * 0.2:,.0f} kt of SAF, one more kt adds about USD {step:.0f}M a year",
], size=21, gap=13)
card(s, 6.75, 1.65, 5.95, 4.95)
text(s, 7.0, 1.82, 5.5, 0.4, "What we do not claim", size=21, bold=True, color=YELLOW)
text(s, 7.0, 2.35, 5.45, 4.1, [
    "Official demand is about 12 times today's estimated real jet use at these airports",
    "The 80 biomass points are modelling inputs, and 13 lie off the coast",
    "Sites are screened only: tenure, peat and forest status are unchecked",
    "Depot layout depends on zero mass loss, and real moisture could change it",
], size=21, gap=13)
source(s, "Sources: RSB and Boeing, Sep 2024; GHD ASEAN study; Fuels and Lubes, Jul 2026; KASCO reality-check scenarios. Full references in the technical report.")

# 7. About me
s = slide("About Me: Wee Zhern Ray",
          "I'm a third-year Chemical Engineering student at NUS, minoring in Hydrogen and Low Carbon Technologies, with a specialisation in safety and sustainability.")
portrait = next((p for p in PORTRAITS if p.exists()), None)
if portrait:
    im = Image.open(portrait).convert("RGBA")
    if portrait.suffix.lower() == ".png":
        W_, H_ = im.size
        im = im.crop((int(0.2 * W_), int(0.27 * H_), int(0.8 * W_), int(0.85 * H_)))
    back = Image.new("RGBA", im.size, (19, 40, 63, 255))
    back.alpha_composite(im)
    buf = io.BytesIO()
    back.convert("RGB").save(buf, "JPEG", quality=92)
    buf.seek(0)
    s.shapes.add_picture(buf, Inches(0.6), Inches(1.6), height=Inches(5.0))
text(s, 5.75, 1.75, 7, 0.7, "Wee Zhern Ray", size=38, bold=True)
text(s, 5.75, 2.6, 7, 2.2, [
    "Year 3 Chemical Engineering",
    "National University of Singapore",
    "Minor in Hydrogen and Low Carbon Technologies",
    "Specialisation in Safety and Sustainability",
], size=22, color=MUTED, gap=8)
box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(5.75), Inches(5.1), Inches(0.62), Inches(0.62))
box.adjustments[0] = 0.15
box.fill.solid()
box.fill.fore_color.rgb = rgb("0A66C2")
box.line.fill.background()
box.shadow.inherit = False
box.text_frame.text = "in"
box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
for r in box.text_frame.paragraphs[0].runs:
    r.font.size, r.font.bold, r.font.name = Pt(22), True, "Calibri"
    r.font.color.rgb = rgb("FFFFFF")
text(s, 6.55, 5.1, 4.4, 0.62, [[("linkedin.com/in/wee-zhern-ray", {"color": TEAL, "bold": True})]], size=19, anchor=MSO_ANCHOR.MIDDLE).click_action.hyperlink.address = LINKEDIN
qr = qrcode.QRCode(box_size=10, border=2)
qr.add_data(LINKEDIN)
qr.make(fit=True)
buf = io.BytesIO()
qr.make_image(fill_color="black", back_color="white").save(buf, "PNG")
buf.seek(0)
s.shapes.add_picture(buf, Inches(11.1), Inches(4.95), height=Inches(1.6))

# 8. Future
s = slide("From Hackathon MVP to Scalable SAF Decision Intelligence",
          "KASCO is a prototype today. Next would come a secure language-model layer, with the solver still in charge of every number. Then road, port and feedstock data, robust optimisation and stakeholder validation. Likely users would be SAF producers, airlines, fuel distributors, airports, consultancies and planning agencies. This is an industrial planning tool, so there is no consumer story here. Thank you.")
stages = [
    ("Stage 1", "Current MVP", ["Mathematical optimisation", "Interactive geospatial network", "Scenario simulation", "Explainable decision support"], FOREST),
    ("Stage 2", "AI enhancement", ["Secure hosted LLM access", "Natural-language scenarios", "Possible ML site shortlisting", "Evidence-grounded reports"], TEAL),
    ("Stage 3", "Real-world validation", ["Road and port data", "Industrial site screening", "Feedstock-quality variability", "Robust optimisation, stakeholders"], BLUE),
    ("Stage 4", "Commercial potential", ["Airlines, SAF producers", "Fuel distributors, airports", "Engineering consultancies", "Government planning agencies"], YELLOW),
]
for i, (a, b_, its, c) in enumerate(stages):
    x = 0.6 + i * 3.07
    card(s, x, 1.65, 2.9, 4.85)
    pill = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x + 0.2), Inches(1.85), Inches(1.15), Inches(0.42))
    pill.adjustments[0] = 0.5
    pill.fill.solid()
    pill.fill.fore_color.rgb = rgb(c)
    pill.line.fill.background()
    pill.shadow.inherit = False
    pill.text_frame.text = a
    pill.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    pill.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    for r in pill.text_frame.paragraphs[0].runs:
        r.font.size, r.font.bold, r.font.name = Pt(14), True, "Calibri"
        r.font.color.rgb = rgb("FFFFFF")
    text(s, x + 0.2, 2.42, 2.5, 0.85, b_, size=21, bold=True)
    text(s, x + 0.2, 3.35, 2.55, 3.0, its, size=16, color=MUTED, gap=9)
source(s, "Stages 2 to 4 are future possibilities, not established results or commercial achievements.")

for sl, (_, line) in zip(prs.slides, SCRIPT):
    sl.notes_slide.notes_text_frame.text = plain(line)

out = REP / "KASCO_Pitch.pptx"
prs.save(out)
print("deck written", out, "notes words", sum(len(x.notes_slide.notes_text_frame.text.split()) for x in prs.slides))
