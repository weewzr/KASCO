# Kalimantan SAF Optimiser

Airbus Challenge 3, Autonomous SG 2026. Built by Wee Zhern Ray, Year 3 Chemical Engineering, NUS.

**Live app:** https://weewzr.github.io/airbustrack3ray/

A planning tool for a Sustainable Aviation Fuel network across Kalimantan. It picks refinery and depot locations and sizes, routes biomass and SAF to the four international airports, and shows the proof behind each number. The solver is written in Rust and compiled to WebAssembly, so the whole product runs in the browser from GitHub Pages with no server and no API key.

## Who it is for

A SAF network planner who must decide where to commit about USD 4.7B of plant capital before engineering starts. The usual alternative is comparing a few hand-drawn layouts in a spreadsheet. Here the planner changes an assumption, reruns the search and sees the network, the cost and every constraint check. The planner decides. The tool does not claim to replace engineering judgement.

## What is in the app

| Deliverable | Where |
|---|---|
| A. Interactive map | Network map tab: 80 sites, flows by leg, click-through figures, layer toggles, side-by-side comparison |
| B. Optimisation engine | `crates/engine`: Lagrangian branch-and-bound, exact min-cost flow, continuous location refinement |
| C. Scenario simulator | Optimisation and Scenario analysis tabs: every input is editable and reruns the real solver in the browser |
| D. Decision support | Decision support tab: rule-based and fully traceable, with no language model. It reruns the solver for what-if questions and declines questions outside the model |
| E. Evaluation and evidence | Evaluation and Reports tabs, plus `docs/reports` |

## Method in brief

Official inputs come from the Airbus update of 31 October 2026, 12:45. Demand is 300 kt SAF per airport, yield is 0.20 and capacity means biomass intake. Costs are on a one-year basis, CapEx straight-line over 20 years, with fixed OpEx at 5% of CapEx. Distance is great-circle x 1.3.

1. **Search over refinery sites.** The candidate-site model is a capacitated facility location problem. Relaxing supply and demand with multipliers splits it into one small subproblem per site, which gives a proven lower bound. Branch-and-bound closes the gap.
2. **Exact flows.** For any set of open refineries, min-cost flow gives the optimal routing.
3. **Continuous refinement.** Sites may be anywhere on land, so plants then move to their weighted geometric median, with a land check.
4. **Independent audit.** `validate.rs` recomputes every balance and the objective from flow records. HiGHS solves the same model from an exported LP file as a second opinion.

Depots are placed at refineries because the second leg costs more per tonne-km than the first and depots lose no mass. Any field depot then adds cost, by the triangle inequality. A field-depot design is included as a priced alternative. See `docs/MODEL.md` for the formulation.

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

Cross-check with HiGHS, which needs Python and `highspy`:

```bash
cargo run --release -p saf_cli -- lp model.lp
python scripts/verify_highs.py model.lp 480
```

## Repository

```
crates/engine   solver, audit, baselines, diagnostics, decision support, 25 tests
crates/cli      batch runner and LP export
crates/wasm     browser entry points
docs            the deployed site, result JSON and reports
data            official datasets, OSRM road matrix, land mask
scripts         data fetch, HiGHS check, report and deck generators (Python)
```

The engine and app are Rust and JavaScript. Python is used only for one-off data fetching, the independent HiGHS check and document generation.

## Sources

Official Airbus problem statement and the update of 31 October 2026. Airports from OpenFlights via the official CSV. Land mask from Natural Earth (public domain). Road distances from OpenStreetMap via OSRM, fetched by `scripts/build_data.py`. Reality-check figures come from public Pertamina, DGCA and BPS statistics, cited in the report. Formulation informed by Ng et al. (2018), Ng and Maravelias (2017), Li et al. (2025), Huang et al. (2019), Hernandez-Araujo et al. (2026) and Castillo-Villar et al. (2026).

Licence: MIT.
