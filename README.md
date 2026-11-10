# KASCO: Kalimantan SAF Supply Chain Optimiser

AI-Driven Optimisation for a More Sustainable Aviation Future

Airbus Challenge 3, Autonomous SG 2026. Built by Wee Zhern Ray, Year 3 Chemical Engineering, NUS.

**Live app:** https://weewzr.github.io/KASCO/

KASCO is a working prototype of a planning tool for a Sustainable Aviation Fuel network across Kalimantan. It picks refinery and depot locations and sizes, routes biomass and SAF to the four international airports, and shows the proof behind each number. The solver is written in Rust and compiled to WebAssembly, so the whole product runs in the browser from GitHub Pages with no server. An optional Claude Sonnet 5.5 analyst answers free-form questions from solver data, using the viewer's own API key.

## Who it is for

A SAF network planner who must decide where to commit about USD 4.7B of plant capital before engineering starts. The usual alternative is comparing a few hand-drawn layouts in a spreadsheet. Here the planner changes an assumption, reruns the search and sees the network, the cost and every constraint check. The planner decides. The tool does not claim to replace engineering judgement.

## What is in the app

| Deliverable | Where |
|---|---|
| A. Interactive map | Network map tab: 80 sites, flows by leg, click-through figures, layer toggles, side-by-side comparison |
| B. Optimisation engine | `crates/engine`: Lagrangian branch-and-bound, exact min-cost flow, continuous location refinement |
| C. Scenario simulator | Optimisation and Scenario analysis tabs: every input is editable and reruns the real solver in the browser |
| D. Decision support | Decision support tab: rule-based and fully traceable, with no language model. What-ifs can change several inputs and rerun the solver, and they refuse if any part is unclear. Questions outside the model are declined. The optional Ask Claude Sonnet 5.5 panel (`docs/assistant.js`) answers free-form questions in short bullets from a snapshot of solver data, opens the matching visual and suggests what to explore next. The viewer's key stays in tab memory and goes only to api.anthropic.com, and lines with a figure not found in the data are removed |
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

## Front end

This section records the 2026-11 front-end review. It changed presentation only. No solver, parameter, result file, export or report generator was touched, and `git diff main --stat` lists nothing under `crates`, `data`, `docs/data`, `docs/reports` or `docs/saf.wasm`.

### Original architecture

The served site in `docs/` is plain HTML, CSS and JavaScript with no bundler. `app.js` keeps one mutable `state` object and renders each tab by assigning template strings to `innerHTML`. Leaflet draws the two maps and Chart.js draws five canvases, both loaded from cdnjs. The Rust engine runs inside `worker.js` as `saf.wasm`, reached through one promise-keyed `rpc` function. `assistant.js` holds the optional language-model analyst. Figures shown before any run come from the committed JSON in `docs/data`.

### What changed

| Area | Change |
|---|---|
| Structure and keyboard | Skip link, a landmark around the tab strip, the WAI-ARIA tabs pattern (roving focus, arrow keys, Home and End, linked panels) and a tab hash in the address bar so a tab can be linked. |
| Names and live regions | Accessible names for the compare select and for the question and key fields. Run status and answers are live regions, and so is the selected-location panel. |
| Analyst panel | A labelled dialog that takes focus on open, closes on Escape and returns focus to its button. The key field, the fetch and the data sent are unchanged. |
| Map | Every focusable marker has a name. The legend explains the flow lines and the faded unused sites. A selected-location panel and a sortable, filterable site list select the same location as a marker click and open its popup, so the map has a keyboard route. |
| Charts and tables | Charts carry a text alternative that quotes their values where there are few. Scrollable tables become focusable named regions only when they overflow. Column headers have scopes, and links that open a new tab say so. |
| Motion and focus | `prefers-reduced-motion` turns off Chart.js animation and Leaflet zoom animation, and CSS transitions shrink to near zero. Every control has a visible focus ring. |
| Evidence labels | Each scenario carries badges for its strength of evidence: exact within target, feasible within a proven gap, refined coordinates (local refinement, no global proof), heuristic, reality check on public data, or no feasible network. Shape and words carry the meaning, colour only supports it. A key on Overview, Scenario analysis and Evaluation explains them. |
| Source of an answer | Solver results, the rule-based Decision support tab and the optional language-model panel each carry their own tag. Model text is marked AI-written and not verified. |
| Scenario configuration | Inputs sit in groups with units. Each field has an inline message for a value that cannot be run, and a warning for a value outside the range the Airbus update gives. A mass-balance screen shows whether the demanded SAF can come from the biomass on offer. Changed inputs are outlined and counted, and reset restores every input including the selects and the run name. |
| Solver controls | Run is disabled while solving. A timer and progress bar show elapsed time against the limit, a status line announces the start and end, and Cancel replaces the worker so the page stays responsive. |
| Comparison | Side by side adds annualised CapEx, fixed and variable OpEx, demand met, fleet, depot modules, optimality gap and evidence, marks truck-km as an estimate, and warns when a heuristic is compared with a proven result. |
| Feasibility summary | Overview shows demand met, the independent audit as a pass count, biomass used, highest refinery use and the gap, all read from existing solver fields. |

