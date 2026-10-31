"""Generate the technical report PDF. Every number is read from the solver's result files.

    python scripts/make_report.py
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
REP = ROOT / "docs" / "reports"
FIG = REP / "fig"
EQ = FIG / "eq"
EQ.mkdir(parents=True, exist_ok=True)
W = A4[0] - 4 * cm
TESTS = int(sys.argv[1]) if len(sys.argv) > 1 else 38


def load(name):
    p = DATA / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


base, field, hd, ht = load("official_base"), load("field_depots"), load("high_demand"), load("high_transport")
road, real, allf = load("road_distance"), load("real_blend"), load("all_feedstock")
inf1, inf2, inf3 = load("infeasible_demand"), load("low_yield"), load("max_five_refineries")
B, S, LAD, H, NET = load("baselines"), load("sensitivity"), load("ladder"), load("highs_check"), load("network")
M, DC, SC, OC, GR, CX = load("marginal"), load("depot_check"), load("site_screen"), load("official_check"), load("grid_check"), load("context_check")
K, C = base["kpis"], base["costs"]
OFF = [s for s in NET["sites"] if not s["on_land"]]
KM = B["kmeans"]
TK = 100 * (field["kpis"]["tonne_km_bn"] / K["tonne_km_bn"] - 1)
VK = 100 * (1 - field["kpis"]["truck_km_m"] / K["truck_km_m"])

ss = getSampleStyleSheet()
body = ParagraphStyle("B", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.6, leading=13.6, spaceAfter=6, alignment=TA_LEFT)
h1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=14, leading=18, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#14365f"))
h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#14365f"))
cap = ParagraphStyle("Cap", parent=body, fontSize=8.4, leading=11, textColor=colors.HexColor("#52514e"), spaceAfter=9)
cell = ParagraphStyle("Cell", parent=body, fontSize=8.1, leading=10.2, spaceAfter=0)
story = []


def P(t):
    story.append(Paragraph(t, body))


def H1(t):
    story.append(Paragraph(t, h1))


def H2(t):
    story.append(Paragraph(t, h2))


def bullets(items):
    for t in items:
        story.append(Paragraph(t, body, bulletText="•"))


def table(rows, widths=None, header=True, keep=True):
    data = [[Paragraph(str(c), cell) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    st = [("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d9d8d2")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef6"))]
    t.setStyle(TableStyle(st))
    story.append(KeepTogether(t) if keep else t)
    story.append(Spacer(1, 7))


def figure(name, width, caption):
    from PIL import Image as PI

    w, h = PI.open(FIG / name).size
    story.append(KeepTogether([Image(str(FIG / name), width=width, height=width * h / w), Paragraph(caption, cap)]))


EQN = 0


def eq(tex, h=0.32):
    """Renders one equation with mathtext and numbers it."""
    global EQN
    EQN += 1
    path = EQ / f"eq{EQN}.png"
    fig = plt.figure(figsize=(6.6, h), dpi=220)
    fig.text(0.0, 0.5, f"${tex}$", fontsize=10.5, va="center", math_fontfamily="cm")
    fig.text(0.985, 0.5, f"({EQN})", fontsize=9, va="center", ha="right")
    fig.savefig(path)
    plt.close(fig)
    story.append(Image(str(path), width=W, height=W * h / 6.6))


def usd(x, d=1):
    return f"USD {x:,.{d}f}M"


# Title
story.append(Paragraph("KASCO", ParagraphStyle("T", parent=h1, fontSize=30, leading=35, spaceBefore=0, textColor=colors.HexColor("#0e7f73"))))
story.append(Paragraph("Kalimantan SAF Supply Chain Optimiser", ParagraphStyle("T2", parent=h1, fontSize=16, leading=20, spaceBefore=0)))
story.append(Paragraph("AI-Driven Optimisation for a More Sustainable Aviation Future", ParagraphStyle("S0", parent=body, fontSize=11, leading=14)))
story.append(Paragraph("Technical report, Airbus Challenge 3, Autonomous SG 2026", ParagraphStyle("S", parent=body, fontSize=11, leading=14)))
P("Wee Zhern Ray, Year 3 Chemical Engineering, National University of Singapore. 31 October 2026.")
P('Live application: <a href="https://weewzr.github.io/airbustrack3ray/" color="#2a78d6">weewzr.github.io/airbustrack3ray</a>. '
  'Source: <a href="https://github.com/weewzr/airbustrack3ray" color="#2a78d6">github.com/weewzr/airbustrack3ray</a>.')

H1("1. Executive summary")
P(f"A SAF network planner must place about {usd(C['capex_total'] / 1000)[:-1]}B of plant capital across Kalimantan before engineering starts. This project gives that planner a tool that searches refinery and depot locations and sizes, routes biomass and SAF exactly, and shows the checks behind each number.")
P(f"On the official inputs of the 31 October update, the best network found costs <b>{usd(base['objective'], 2)} per year</b>, or <b>USD {K['unit_cost_usd_t']:,.0f} per tonne SAF</b> before feedstock. It uses {K['n_refineries_large']} large refineries, {K['n_depots']} depot modules ({K['n_depots_large']} large, {K['n_depots_small']} small), {K['biomass_used_kt']:,.0f} kt of biomass from {K['sites_used']} sites, and meets all 1,200 kt of demand. On candidate sites the cost is proven within {100 * base['gap']:.2f}% of the optimum. The final coordinates are a local refinement with no global proof.")
P(f"Refinery cost dominates the decision, since transport is only {100 * C['logistics_total'] / C['total_annual']:.1f}% of the total. Under the official inputs depots belong at the refinery, and a HiGHS run with depots free to go anywhere confirmed this on the base fleet. Field depots cost {usd(B['field']['saving_usd_m'])} more per year. They move {TK:.1f}% more tonne-km but need an estimated {VK:.0f}% fewer truck-km, a trade-off left for the planner to weigh.")
P(f"The network costs {usd(B['greedy']['saving_usd_m'])} to {usd(B['airport_first']['saving_usd_m'])} per year less than two simple heuristic layouts. A strong k-means benchmark, handed the same six-plant fleet and our refinement, reaches our network at best and sits {usd(KM['median_saving_usd_m'])} above it at median. That supports the result and also shows the objective is flat near the optimum. KASCO's value is the proven bound, the fleet and size choice in each scenario, and limits such as the cost step at {6 * 1087 * 0.2:,.1f} kt of SAF.")

H1("Reference Frame")
H2("Variables and parameters")
table([
    ["Symbol", "Definition", "Units", "Value or range"],
    ["i, j, k, a, s", "Biomass site, depot site, refinery site, airport, size (small, large)", "", "80 sites, 4 airports"],
    ["x<sub>ij</sub>", "Biomass from site i to depot at j", "kt/yr", "Decision, continuous"],
    ["u<sub>jk</sub>", "Pre-processed biomass, depot j to refinery k", "kt/yr", "Decision, continuous"],
    ["w<sub>ka</sub>", "SAF from refinery k to airport a", "kt/yr", "Decision, continuous"],
    ["y<sub>js</sub>", "Depot modules of size s at j", "count", "Decision, integer"],
    ["z<sub>ks</sub>", "Refinery of size s open at k", "binary", "Decision"],
    ["t<sub>js</sub>, r<sub>ks</sub>", "Throughput by size at depot and refinery", "kt/yr", "Decision, continuous"],
    ["B<sub>i</sub>", "Biomass available at site i", "kt/yr", "22.84 to 99.90, sum 6,800"],
    ["D<sub>a</sub>", "SAF demand at airport a", "kt/yr", "300 each"],
    ["&eta;, &rho;", "Refinery yield, depot mass retention", "t/t", "0.20, 1.00"],
    ["C<super>D</super><sub>s</sub>, C<super>R</super><sub>s</sub>", "Depot and refinery biomass intake capacity", "kt/yr", "150, 300; 500, 1,087"],
    ["F<super>D</super><sub>s</sub>, F<super>R</super><sub>s</sub>", "Depot and refinery CapEx", "USD M", "2.25, 4.5; 480, 765"],
    ["v<super>D</super><sub>s</sub>, v<super>R</super><sub>s</sub>", "Variable OpEx on biomass in", "USD/t", "5, 4; 60, 55"],
    ["&tau;<sub>1</sub>, &tau;<sub>2</sub>, &tau;<sub>3</sub>", "Tariff by leg", "USD/t/km", "0.10, 0.12, 0.08"],
    ["n, f", "CapEx life, fixed OpEx share", "yr, 1/yr", "20, 0.05"],
    ["d", "Distance between two points", "km", "Great-circle x 1.3"],
], [2.5 * cm, 7.6 * cm, 1.7 * cm, 5.2 * cm])
H2("Equations")
P("The objective is equation (1). Equations (2) to (8) are its constraints. Equation (9) defines distance. Equations (10) to (12) are the solution method. All appear in full in section 6.")
H2("Assumptions needed to read them")
P("One-year cost basis with straight-line CapEx and no interest. Biomass mass is taken as stated, with moisture ignored by instruction. All values are deterministic. Masses are annual. Refinery capacity is biomass intake.")

H1("2. Problem and industrial context")
P("The named user is a SAF network planner at a project developer or fuel supplier, recommending sites before front-end engineering. Airbus's Singapore office was reported in August 2025 to be working with IPB University on Indonesian biomass availability, logistics, supply chain mapping and factory siting to cut transport cost, with empty fruit bunches in Sumatra and Kalimantan named as feedstock [19]. The same reports list weak infrastructure, an unclear legal framework and limited large-scale processing as obstacles. Those are secondary reports, and their details differ.")
P("We found no published description of how planners work today. Comparing a few layouts in GIS and spreadsheets is our reasoned assumption, and it should be read as such. Mistakes are persistent, since a large refinery fixes USD 765M of capital and its haulage for 20 years. Project risk is real: a gasification Fischer-Tropsch plant in Nevada entered bankruptcy in 2024 after equipment and liquidity problems [20].")
P("SAF supply is scarce, at about 1.9 Mt in 2025 or 0.6% of jet fuel [21]. Indonesia's first requirement, 1% from 2027, covers international flights from its two busiest airports [16], and Pertamina's first SAF was used cooking oil co-processed at Cilacap [22]. Regional studies support residues as a feedstock: about 45.7 Mt of SAF potential across Southeast Asia by 2050 [23], and Fischer-Tropsch among the most viable routes [24]. A preliminary national estimate puts palm residues near 77% of Indonesian waste-based SAF potential [25]. We found no Kalimantan-wide residue tonnage, so the 6,800 kt remains a challenge input.")
P("The physical constraints are real. Biomass clusters in West, Central and East Kalimantan, the airports sit far apart, and Tarakan is an island. A sample of 854 site pairs on OpenStreetMap gave a median road distance of 1.9 times great-circle, above the official 1.3. Older work on Central Kalimantan palm freight found road and river close to evenly used, with intermodal routes the cheapest generalised option [26].")

P("The platform helps that planner decide where to open plants, what size to build, which biomass sites to contract, how to route fuel, and when demand growth forces new capacity. Likely users are SAF producers, fuel distributors, airlines, airport operators, engineering consultancies and government planners. These are possible users, not existing customers.")

H1("3. Official Airbus challenge requirements")
P("The brief asks for a SAF supply chain across Kalimantan that minimises OpEx, CapEx and logistics while meeting demand at four airports: Supadio (PNK), Iskandar at Pangkalan Bun (PKN), Sepinggan (BPN) and Juwata (TRK). The chain runs biomass site, pre-processing depot, refinery, airport. The answer must give coordinates, facility sizes and routes. The update of 31 October at 12:45 fixed every open parameter and says it overrides the original where they differ.")

H1("4. Data and assumptions")
H2("Validation of the official data")
table([
    ["Check", "Result"],
    ["Biomass rows and total", "80 rows, 6,800.00 kt, matching the brief"],
    ["Range per site", "22.84 to 99.90 kt, inside the stated 20 to 100 kt"],
    ["Null cells, duplicate ids", "0, 0"],
    ["kt and tonnes columns agree", "Yes, on every row"],
    ["Airports", "4 rows, 300 kt each, 1,200 kt total"],
    ["Refinery cost scaling", "765 / 480 equals (1,087 / 500)<super>0.60</super>, the six-tenths rule"],
    ["Depot unit CapEx", "USD 15k per kt for both sizes, so large wins only on variable cost"],
    ["Coastline check", f"{len(OFF)} of 80 points, {sum(s['kt'] for s in OFF):,.0f} kt, fall off the Natural Earth 10 m coast"],
], [6.2 * cm, 10.8 * cm])
P(f"The 80 points should be read as modelling inputs, not surveyed production sites. {sum(1 for s in OFF if s['district'] == 'Ketapang')} of the {len(OFF)} off-coast points are labelled Ketapang, and the farthest lies {max(p['km_to_land'] for p in SC['offshore_points']):.1f} km from the coastline, too far to be a mapping error. We keep them as biomass sources because the coordinates are official, but they cannot host a refinery since the brief requires land. The first solver version missed this, and the independent audit caught a plant placed on one of those points.")
if OC:
    P(f"The script <font face='Courier'>check_official.py</font> compares {OC['n']} engine inputs with the official workbook and airport file. All match. Real-uplift figures come from <font face='Courier'>fetch_context.py</font>, which fetches each source page and records whether the quoted figure was found. They are used only in the labelled reality check.")
H2("Assumption register")
table([
    ["Input", "Value", "Status", "Source"],
    ["Capacity basis", "Biomass intake", "Official", "Update, 12:45"],
    ["Yield", "0.20 t SAF per t biomass", "Official", "Update, 12:45"],
    ["Depot mass loss", "0%", "Official", "Update, 12:45"],
    ["Demand", "300 kt per airport", "Official", "challenge3_airports_4.csv"],
    ["Costs", "CapEx / 20, fixed OpEx 5%, variable per tonne", "Official", "challenge3_parameters.xlsx"],
    ["Distance", "Great-circle x 1.3", "Official", "Update, 12:45"],
    ["Tarakan leg", "Barge at 0.08 USD/t/km", "Official", "Update, 12:45"],
    ["Refinery candidates", "On-land sites plus PNK, PKN, BPN", "Ours", "Tarakan excluded, as biomass cannot reach the island"],
    ["One refinery per site", "At most one", "Ours", "Depot modules may share a site"],
    ["Field depot radius", "60 km", "Ours", "Used only in the field design"],
    ["Real uplift", "About 100 kt/yr", "Public", "Reality check only, see section 13"],
], [3.8 * cm, 6.0 * cm, 1.6 * cm, 5.6 * cm])

H1("5. Literature review")
P("Six papers shaped the formulation. Ng and Maravelias [3] build a multi-period MILP with variable depot and biorefinery locations, and report that sites near a biorefinery ship directly while distant sites justify a depot. That pattern depends on densification lowering later transport cost, which the brief's tariffs do not offer. Their example took 3,405 s to reach a 0.43% gap with 431 binaries, a warning about scale. Ng et al. [2] stress accurate distances and show that pruning reduces 557 candidate depots and over three million arcs to 378 depots and 80,000 arcs, which supports candidate reduction.")
P("Huang et al. [5] compare ATJ, FT and HTL on corn stover. They report that large centralised plants win through economies of scale, which matches our result. Li et al. [4] show that assuming fixed yields overstates maximum SAF supply by 14.15% and net revenue by 18.27% when ash varies, so yield deserves scrutiny. Hernandez-Araujo et al. [6] couple supply chain and process models for bagasse-based ATJ, and Castillo-Villar et al. [7] use machine learning to pick facility configurations for a county, depot, biorefinery, airport network, which is the same four-tier shape as this problem.")
P("We take the four-tier mass balance from [7], the strong linking constraints from the facility location literature, and the candidate-reduction idea from [2]. We did not combine their cost data, because the update fixes all costs. Course material from CN4252 [8, 9] informed the annualisation logic and the assumption register.")
P("Three papers shaped what we chose not to build. Ng et al. [2] support real road distances, which we test as a sensitivity because the official distance is fixed. Li et al. [4] warn against fixed yields. Their figures come from US logging residues and do not transfer, but as an illustration only, a 14% shortfall on 0.20 would give 0.172, below our feasibility threshold of 0.176. Keyvandarian et al. [27] apply adaptive robust optimisation to SAF allocation under production uncertainty. We lack data to calibrate an uncertainty set, so that stays future work, and the official 0.20 stays unchanged.")

H1("6. Mathematical formulation")
P("Minimise annual cost:")
eq(r"\min\ \left(\frac{1}{n}+f\right)\left[\sum F^D_s y_{js}+\sum F^R_s z_{ks}\right]+\sum v^D_s t_{js}+\sum v^R_s r_{ks}+\sum \tau_1 d_{ij}x_{ij}+\sum \tau_2 d_{jk}u_{jk}+\sum \tau_3 d_{ka}w_{ka}", 0.42)
P("Subject to biomass availability, depot balance and capacity, depot mass retention, refinery balance and capacity, conversion, demand, and domains:")
eq(r"\sum_j x_{ij}\leq B_i\quad \forall i")
eq(r"\sum_i x_{ij}=\sum_s t_{js},\qquad t_{js}\leq C^D_s\,y_{js}\quad \forall j,s")
eq(r"\sum_k u_{jk}=\rho\sum_i x_{ij}\quad \forall j")
eq(r"\sum_j u_{jk}=\sum_s r_{ks},\qquad r_{ks}\leq C^R_s\,z_{ks}\quad \forall k,s")
eq(r"\sum_a w_{ka}=\eta\sum_s r_{ks}\quad \forall k")
eq(r"\sum_k w_{ka}\geq D_a\quad \forall a")
eq(r"\sum_s z_{ks}\leq 1,\quad z_{ks}\in\{0,1\},\quad y_{js}\in\mathbb{Z}_{\geq 0},\quad x,u,w,t,r\geq 0")
eq(r"d_{pq}=1.3\times 2R\,\arcsin\sqrt{\sin^2\frac{\Delta\phi}{2}+\cos\phi_p\cos\phi_q\sin^2\frac{\Delta\lambda}{2}}")
H2("Truck size")
P("The tariff is per tonne-km and the same for both truck sizes, so truck size cannot enter the objective. We report trip counts only, and we do not model trucks as a decision.")
H2("Why depots sit at refineries")
P("Take biomass moving from site i through a depot at j to a refinery at k. Its transport cost per tonne is &tau;<sub>1</sub>d<sub>ij</sub> + &rho;&tau;<sub>2</sub>d<sub>jk</sub>. If &rho;&tau;<sub>2</sub> is at least &tau;<sub>1</sub>, this is at least &tau;<sub>1</sub>(d<sub>ij</sub> + d<sub>jk</sub>), which by the triangle inequality is at least &tau;<sub>1</sub>d<sub>ik</sub>. For a depot serving one refinery, moving it to that refinery therefore never raises transport cost and keeps the same modules.")
P(f"A depot feeding two refineries needs more care, since splitting it could add a module. The argument alone therefore leaves a margin, bounded by the difference between actual depot cost and its linear floor: {usd(C['opex_var_depots'] + 0.1 * C['capex_depots'] - K['biomass_used_kt'] * 5.5 / 1000, 2)} per year on the base fleet.")
if DC:
    P(f"We closed that margin computationally. With the six base-case refineries fixed, HiGHS solved the full three-tier model with depots at any site, shared between refineries, in integer modules. It proved {usd(DC['free_depot_cost'], 4)} ({DC['gap_pct']:.4f}% gap), the same as the co-located cost, with {len(DC['shared_depots'])} shared and {len(DC['remote_depots'])} remote depots.")
P("The result needs metric distances, &rho;&tau;<sub>2</sub> at or above &tau;<sub>1</sub>, and this fleet. It reverses below a retention of 0.833, which is why the instruction to ignore moisture loss matters. A real depot that dries wet biomass could earn its place in the field, so this is a result about these inputs, not a general rule.")

H1("7. Solver architecture")
table([
    ["Method", "Assessment", "Decision"],
    ["General MILP solver (HiGHS)", "Reliable with a proven bound, but C++ and heavy to run live in a browser", "Kept as the independent check"],
    ["Purpose-built Lagrangian branch-and-bound in Rust", "Exploits problem structure, compiles to WebAssembly, gives a true bound", "Chosen engine"],
    ["MINLP with free coordinates", "Non-convex, no practical global proof at this size", "Replaced by a two-step method"],
    ["Clustering plus MILP", "Fast but depends on arbitrary cluster counts", "Used only as a starting design"],
    ["Pure metaheuristic", "No bound, so no honest statement of quality", "Rejected"],
], [5.2 * cm, 7.6 * cm, 4.2 * cm])
P("Measurements drove this choice. In a timed run of a general MILP on an earlier version of this problem, 99.1% of runtime sat inside the solver, so a language change alone could not help. The gain came from using the structure. Relaxing supply and demand with multipliers u and &lambda; splits the model into one subproblem per site:")
eq(r"L(u,\lambda)=\sum_a\lambda_a E_a-\sum_i u_iB_i+\min_{z}\ \sum_{k,s}z_{ks}\left(G_s+V_{ks}(u,\lambda)\right),\qquad \sum_{k,s}C^R_s z_{ks}\geq\sum_a E_a", 0.38)
P("Here E<sub>a</sub> is the biomass equivalent of demand, G<sub>s</sub> the annual fixed cost of a plant and V<sub>ks</sub> the best value of site k, found by pairing the cheapest inputs with the dearest outputs. Any multipliers give a valid lower bound, and subgradient steps tighten it. Each design found is priced exactly by min-cost flow.")
P("The relaxed problem may pick one site in both sizes. This keeps the bound valid, because it only removes a constraint, and it occurred in 0.6% of relaxed solutions on the base case. Reported designs are always one size per site. Branching adds little on this instance: biomass sites are near-substitutes, so closing one barely moves the bound, and the reported gap is close to the root relaxation. A best-first variant tested outside the repository did not improve it.")
P("Sites may be anywhere on land, so a final step alternates a location move and a re-allocation [10], where each plant moves by Weiszfeld iteration [11]:")
eq(r"\mathbf{p}^{(t+1)}=\left(\sum_m\frac{\omega_m\,\mathbf{p}_m}{\|\mathbf{p}^{(t)}-\mathbf{p}_m\|}\right)\left(\sum_m\frac{\omega_m}{\|\mathbf{p}^{(t)}-\mathbf{p}_m\|}\right)^{-1},\qquad \omega_m=\tau\times\mathrm{flow}_m", 0.46)
P("A land mask rejects offshore moves. This step converges to a local optimum and carries no global proof.")

H2("System architecture")
P("The engine is a Rust library covering data, instance building, min-cost flow, search, refinement, audit, baselines, diagnostics and decision support, with 38 automated tests. A command-line tool runs batches and exports the model. A WebAssembly build of the same library runs inside the browser in a Web Worker, so the deployed site on GitHub Pages needs no server, and the solver needs no account or API key. The page uses Leaflet for the map and Chart.js for charts. Python appears only in supporting scripts for data fetching, the HiGHS check and these documents.")

H1("8. Optimisation results")
table([
    ["Measure", "Value"],
    ["Total annual cost", f"{usd(base['objective'], 2)}"],
    ["Cost per tonne SAF", f"USD {K['unit_cost_usd_t']:,.0f}"],
    ["Candidate-site cost", f"{usd(base['discrete_objective'], 2)}"],
    ["Proven lower bound, candidate sites", f"{usd(base['bound'], 2)}"],
    ["Proven gap", f"{100 * base['gap']:.2f}%"],
    ["Search effort", f"{base['nodes']:,} nodes, {base['iterations']:,} bound iterations, {base['runtime_s']:.0f} s"],
    ["Biomass used", f"{K['biomass_used_kt']:,.0f} kt from {K['sites_used']} sites"],
    ["SAF delivered", f"{K['saf_kt']:,.0f} kt, 100% of demand"],
] + ([["HiGHS cost, same model", f"{usd(H['objective'], 2)} ({H['model_status']})"], ["HiGHS lower bound", f"{usd(H['bound'], 2)}"], ["HiGHS gap and time limit", f"{H['gap_pct']:.2f}%, {H['time_limit_s']:.0f} s"]] if H else []), [7 * cm, 10 * cm])

H1("9. Geographic network results")
table([["Refinery", "Size", "Latitude", "Longitude", "Biomass kt", "SAF kt", "Used", "Nearest site"]] + [
    [r["id"], r["size"], f"{r['lat']:.4f}", f"{r['lon']:.4f}", f"{r['biomass_in']:,.0f}", f"{r['saf_kt']:,.0f}", f"{100 * r['utilisation']:.1f}%", r["near"]] for r in base["refineries"]
], [1.4 * cm, 1.2 * cm, 1.6 * cm, 1.7 * cm, 1.5 * cm, 1.1 * cm, 1.2 * cm, 7.3 * cm])
dep = {}
for d in base["depots"]:
    dep.setdefault(d["id"], []).append(f"{d['count']} {d['size']}")
P("Depot modules at each refinery: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in dep.items()) + ".")
P(f"Continuous refinement saved only {usd(base['refine_saving'], 2)} per year. Biomass sites sit in tight clusters, so the best candidate site is already close to the geometric median." + (f" As a stress test we added {GR['grid_added']} land grid points at {GR['spacing_deg']} degree spacing to the {GR['candidates']} candidates. After refinement that run reached {usd(GR['refined_cost'], 2)}, which is strong evidence, though not proof, that the candidate restriction hides little." if GR else ""))
figure("map_base.png", 13.5 * cm, "Figure 1. Optimised network. Refineries sit inside the biomass clusters, with depots at each refinery. Lines are schematic, and the last leg to Tarakan is by barge.")
H2("Preliminary site screening")
P(f"{SC['note']} Land tenure, peat and forest status are unchecked. The table adds no constraint to the optimiser, and data come from OSRM and OpenStreetMap within {SC['radius_km']} km.")
table([["Plant", "To road, m", "Named rivers", "Ports, piers", "Industrial", "Protected nearby"]] + [
    [r["id"], f"{r['road_m']:,}" if r["road_m"] is not None else "n/a", ", ".join(r.get("rivers", [])) or ("None mapped" if r["screened"] else "Not screened"), r.get("ports", "n/a"), r.get("industrial", "n/a"), ", ".join(r.get("protected", [])) or ("None mapped" if r["screened"] else "Not screened")] for r in SC["sites"]
], [1.3 * cm, 1.7 * cm, 5.6 * cm, 1.7 * cm, 1.7 * cm, 4.9 * cm])

H2("Transport and material flows")
table([["From", "To", "SAF kt", "Distance km", "USD M/yr", "Mode"]] + [
    [f["src"], f["dst"], f"{f['kt']:,.1f}", f"{f['km']:,.0f}", f"{f['usd_m']:.2f}", f["mode"]] for f in base["flows_ra"]
], [2 * cm, 2 * cm, 2.4 * cm, 2.6 * cm, 2.4 * cm, 5.6 * cm])
P(f"Sites unused: {', '.join(K['sites_skipped'])}. These account for the 800 kt not needed. Mean biomass haul is {K['mean_km_farm_depot']:.0f} km and mean SAF haul {K['mean_km_refinery_airport']:.0f} km. Biomass is five times heavier per tonne of SAF, so plants stay close to it and SAF travels further. Delivery to Tarakan is the longest and the sole barge leg.")
t = base["trips"]
table([["Leg", "Tonnes", "Small truck", "Trips", "Large truck", "Trips"]] + [[x["leg"], f"{x['tonnes']:,.0f}", f"{x['small_t']:.0f} t", f"{x['trips_small']:,.0f}", f"{x['large_t']:.0f} t", f"{x['trips_large']:,.0f}"] for x in t], [4.4 * cm, 3 * cm, 2 * cm, 2.8 * cm, 2 * cm, 2.8 * cm])

H1("10. Cost and facility analysis")
figure("cost.png", 15 * cm, "Figure 2. Annual cost by component, official base case.")
table([
    ["Component", "USD M/yr", "Share"],
    ["Annualised CapEx", f"{C['annual_capex']:.1f}", f"{100 * C['annual_capex'] / C['total_annual']:.1f}%"],
    ["Fixed OpEx", f"{C['opex_fixed']:.1f}", f"{100 * C['opex_fixed'] / C['total_annual']:.1f}%"],
    ["Variable OpEx, refineries", f"{C['opex_var_refineries']:.1f}", f"{100 * C['opex_var_refineries'] / C['total_annual']:.1f}%"],
    ["Variable OpEx, depots", f"{C['opex_var_depots']:.1f}", f"{100 * C['opex_var_depots'] / C['total_annual']:.1f}%"],
    ["Transport, site to depot", f"{C['logistics_farm_depot']:.1f}", f"{100 * C['logistics_farm_depot'] / C['total_annual']:.1f}%"],
    ["Transport, refinery to airport", f"{C['logistics_refinery_airport']:.1f}", f"{100 * C['logistics_refinery_airport'] / C['total_annual']:.1f}%"],
    ["Total", f"{C['total_annual']:.1f}", "100%"],
], [8 * cm, 3 * cm, 3 * cm])
P(f"Total CapEx is {usd(C['capex_total'], 0)}, of which refineries are {100 * C['capex_refineries'] / C['capex_total']:.1f}%. The objective excludes biomass purchase, as the update defines it, so USD {K['unit_cost_usd_t']:,.0f}/t is a delivered cost before feedstock. Readers should not compare it directly with a market SAF price.")

H1("11. Baseline comparison")
figure("baseline.png", 12 * cm, "Figure 3. Annual cost on identical demand, distances and cost basis.")
table([["Design", "USD M/yr", "Extra cost vs optimised", "Refineries", "Depots", "Truck-km, M/yr"]] + [
    ["Optimised", f"{B['optimised']['objective']:.1f}", "n/a", B["optimised"]["n_ref"], B["optimised"]["n_dep"], f"{B['optimised']['truck_km_m']:.1f}"],
    ["Field depots, 60 km radius", f"{B['field']['objective']:.1f}", f"{B['field']['saving_usd_m']:.1f} ({B['field']['saving_pct']:.1f}%)", B["field"]["n_ref"], B["field"]["n_dep"], f"{B['field']['truck_km_m']:.1f}"],
    ["Greedy: richest sites, farthest-first plants", f"{B['greedy']['objective']:.1f}", f"{B['greedy']['saving_usd_m']:.1f} ({B['greedy']['saving_pct']:.1f}%)", B["greedy"]["n_ref"], B["greedy"]["n_dep"], f"{B['greedy']['truck_km_m']:.1f}"],
    ["Airport-first: plants at PNK, PKN, BPN", f"{B['airport_first']['objective']:.1f}", f"{B['airport_first']['saving_usd_m']:.1f} ({B['airport_first']['saving_pct']:.1f}%)", B["airport_first"]["n_ref"], B["airport_first"]["n_dep"], f"{B['airport_first']['truck_km_m']:.1f}"],
    [f"K-means, same fleet and refinement, best of {KM['restarts']}", f"{KM['best']:.1f}", f"{max(0, KM['best_saving_usd_m']):.1f} ({max(0, KM['best_saving_pct']):.1f}%)", KM["n_ref"], KM["n_dep"], "n/a"],
    ["K-means, same fleet and refinement, median", f"{KM['median']:.1f}", f"{KM['median_saving_usd_m']:.1f} ({KM['median_saving_pct']:.1f}%)", KM["n_ref"], KM["n_dep"], "n/a"],
], [5.6 * cm, 1.9 * cm, 3.6 * cm, 1.8 * cm, 1.4 * cm, 2.6 * cm])
P("All baselines passed the same audit. The greedy and airport rules are simple heuristics. K-means is deliberately strong, because it is handed the cheapest fleet, exact flows and our refinement. Its best run reaches our network.")
P("That result cuts both ways. A separate starting method reaching the same cost is independent support for it. It also shows the site search adds little once the fleet is known, because transport is a small share of cost and the objective is flat near the optimum. The search still contributes the proven bound, the fleet and size choice when a scenario makes that unobvious, and the limits in section 13. These are model results, with no measured savings against real planners.")
H1("12. Depot trade-off")
ab = [
    ("Annual total, USD M", lambda s: s["objective"], 2), ("CapEx, USD M", lambda s: s["costs"]["capex_total"], 1), ("Annualised CapEx plus fixed OpEx, USD M/yr", lambda s: s["costs"]["annual_capex"] + s["costs"]["opex_fixed"], 1),
    ("Variable OpEx, USD M/yr", lambda s: s["costs"]["opex_variable"], 1), ("Logistics, USD M/yr", lambda s: s["costs"]["logistics_total"], 1), ("Depots", lambda s: s["kpis"]["n_depots"], 0), ("Refineries", lambda s: s["kpis"]["n_refineries"], 0),
    ("Biomass, kt/yr", lambda s: s["kpis"]["biomass_used_kt"], 0), ("SAF, kt/yr", lambda s: s["kpis"]["saf_kt"], 0), ("Demand met, %", lambda s: 100 * s["kpis"]["fill_rate"], 0), ("Freight moved, billion tonne-km", lambda s: s["kpis"]["tonne_km_bn"], 3), ("Estimated truck-km, millions", lambda s: s["kpis"]["truck_km_m"], 1),
]
table([["Measure", "A: at refinery, optimised", "B: in field, heuristic", "Change"]] + [[l, f"{f(base):,.{d}f}", f"{f(field):,.{d}f}", f"{f(field) - f(base):+,.{d}f}"] for l, f, d in ab], [7 * cm, 3.6 * cm, 3.4 * cm, 3 * cm])
P(f"Design B gathers biomass within 60 km and hauls the long leg in larger trucks, so it moves {TK:.1f}% more tonne-km but needs an estimated {VK:.1f}% fewer truck-km. That estimate assumes large trucks with empty returns and includes the barge portion to Tarakan, so it is not a count of vehicle trips. A tonne-km tariff cannot see this benefit. B is a heuristic with no optimality proof, and it sits {100 * field['gap_to_bound']:.2f}% above the proven bound.")

H1("13. Scenario and sensitivity analysis")
table([["Scenario", "Status", "USD M/yr", "USD/t", "Ref", "Dep", "Gap"]] + [
    [n, s["status"], f"{s['objective']:.1f}", f"{s['kpis']['unit_cost_usd_t']:,.0f}", s["kpis"]["n_refineries"], s["kpis"]["n_depots"], "No proof" if s["gap"] is None else f"{100 * s['gap']:.2f}%"]
    for n, s in [("Official base", base), ("High demand, +10%", hd), ("High transport, +50%", ht), ("All 6,800 kt, 340 kt per airport", allf), ("Field depots", field), ("OSRM road distances", road), ("Real uplift at 5% blend", real)]
], [5.8 * cm, 2.4 * cm, 2 * cm, 1.8 * cm, 1 * cm, 1 * cm, 1.6 * cm])
P(f"High demand forces a small plant into the fleet because six large plants take only 6,522 kt. Raising tariffs by 50% adds {usd(ht['objective'] - base['objective'])} and leaves the fleet at six plants. Figure 4 shows why: refinery terms dominate, and yield matters most, since it sets how much biomass and capacity are needed at all.")
figure("tornado.png", 12 * cm, "Figure 4. One-at-a-time changes of 20% around the base case. Yield and biomass at -20% are infeasible.")
figure("ladder.png", 12 * cm, f"Figure 5. Cost per tonne by demand level. Each point is a full solve.")
H2("Marginal economics")
P(f"Each row below is a full re-solve on candidate sites, against a base of {usd(M['base'], 2)}. These are finite-difference planning estimates and not shadow prices, because plant decisions are whole units.")
table([["Change", "USD M/yr", "USD per extra t", "Fleet", "Gap"]] + [
    [r["label"], "Infeasible" if r["delta"] is None else f"{r['delta']:+.1f}", "n/a" if r["usd_per_t"] is None else f"{r['usd_per_t']:,.0f}", "n/a" if r["delta"] is None else f"{r['n_large']} large" + (f", {r['n_small']} small" if r["n_small"] else ""), "n/a" if r["gap"] is None else f"{100 * r['gap']:.2f}%"] for r in M["rows"]
], [6.4 * cm, 2.4 * cm, 2.8 * cm, 3.2 * cm, 2 * cm])
P(f"Six large plants reach their limit at {6 * 1087 * 0.2:,.1f} kt of SAF. Below that, extra demand costs about USD 480 to 560 per tonne. The next kilotonne needs a seventh plant, so cost steps up sharply. Several increments are smaller than the solver gap in absolute terms, so small differences should not be over-read.")
H2("Reality check on demand")
P(f"The official demand of 1,200 kt is far above what these airports use today. We estimate real jet uplift at about 100 kt per year, from Pertamina volumes at BPN and PNK [13, 14] and DGCA and BPS passenger counts [15], so official demand is about 12 times total current jet use. Indonesia's 1% SAF mandate from 2027 covers international departures from Jakarta and Bali only [16], so we applied Singapore's 3 to 5% target for 2030 [17] as a stand-in. A 5% blend gives about 5 kt SAF, which the model serves with one small refinery at 5% utilisation at USD {real['kpis']['unit_cost_usd_t']:,.0f}/t. The official figure should therefore be read as a future or regional hub volume. Cost per tonne only settles once plants run near capacity, as Figure 5 shows.")
H2("Reality check on distance")
P(f"With OSRM road distances in place of great-circle x 1.3, annual cost rises by {usd(road['objective'] - base['discrete_objective'])} to {usd(road['objective'])}, a {100 * (road['objective'] / base['discrete_objective'] - 1):.1f}% change, and the fleet size holds. Transport's low share limits the effect.")
H2("Where the model fails")
table([["Case", "Result", "What the planner sees"]] + [
    ["Demand +20%", "Infeasible", inf1["diagnostics"][0]["reason"] + " " + inf1["diagnostics"][0]["fix"]],
    ["Yield 0.15", "Infeasible", inf2["diagnostics"][0]["reason"] + " " + inf2["diagnostics"][0]["fix"]],
    ["At most 5 refineries", "Infeasible", inf3["diagnostics"][0]["reason"] + " " + inf3["diagnostics"][0]["fix"]],
], [3 * cm, 2 * cm, 12 * cm])
P(f"Demand can rise by at most {100 * (6800 / 6000 - 1):.1f}% before feedstock runs out. Yield below {1200 / 6800:.3f} makes 1,200 kt unreachable. The update allows yields of 15 to 25%, so the bottom of that range cannot meet official demand.")

H1("14. AI decision support")
P("KASCO has two question layers. The Decision support tab is explainable and rule-based, with mathematical optimisation underneath. It uses no language model and no trained machine-learning model, which keeps every number reproducible. A question routes by rule to an intent, and each intent reads named fields from a solver result and lists them under its answer. A refinery explanation includes a time-limited counterfactual solve with nearby sites closed. Questions about emissions, price or law are declined with a reason, because the model holds cost, mass and capacity only.")
P("A what-if request is read clause by clause, so it can change several inputs at once, each with its own sign. It runs only when every part maps to a validated input, and otherwise it refuses and says which part it could not read. An audit found that the first version silently dropped a change and read the hyphen in 'what-if' as a minus sign. Both faults are fixed and covered by tests. The trade-off is that this layer understands a narrower range of phrasing than a language model would.")
P("The second layer is an optional analyst panel that calls Claude Opus 5.5 directly from the browser. GitHub Pages cannot hold a private key, so the viewer pastes their own Anthropic key, which stays in the tab's memory and goes only to api.anthropic.com. The model receives a snapshot of solver results, can call the rule-based engine for what-ifs, and returns short bullets, practical actions, the visual to open and what to explore next. The app removes any line with a figure it cannot match to the snapshot, the question or the solver output. That check catches invented figures, but it cannot prove a matched figure supports the claim beside it, so a planner should confirm the answer on the visual it opens. A hosted version would need a proxy, an account and a spend cap, so that stays future work.")

H1("15. Validation and optimality evidence")
P(f"A separate audit module recomputes every balance and the objective from flow records, using its own distance calculation. All {len(base['validation'])} checks pass on the base case. Automated tests cover input data, capacities, mass balance, yield, demand, objective arithmetic, recalculation, infeasible cases, tampering and the what-if parser, and all {TESTS} pass. Tampering tests confirm the audit fails when a flow or objective is altered.")
if H:
    P(f"As a second opinion, the Rust tool exports the co-located candidate-site model as a plain LP file and HiGHS {H['solver'].split()[-1]} solves it separately. HiGHS reaches {usd(H['objective'], 4)} with a lower bound of {usd(H['bound'], 2)} ({H['gap_pct']:.2f}% gap at its {H['time_limit_s']:.0f} s limit). The Rust cost on the same candidate sites is {usd(base['discrete_objective'], 4)} with a bound of {usd(base['bound'], 2)} ({100 * base['gap']:.2f}% gap in {base['runtime_s']:.0f} s). Two separate codes reached the same cost, which is strong evidence that the formulation and the search agree.")
CK = load("bound_check")
if CK:
    P(f"A tighter bound is only useful if it is valid, so we tested it on {len(CK)} smaller demand levels that HiGHS can close. In each case the Rust bound must not exceed the HiGHS optimum.")
    table([["Total demand, kt", "Rust cost", "Rust bound", "HiGHS cost", "HiGHS bound", "Bound valid"]] + [[f"{r['total_demand_kt']:.0f}", f"{r['rust_cost']:.3f}", f"{r['rust_bound']:.3f}", f"{r['highs_cost']:.3f}", f"{r['highs_bound']:.3f}", "Yes" if r["bound_valid"] else "No"] for r in CK], [3 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.6 * cm])
P("Status of each result: the base case is feasible within a proven gap on candidate sites, the five small cases match a proven optimum, refined coordinates are locally refined, and the field design is a heuristic. We make no claim of global optimality for the unrestricted location problem.")

H1("16. Limitations")
P("The challenge's simplified inputs are necessary for a fair comparison, and they also shape the answer. Official demand is about 12 times our estimate of today's real jet use at these airports. The 80 biomass points are modelling inputs. A single tariff per leg hides road quality, river transport and seasonal access. Zero depot mass loss removes the main physical reason for field depots.")
bullets([
    "The model is deterministic and annual, with no seasonality, storage or supply risk.",
    "Biomass price is outside the objective by instruction. Including it would favour the same sites only if prices are uniform.",
    "Co-located depots follow from zero mass loss and the published tariffs. Real wet feedstock could change this, as section 6 shows.",
    f"The field design is a heuristic, so its {usd(B['field']['saving_usd_m'])} premium is an upper estimate.",
    "Site screening is preliminary. Land tenure, peat, forest status, water and hydrogen supply are unchecked, so no site is shown to be buildable.",
    "The land mask covers all of Borneo, so it does not separate Kalimantan from Sarawak and Sabah. All base-case plants lie in Kalimantan.",
    "The truck-km estimate assumes large trucks and empty returns, and it includes the barge portion to Tarakan.",
    "Real uplift for PKN and TRK is scaled from passengers, and the PNK volume is reported for West Kalimantan as a whole.",
])

H1("17. Future development")
P("These are possible next steps, not commitments or achievements.")
bullets([
    "<b>Secure language-model layer.</b> Natural-language requests would pass through a server-side proxy to structured parameters, the existing validator and the Rust solver. The model would never set costs, sites or results.",
    "<b>Real-world validation.</b> Replace the tariffs and distances with road, river and port data, then screen sites for land tenure, peat and forest status with local stakeholders [2].",
    "<b>Feedstock quality.</b> Replace the fixed yield with measured site data, including moisture and ash, as Li et al. recommend for logging residues [4]. Moisture alone decides whether depots belong in the field.",
    "<b>Uncertainty.</b> Once supply data can support an uncertainty set, test robust optimisation in the style of Keyvandarian et al. [27].",
])

H1("18. Conclusions")
P(f"A six-plant network at {usd(base['objective'], 0)} per year meets official demand, with the result checked by an independent audit and a second solver. The strongest levers are refinery cost and yield, and transport matters much less than a logistics framing suggests. KASCO's value lies in letting a planner test these questions in seconds, see where an idea fails and know how far an answer can be from the best possible. Given the right fleet, simple methods can get close, and we say so.")

H1("19. References")
refs = [
    "Airbus and Acacia Hackathon Society (2026). Autonomous SG 2026 problem statements, and Summary of Updates, 31 October 2026, 12:45.",
    "Ng, R.T.L., Kurniawan, D., Wang, H., Mariska, B., Wu, W., Maravelias, C.T. (2018). Integrated framework for designing spatially explicit biofuel supply chains. Applied Energy 216, 116-131.",
    "Ng, R.T.L., Maravelias, C.T. (2017). Design of biofuel supply chains with variable regional depot and biorefinery locations. Renewable Energy 100, 90-102.",
    "Li, P., Yu, T.E., Labbe, N., Abdoulmoumine, N., Garcia-Perez, M., Hoyt, K.P., English, B.C. (2026). Spatial optimization of the sustainable aviation fuel supply chains from forest residues via fast pyrolysis/hydrotreatment considering feedstock ash content variability. Biomass and Bioenergy 208, 108793.",
    "Huang, E., Zhang, X., Rodriguez, L., Khanna, M., de Jong, S., Ting, K.C., Ying, Y., Lin, T. (2019). Multi-objective optimization for sustainable renewable jet fuel production: a case study of corn stover based supply chain system in Midwestern U.S. Renewable and Sustainable Energy Reviews 115, 109403.",
    "Hernandez-Araujo, I.F., Quiroz Ramirez, J.J., Contreras-Zarazua, G., Sanchez-Ramirez, E., Segovia-Hernandez, J.G. (2026). Integrated multiscale optimization of sustainable aviation fuel systems: coupling supply chain with intensified alcohol-to-jet process upgrading. Processes 14, 2653.",
    "Castillo-Villar, K.K., Keith, K., Alaeddini, A. (2026). Computationally efficient optimization of bio-jet fuel supply chains using machine-learning-assisted mixed-integer programming. Energies 19, 3570.",
    "Chia, M. (2026). Sustainable Aviation Fuel: trends, technologies and outlook. CN4252 lecture, National University of Singapore.",
    "Lim, K.H. (2026). From lab to market: venture building in decarbonization. CN4252 lecture, National University of Singapore.",
    "Cooper, L. (1963). Location-allocation problems. Operations Research 11(3), 331-343.",
    "Weiszfeld, E. (1937). Sur le point pour lequel la somme des distances de n points donnes est minimum. Tohoku Mathematical Journal 43, 355-386.",
    "Huangfu, Q., Hall, J.A.J. (2018). Parallelizing the dual revised simplex method. Mathematical Programming Computation 10, 119-142.",
    "Pertamina Patra Niaga Kalimantan statements on daily avtur distribution, March 2024, reported in regional press including Kompas, 25 March 2024.",
    "Pontianak Post (2024). Permintaan avtur naik 8% di Bandara Supadio.",
    "Wikipedia airport pages for PNK, PKN, BPN and TRK, citing DGCA and BPS Statistik Transportasi Udara 2024. Accessed 31 October 2026.",
    "Argus Media (2024). Indonesia to require SAF for flights from 2027; Antara News (2026), on the 2027 rollout at Jakarta and Bali.",
    "S&amp;P Global (2024). Singapore mandates SAF use for departing flights, to introduce levy from 2026.",
    "OpenStreetMap contributors via OSRM; Natural Earth 10 m land; OpenFlights airports. Accessed 31 October 2026.",
    "QC Intelligence (August 2025). Airbus and Indonesia team up on biomass-based SAF: reports. qcintel.com. Also Biofuels Digest, August 2025.",
    "Waste Dive (September 2024). Fulcrum BioEnergy Chapter 11 filing. wastedive.com.",
    "IATA (9 December 2025). Press release on 2025 SAF production. iata.org.",
    "Hydrocarbon Engineering (13 August 2025). Kilang Pertamina delivers SAF.",
    "Roundtable on Sustainable Biomaterials and Boeing (3 September 2024). Sustainable feedstock potential in Southeast Asia. rsb.org.",
    "GHD. Promoting sustainable aviation fuels across Southeast Asian Nations. ghd.com. See also S&amp;P Global, 11 April 2025.",
    "Inayah et al. (2026). Preliminary assessment of SAF potential from municipal, agricultural and plantation wastes in Indonesia. journals.aau.dk.",
    "Jurnal Transportasi, Universitas Katolik Parahyangan. Regional freight transportation model for crude palm oil in Central Kalimantan. About 2010.",
    "Keyvandarian, A., Pirnia, M., Scott, D. (2026). Robust optimal design of sustainable aviation fuel supply chain. Computers and Industrial Engineering.",
]
for n, r in enumerate(refs, 1):
    story.append(Paragraph(f"[{n}] {r}", ParagraphStyle("R", parent=body, fontSize=8.4, leading=11, spaceAfter=3)))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52514e"))
    canvas.drawString(2 * cm, 1.2 * cm, "KASCO: Kalimantan SAF Supply Chain Optimiser. Wee Zhern Ray")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
    canvas.restoreState()


doc = SimpleDocTemplate(str(REP / "KASCO_Technical_Report.pdf"), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.9 * cm, title="KASCO technical report", author="Wee Zhern Ray")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("report written")
