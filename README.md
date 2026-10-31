# KASCO: Kalimantan SAF Supply Chain Optimiser

AI-Driven Optimisation for a More Sustainable Aviation Future

Airbus Challenge 3, Autonomous SG 2026. Built by Wee Zhern Ray, Year 3 Chemical Engineering, NUS.

**Live app:** https://weewzr.github.io/airbustrack3ray/

KASCO is a working prototype of a planning tool for a Sustainable Aviation Fuel network across Kalimantan. It picks refinery and depot locations and sizes, routes biomass and SAF to the four international airports, and shows the proof behind each number. The solver is written in Rust and compiled to WebAssembly, so the whole product runs in the browser from GitHub Pages with no server. An optional Claude Opus 5.5 analyst answers free-form questions from solver data, using the viewer's own API key.

## Who it is for

A SAF network planner who must decide where to commit about USD 4.7B of plant capital before engineering starts. The usual alternative is comparing a few hand-drawn layouts in a spreadsheet. Here the planner changes an assumption, reruns the search and sees the network, the cost and every constraint check. The planner decides. The tool does not claim to replace engineering judgement.

## What is in the app

| Deliverable | Where |
|---|---|
| A. Interactive map | Network map tab: 80 sites, flows by leg, click-through figures, layer toggles, side-by-side comparison |
| B. Optimisation engine | `crates/engine`: Lagrangian branch-and-bound, exact min-cost flow, continuous location refinement |
| C. Scenario simulator | Optimisation and Scenario analysis tabs: every input is editable and reruns the real solver in the browser |
| D. Decision support | Decision support tab: rule-based and fully traceable, with no language model. What-ifs can change several inputs and rerun the solver, and they refuse if any part is unclear. Questions outside the model are declined. The optional Ask Claude Opus 5.5 panel (`docs/assistant.js`) answers free-form questions in short bullets from a snapshot of solver data, opens the matching visual and suggests what to explore next. The viewer's key stays in tab memory and goes only to api.anthropic.com, and lines with a figure not found in the data are removed |
| E. Evaluation and evidence | Evaluation and Reports tabs, plus `docs/reports` |

## Official inputs

From the Airbus update of 31 October 2026, 12:45, and `data/challenge3_parameters.xlsx`. `scripts/check_official.py` compares the engine with the workbook.

- Demand is 300 kt SAF per airport, 1,200 kt in total, which needs 6,000 kt of biomass. Using all 6,800 kt is not required.
- Yield is 0.20 t SAF per t biomass, depots lose no mass, and capacity means biomass intake.
- Costs are on a one-year basis: CapEx straight-line over 20 years with no interest, and fixed OpEx at 5% of CapEx.
- Variable OpEx per tonne in is USD 5 and 4 for small and large depots, and USD 60 and 55 for small and large refineries.
- Distance is great-circle x 1.3. Tariffs are 0.10, 0.12 and 0.08 USD/t/km, the same for both truck sizes.
- Tarakan is an island, so its last leg is by barge at USD 0.08/t/km.

## Results

Base case: USD 890.09M per year, USD 742 per tonne SAF before feedstock, six large refineries and 23 depot modules. On candidate sites this is proven within 0.75%.

| Result | Status |
|---|---|
| Base case, 70 candidate sites | Feasible within a proven gap |
| Five smaller cases | Rust cost equals the HiGHS proven optimum |
| Refined coordinates | Local refinement, no global proof |
| Field depots | Heuristic, no optimality proof |

The network costs USD 61M to 77M per year less than two simple heuristic layouts. A strong k-means benchmark, handed the same six-plant fleet and our refinement, reaches the same network at best and sits about USD 1.1M above it at median, because transport is only 7.5% of cost. The tool's value is the proven bound, the fleet and size choice in each scenario, and the limits it exposes. These are model results, not measured savings against real planners.

## Method in brief

1. **Search over refinery sites.** The candidate-site model is a capacitated facility location problem. Relaxing supply and demand with multipliers splits it into one small subproblem per site, which gives a proven lower bound. Branch-and-bound searches the sites, though most of the bound comes from the root relaxation.
2. **Exact flows.** For any set of open refineries, min-cost flow gives the optimal routing.
3. **Continuous refinement.** Sites may be anywhere on land, so plants then move to their weighted geometric median, with a land check.
4. **Independent checks.** `validate.rs` recomputes every balance and the objective from flow records. HiGHS solves the co-located model from an exported LP file as a second opinion.

Depots sit at refineries under these inputs, because the second leg costs more per tonne-km and depots lose no mass. On the base fleet, HiGHS confirmed that no cheaper layout exists with depots free to go anywhere (`scripts/verify_depots.py`). Real wet feedstock could change this, so a field-depot design is included as a priced alternative. It moves more tonne-km but needs an estimated 25% fewer truck-km. See `docs/MODEL.md` for the formulation.

## Limits

- The 80 biomass points are official modelling inputs, not surveyed sites. 13 fall off the coastline.
- Site screening is preliminary, so no site is shown to be buildable. Land tenure, peat and forest status are unchecked.
- Official demand is about 12 times our estimate of today's real jet use at these airports, so this is a hub-scale plan.
- The model is deterministic and annual, and biomass purchase price is outside the objective by instruction.

## Documents

The technical report, pitch deck and cover image are in `docs/reports`. Submission text and the pitch script are in `docs/SUBMISSION.md`.

## Run it

Serve the site locally:

```bash
cd docs && python -m http.server 8765
```

Rebuild from source (needs Rust and the `wasm32-unknown-unknown` target):

```bash
cargo test --release -p saf_engine
cargo run --release -p saf_cli -- all 60
cargo build --release -p saf_wasm --target wasm32-unknown-unknown
cp target/wasm32-unknown-unknown/release/saf_wasm.wasm docs/saf.wasm
```

Cross-checks, which need the Python packages in `requirements-dev.txt`:

```bash
cargo run --release -p saf_cli -- lp model.lp
```

```bash
python scripts/verify_highs.py model.lp 480
```

```bash
python scripts/verify_bound.py target/release/saf model_folder
```

```bash
python scripts/verify_depots.py 240
```

```bash
python scripts/check_official.py
```

## Repository

```
crates/engine   solver, audit, baselines, diagnostics, decision support, 38 tests
crates/cli      batch runner and LP export
crates/wasm     browser entry points
docs            the deployed site, result JSON and reports
data            official datasets, OSRM road matrix, land mask
scripts         data fetch, HiGHS check, report and deck generators (Python)
```

The engine and app are Rust and JavaScript. Python is used only for data fetching, independent checks and document generation.

## Sources

Official Airbus problem statement and the update of 31 October 2026. Airports from the official CSV. Land mask from Natural Earth (public domain). Road distances from OpenStreetMap via OSRM, fetched by `scripts/build_data.py`. Real-uplift figures are fetched and recorded by `scripts/fetch_context.py`, with sources in `docs/data/context_check.json`, and appear only in a labelled reality check. Real-world evidence is cited in the Reports tab and the report. Formulation informed by Ng et al. (2018), Ng and Maravelias (2017), Li et al. (2026), Huang et al. (2019), Hernandez-Araujo et al. (2026), Castillo-Villar et al. (2026) and Keyvandarian et al. (2026).

Licence: MIT.