One displayed value was corrected. A custom run of a heuristic design (depots in the field) showed 0.00% under the label Proven gap. It now shows the distance above the proven bound, labelled as a heuristic with no proof, as the Overview already did.

### Astryx evaluation

Astryx (`@astryxdesign/core` 0.7.11, MIT, beta) was tried as an isolated island bundled with esbuild 0.28.2 (minified, subpath imports, React 19.3.1). The probes lived outside the repository and are not committed. Sizes were re-measured on the day of the change and mount times are the median of five mounts in headless Edge.

| Probe | JS raw, B | JS gzip, B | Added over React alone, gzip B | Mount, ms |
|---|---|---|---|---|
| React only | 223,507 | 69,049 | n/a | 62 |
| TabList, 7 tabs | 460,104 | 144,454 | 75,405 | 119.9 |
| Dialog, Button, Tooltip | 540,166 | 169,323 | 100,274 | 152.1 |

Astryx also ships prebuilt CSS: 269,224 B (39,947 B gzip) plus a 11,501 B reset and a 24,877 B neutral theme, 47,571 B gzip in all. For comparison, the whole of `app.js` is 25,248 B gzip after this change. The TabList island alone costs about three times that, and it would replace a seven-button strip that about 25 lines of vanilla JavaScript now handle. It would also add a second owner of the current-tab state next to `state.tab`, and its `light-dark()` theme tokens would need mapping onto the dark palette.

**Decision: no Astryx component is adopted, and no bundle is committed.** The review found no accessibility, consistency or maintainability gain that the existing stack could not deliver at a fraction of the cost, so the shipped site keeps its vanilla JavaScript.

| Component considered | Not migrated because |
|---|---|
| TabList, Tab | Same pattern achieved in about 25 lines. Island adds 75 kB gzip JS, 48 kB gzip CSS and a second state owner. |
| Dialog, Drawer | Role, focus entry, Escape and focus return took about 10 lines. The island adds 100 kB gzip JS, and moving the key field into React would put the key handling at risk. |
| Table, Badge | Tables are static markup built from solver output. Rebuilding them as React data adds rewrite risk for no new behaviour. The badges cost under 1 kB of CSS. |
| Field, NumberInput, Selector | The form reads its values from the DOM in `formParams()`. A controlled React form would create a second source of truth. |
| Charts | `@astryxdesign/charts` is experimental and is not used in a scientific interface. Chart.js stays. |
| Map | Astryx has no map component. Leaflet stays. |

Dependencies added: none for the served site. `package.json` lists two development dependencies for the checks (`axe-core` 4.14.0 and `puppeteer-core` 24.43.1), locked in `package-lock.json`. Neither is served or bundled.

### Theming decisions

The dark palette and its CSS custom properties are unchanged apart from two tokens. `--bad` moved from `#e66767` to `#f08080`, which lifts the failed-status pill from 4.17:1 to 5.20:1 on `--surface-2` (6.12:1 on `--surface`). `--focus` (`#6fe3d6`, 10.3:1 on `--surface`) is new and drives the focus ring. Nothing else in the palette or in the shapes of tabs, buttons and forms changed.

### Measurements

Commands are in the next section. Lighthouse used Edge with `--headless=new`, two runs per case against a plain `python -m http.server` (no compression), baseline commit 41194fa and this branch.

| Form factor | Build | Performance | Accessibility | FCP, ms | LCP, ms | TBT, ms | CLS | Transfer, KiB |
|---|---|---|---|---|---|---|---|---|
| desktop | Baseline 41194fa | 96 / 98 | 100 / 100 | 852 / 552 | 1012 / 861 | 20 / 30 | 0.074 / 0.074 | 362 / 362 |
| desktop | This branch | 97 / 98 | 100 / 100 | 794 / 572 | 794 / 572 | 18 / 23 | 0.091 / 0.091 | 395 / 395 |
| mobile | Baseline 41194fa | 88 / 89 | 100 / 100 | 2048 / 2033 | 2048 / 2033 | 186 / 144 | 0.160 / 0.160 | 362 / 362 |
| mobile | This branch | 89 / 89 | 100 / 100 | 2237 / 2033 | 2237 / 2033 | 327 / 346 | 0.011 / 0.011 | 395 / 395 |

Each cell shows run 1 and run 2. A second batch alternated the two builds on mobile, three runs each, to separate build effects from drift over time:

| Mobile, alternating | Performance | TBT, ms | FCP, ms | CLS |
|---|---|---|---|---|
| Baseline 41194fa | 94 / 93 / 92 | 79 / 273 / 238 | 2407 / 1791 / 2127 | 0 / 0.011 / 0.011 |
| This branch | 92 / 94 / 89 | 258 / 248 / 332 | 2056 / 1752 / 2201 | 0 / 0.011 / 0.011 |

The runs vary more between repeats of the same build than between the two builds. In the first batch the branch showed higher mobile blocking time (327 and 346 ms against 186 and 144 ms) and a higher desktop layout shift (0.091 against 0.074). The alternating batch gives medians of 238 ms for the baseline and 258 ms for the branch, and the same layout shift for both, so this sample can neither show nor rule out a small slowdown. What is certain is the size: transfer grows by 33 KiB uncompressed, which is the added script, style and markup. Timed in the page without throttling, rendering the Overview takes 16.0 ms before and 16.7 ms after (median of 8), and building the Optimisation form takes 0.5 ms before and 1.8 ms after. The Lighthouse accessibility score is 100 for both builds because it uses a subset of the axe rules, which is why the full axe run is reported below.

| Measure | Before | After |
|---|---|---|
| axe-core 4.14.0 violations, 7 tabs, 1440x900, with and without reduced motion | 40 nodes (region 7, aria-command-name 29, color-contrast 3, select-name 1) | 0 |
| axe-core violations, 7 tabs, 390x844, with and without reduced motion | 51 nodes (the above plus scrollable-region-focusable 11) | 0 |
| `app.js` raw, gzip (LF endings) | 50,597 B, 16,919 B | 76,474 B, 25,248 B |
| `assistant.js` raw, gzip | 21,179 B, 7,814 B | 21,971 B, 8,064 B |
| `style.css` raw, gzip | 8,649 B, 2,496 B | 14,589 B, 3,800 B |
| `index.html` raw, gzip | 2,306 B, 978 B | 3,015 B, 1,165 B |
| First-load code (HTML, CSS, two scripts), gzip | 28,207 B | 38,277 B |
| `saf.wasm` | 1,667,898 B | unchanged, still fetched on the first solve |

The before values for axe come from a run against the baseline commit with the same rules and viewports.

### Tests run

- `cargo test --release -p saf_engine`: 38 passed (target directory outside the repository).
- `python scripts/check_official.py` in a copy of `data` and `docs/data`: 30 checks, all passed, output identical to the committed `official_check.json`.
- `npm run check:ui`: 61 of 61 checks passed (axe on 28 page states, keyboard pattern, marker names and Enter on a marker, site list, validation, solver status and cancel, a short real solve, labels, chart text, reduced motion, the Overview cost against the committed solver output, and every committed scenario on four tabs).
- The HiGHS cross-check scripts (`verify_bound.py`, `verify_depots.py`, `verify_highs.py`) were not rerun. They need HiGHS and long solves, and the engine, data and WASM file are byte-identical to the baseline.

### Known limitations

- Leaflet flow lines and site circles cannot take keyboard focus. The site list is the keyboard route to sites, and the flows CSV holds the flow lines.
- Accessibility was checked with axe-core and scripted keyboard and DOM checks. It was not tested with a screen reader, and visual review covered only a few window sizes.
- The input bounds in `RULES` (`docs/app.js`) only stop values that cannot be run. They are not engine validation, and the engine's own diagnostics still decide feasibility.
- The mass-balance screen is a necessary condition. A pass does not promise a feasible network.
- Cancel replaces the worker, so the next solve reloads `saf.wasm` from the browser cache.
- The address bar holds the tab only, not the selected scenario.
- Leaflet and Chart.js still load from cdnjs without integrity attributes, as before.
- `npm run check:ui` needs network access for those libraries and the map tiles, and a Chrome or Edge executable (set `CHROME_PATH` if it is not in a standard place).

### Future maintenance

- Cache-busting query strings are now `style.css?v=9`, `app.js?v=7` and `assistant.js?v=5`. Bump them with any edit.
- Evidence badges follow each scenario's `status`. A new scenario that rests on public data must be added to `REALITY_CHECK` in `docs/app.js`.
- Run `npm run check:ui` before publishing, because merging to `main` publishes the site at once.
- Revisit Astryx only if the whole front end moves to a component framework. A single island does not repay its size here.

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

Front-end checks (axe-core, keyboard, labels and a short real solve in a headless browser). They need Node 22 or later, a Chrome or Edge executable and network access. They change no file:

```bash
npm install
npm run check:ui
```

## Repository

```
crates/engine   solver, audit, baselines, diagnostics, decision support, 38 tests
crates/cli      batch runner and LP export
crates/wasm     browser entry points
docs            the deployed site, result JSON and reports
data            official datasets, OSRM road matrix, land mask
scripts         data fetch, HiGHS check, report and deck generators (Python), check_ui.mjs front-end checks
package.json    development-only dependencies for the front-end checks
```

The engine and app are Rust and JavaScript. Python is used only for data fetching, independent checks and document generation.

## Sources

Official Airbus problem statement and the update of 31 October 2026. Airports from the official CSV. Land mask from Natural Earth (public domain). Road distances from OpenStreetMap via OSRM, fetched by `scripts/build_data.py`. Real-uplift figures are fetched and recorded by `scripts/fetch_context.py`, with sources in `docs/data/context_check.json`, and appear only in a labelled reality check. Real-world evidence is cited in the Reports tab and the report. Formulation informed by Ng et al. (2018), Ng and Maravelias (2017), Li et al. (2026), Huang et al. (2019), Hernandez-Araujo et al. (2026), Castillo-Villar et al. (2026) and Keyvandarian et al. (2026).

Licence: MIT.
