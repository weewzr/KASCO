# Front-end review, November 2026

This file records the 2026-11 front-end review of the KASCO site. It was moved here unchanged in substance from the README. The review changed presentation only. No solver, parameter, result file, export or report generator was touched, and `git diff main --stat` on the review branch listed nothing under `crates`, `data`, `docs/data`, `docs/reports` or `docs/saf.wasm`.

## Original architecture

The served site in `docs/` is plain HTML, CSS and JavaScript with no bundler. `app.js` keeps one mutable `state` object and renders each tab by assigning template strings to `innerHTML`. Leaflet draws the two maps and Chart.js draws five canvases, both loaded from cdnjs. The Rust engine runs inside `worker.js` as `saf.wasm`, reached through one promise-keyed `rpc` function. `assistant.js` holds the optional language-model analyst. Figures shown before any run come from the committed JSON in `docs/data`.

## What changed

| Area | Change |
|---|---|
| Structure and keyboard | Skip link, a landmark around the tab strip, the WAI-ARIA tabs pattern (roving focus, arrow keys, Home and End, linked panels) and a tab hash in the address bar so a tab can be linked. |
| Names and live regions | Accessible names for the compare select and for the question and key fields. Run status and answers are live regions, and so is the selected-location panel. |
| Analyst panel | A labelled dialog that takes focus on open, closes on Escape and returns focus to its button. The key field, the fetch and the data sent are unchanged. |
| Map | Every focusable marker has a name. The legend explains the flow lines and the faded unused sites. A selected-location panel and a sortable, filterable site list select the same location as a marker click and open its popup, so the map has a keyboard route. |
| Charts and tables | Charts carry a text alternative that quotes their values where there are few. Scrollable tables become focusable named regions only when they overflow. Column headers have scopes, and links that open a new tab say so. |
| Motion and focus | `prefers-reduced-motion` turns off Chart.js animation and Leaflet zoom animation, and CSS transitions shrink to near zero. Every control has a visible focus ring. |
| Evidence labels | Each scenario carries badges for its strength of evidence: exact within target, feasible within a proven gap, refined coordinates (local refinement, no global proof), heuristic, reality check on public data, or no feasible network. Shape and words carry the meaning, and colour only supports it. A key on Overview, Scenario analysis and Evaluation explains them. |
| Source of an answer | Solver results, the rule-based Decision support tab and the optional language-model panel each carry their own tag. Model text is marked AI-written and not verified. |
| Scenario configuration | Inputs sit in groups with units. Each field has an inline message for a value that cannot be run, and a warning for a value outside the range the Airbus update gives. A mass-balance screen shows whether the demanded SAF can come from the biomass on offer. Changed inputs are outlined and counted, and reset restores every input including the selects and the run name. |
| Solver controls | Run is disabled while solving. A timer and progress bar show elapsed time against the limit, a status line announces the start and end, and Cancel stops the solve by replacing the worker, because the engine cannot be interrupted from inside it. |
| Comparison | Side by side adds annualised CapEx, fixed and variable OpEx, demand met, fleet, depot modules, optimality gap and evidence, marks truck-km as an estimate, and warns when a heuristic is compared with a proven result. |
| Feasibility summary | Overview shows demand met, the independent audit as a pass count, biomass used, highest refinery use and the gap, all read from existing solver fields. |

One displayed value was corrected. A custom run of a heuristic design (depots in the field) showed 0.00% under the label Proven gap. It now shows the distance above the proven bound, labelled as a heuristic with no proof, as the Overview already did.

## Astryx evaluation

Astryx (`@astryxdesign/core` 0.7.11, MIT, beta) was tried as an isolated island bundled with esbuild 0.28.2 (minified, subpath imports, React 19.3.1). The probes lived outside the repository and are not committed. Sizes were re-measured on the day of the change and mount times are the median of five mounts in headless Edge.

| Probe | JS raw, B | JS gzip, B | Added over React alone, gzip B | Mount, ms |
|---|---|---|---|---|
| React only | 223,507 | 69,049 | n/a | 62 |
| TabList, 7 tabs | 460,104 | 144,454 | 75,405 | 119.9 |
| Dialog, Button, Tooltip | 540,166 | 169,323 | 100,274 | 152.1 |

Astryx also ships prebuilt CSS: 269,224 B (39,947 B gzip) plus a 11,501 B reset and a 24,877 B neutral theme, 47,571 B gzip in all. For comparison, the whole of `app.js` is 25,248 B gzip after this change. The TabList island alone costs about three times that, and it would replace a seven-button strip that about 25 lines of vanilla JavaScript now handle. It would also add a second owner of the current-tab state next to `state.tab`, and its `light-dark()` theme tokens would need mapping onto the dark palette.

**Decision: no Astryx component is adopted, and no bundle is committed.** The review found no accessibility, consistency or maintainability gain that the existing stack could not deliver at a fraction of the cost, so the shipped site keeps its vanilla JavaScript.

| Component considered | Reason it was not migrated |
|---|---|
| TabList, Tab | Same pattern achieved in about 25 lines. Island adds 75 kB gzip JS, 48 kB gzip CSS and a second state owner. |
| Dialog, Drawer | Role, focus entry, Escape and focus return took about 10 lines. The island adds 100 kB gzip JS, and moving the key field into React would put the key handling at risk. |
| Table, Badge | Tables are static markup built from solver output. Rebuilding them as React data adds rewrite risk for no new behaviour. The badges cost under 1 kB of CSS. |
| Field, NumberInput, Selector | The form reads its values from the DOM in `formParams()`. A controlled React form would create a second source of truth. |
| Charts | `@astryxdesign/charts` is experimental and is not used in a scientific interface. Chart.js stays. |
| Map | Astryx has no map component. Leaflet stays. |

Dependencies added: none for the served site. `package.json` lists two development dependencies for the checks (`axe-core` 4.14.0 and `puppeteer-core` 24.43.1), locked in `package-lock.json`. Neither is served or bundled.

## Theming decisions

The dark palette and its CSS custom properties are unchanged apart from two tokens. `--bad` moved from `#e66767` to `#f08080`, which lifts the failed-status pill from 4.17:1 to 5.20:1 on `--surface-2` (6.12:1 on `--surface`). `--focus` (`#6fe3d6`, 10.3:1 on `--surface`) is new and drives the focus ring. Nothing else in the palette or in the shapes of tabs, buttons and forms changed.

## Measurements

How each number was obtained:

- Sizes: `git show <revision>:docs/app.js | gzip -9 | wc -c`, and the same for the other files, with line endings normalised to LF.
- axe-core 4.14.0: `npm run check:ui` for the branch. The baseline figures come from the same rules, pages and viewports run against commit 41194fa.
- Lighthouse 12.8.2: `lighthouse http://127.0.0.1:<port>/index.html [--preset=desktop] --port=<debugging port> --only-categories=performance,accessibility --output=json`, attached to an Edge started with `--headless=new --remote-debugging-port=<port>`. Each build was served by `python -m http.server` from its own `docs` folder (no compression): commit 41194fa and this branch.
- In-page timing: `renderOverview()` and `renderOptimise()` called eight times each in the page, a forced layout after every call, median reported.
- Island sizes: esbuild bundles of each probe with `--bundle --minify --format=iife --jsx=automatic`, then `gzip -9`. Mount time is `performance.now()` from the start of the bundle to the first element appearing in `#root` (a MutationObserver), in headless Edge, median of five.

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

The runs vary more between repeats of the same build than between the two builds. In the first batch the branch showed higher mobile blocking time (327 and 346 ms against 186 and 144 ms) and a higher desktop layout shift (0.091 against 0.074). The alternating batch gives medians of 238 ms for the baseline and 258 ms for the branch, and the same layout shift for both, so this sample can neither show nor rule out a small slowdown. What is certain is the size: transfer grows by 33 KiB uncompressed, which is the added code and markup. Timed in the page without throttling, rendering the Overview takes 16.0 ms before and 16.7 ms after (median of 8), and building the Optimisation form takes 0.5 ms before and 1.8 ms after. The Lighthouse accessibility score is 100 for both builds because it uses a subset of the axe rules, which is why the full axe run is reported below.

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

## Tests run

- `cargo test --release -p saf_engine`: 38 passed (target directory outside the repository).
- `python scripts/check_official.py` in a copy of `data` and `docs/data`: 30 checks, all passed, output identical to the committed `official_check.json`.
- `npm run check:ui`: 64 of 64 checks passed (axe on 28 page states and again with the analyst dialog open, keyboard pattern, marker names, Enter and Escape on a marker, site list, validation, solver status and cancel, a short real solve, labels, chart text, reduced motion, the Overview cost against the committed solver output, and every committed scenario on four tabs).
- The HiGHS cross-check scripts (`verify_bound.py`, `verify_depots.py`, `verify_highs.py`) were not rerun. They need HiGHS and long solves, and the engine, data and WASM file are byte-identical to the baseline.

## Known limitations

- Leaflet flow lines and site circles cannot take keyboard focus. The site list is the keyboard route to sites, and the flows CSV holds the flow lines.
- Accessibility was checked with axe-core and scripted keyboard and DOM checks. It was not tested with a screen reader, and visual review covered only a few window sizes.
- The input bounds in `RULES` (`docs/app.js`) only stop values that cannot be run. They are not engine validation, and the engine's own diagnostics still decide feasibility.
- The mass-balance screen is a necessary condition. A pass does not promise a feasible network.
- Cancel replaces the worker, so the next solve reloads `saf.wasm` from the browser cache.
- The address bar holds the tab only, not the selected scenario.
- Leaflet and Chart.js still load from cdnjs, now with Subresource Integrity (see the polish pass below). A new library version needs new hashes.
- `npm run check:ui` needs network access for those libraries and the map tiles, and a Chrome or Edge executable (set `CHROME_PATH` if it is not in a standard place).

## Future maintenance

- Cache-busting query strings are now `tokens.core.css?v=1`, `style.css?v=10`, `app.js?v=9` and `assistant.js?v=6`. Bump them with any edit. The result JSON is cached normally and carries `DATA_V` in `app.js` (currently 1): bump it whenever any file in `docs/data` changes, or a visitor can keep a stale result for the cache lifetime.
- When Leaflet or Chart.js is upgraded, recompute the `integrity` hashes from the exact files: `curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`, and compare with the sha512 that the cdnjs API lists for the file.
- Evidence badges follow each scenario's `status`. A new scenario that rests on public data must be added to `REALITY_CHECK` in `docs/app.js`.
- Pull requests run `.github/workflows/ci.yml` (engine tests, official-value check, the 64 browser checks). Run `npm run check:ui` before publishing anyway, because merging to `main` publishes the site at once and the workflow does not deploy.
- Revisit Astryx only if the whole front end moves to a component framework. A single island does not repay its size here.

## Layout polish and CI pass (branch `fix/layout-polish-and-ci`)

Targeted fixes to the live site. The dark teal identity, the tagline, the evidence badges, the source tags, the proven-gap wording, the limits and assumption registers, every number and the in-browser solver are unchanged. No Rust code, no file in `docs/data` and not `docs/saf.wasm` changed.

| Defect (Stage A audit) | Fix |
|---|---|
| Side by side table clipped on desktop, value columns off-screen on a phone | The card spans the full width of the grid, and so does the chart card below it. At 720 px and narrower each measure becomes a stacked block (label, then Selected, Compared and Change with their own captions, taken from `data-label` attributes). The visually hidden header row is kept for screen readers. |
| Map legend covered about 40 percent of a phone map | The legend is a `<details>` titled "Legend". It starts closed at 720 px and narrower (1.7 percent of the map) and open on larger screens, and a viewer can toggle it from the keyboard. The sortable site list is unchanged. |
| Floating Ask button covered the footer and last rows | The footer has 84 px of bottom padding, so at the end of every tab the button sits below the last line of text (checked by measuring the footer text range against the button). |
| Flat, small type scale | Data text is at least 13 px (was 11 to 12.5 px in places): table 14, headers 13.5, pills and badges 13, notes 13.5, tile captions 13, footer 13.5, legend and popups 13, form units 13. h2 is 20 px, h3 16 px at weight 650, form legends 15 px. Body stays 15 px, tile values 24 px. The smallest rendered text on the Scenario analysis tab, header and footer is 12.5 px (source tags). |
| White text on teal | The audit computed 2.56:1. No control used that pair (buttons are white on the forest green `#1f7a4d`, 5.32:1). The token `--on-teal: #0a1626` (7.09:1 on `#19b5a5`) is defined for any future teal fill. One real low pair was found and fixed: the white airport code on the blue marker (3.64:1) is now navy (4.99:1). |
| No favicon, theme colour or Open Graph tags | `favicon.svg`, `theme-color`, `og:*` and a Twitter card tag, and a 1200 x 630 `og.png` with the name and a plain description only. The image is not loaded by the page. |
| No integrity on cdnjs files | `integrity` (sha384), `crossorigin="anonymous"` and `referrerpolicy="no-referrer"` on Leaflet CSS, Leaflet JS and Chart.js. Hashes were computed from the exact downloaded files and their sha512 matched the cdnjs API listing. |
| Result JSON fetched with `no-store` | `fetch("data/<name>.json?v=" + DATA_V)` with the browser's normal caching. |
| No shared tokens | `docs/tokens.core.css` (version 1.0.0, spacing, radii, motion, focus width, minimum sizes, Okabe-Ito palette) is loaded before `style.css`; it is the unchanged canonical copy from weewzr/weewzr (variable names `--text-min`, `--tick-min`, `--touch-min`, `--measure`, rem spacing), and `style.css` does not use the minimum-size tokens. `style.css` uses its focus width and offset and two radii where the values were identical, so the look is unchanged. |

Contrast of the token pairs involved (WCAG 2.x relative luminance, computed from the hex values): white on forest 5.32, navy on teal 7.09, navy on airport blue 4.99, teal on page background 7.09, muted on surface 6.52, muted on surface 2 5.54, link on surface 7.32, warning on surface 2 5.93, failure on surface 2 5.20, good on surface 2 5.80. Every pair is at least 4.5:1.

Page weight, cold load of the Overview tab in headless Edge against a local server without compression (`Network.loadingFinished` encoded bytes, all requests including cdnjs and map tiles): 403,724 B in 29 requests before, 408,792 B in 30 requests after. Own first-load code, gzip with LF endings: HTML 1,165 to 1,602 B, CSS 3,919 to 4,294 B plus 634 B for `tokens.core.css`, `app.js` 25,556 to 25,776 B, `assistant.js` 8,058 B unchanged, and a 225 B favicon. The total goes from 38,698 B to 40,589 B. There is no new third-party host: the only external host is still cdnjs (plus the map tiles). The favicon request that returned 404 now succeeds.

Continuous integration: `.github/workflows/ci.yml` runs on pull requests only, in three jobs. `cargo test --release -p saf_engine --locked`; `scripts/check_official.py` followed by a diff of `docs/data/official_check.json`; and `npm run check:ui` in the runner's Chrome (`CHROME_PATH`, with `--no-sandbox` added by `check_ui.mjs` when `CI` is set). It does not deploy, and GitHub Pages keeps publishing `docs/` from `main` through its own workflow. The HiGHS cross-check scripts are not in CI because they need the full Python stack and long solves.

Checks run for this pass, locally: `cargo test --release -p saf_engine` 38 passed; `check_official.py` in a Python 3.12 virtual environment 30 of 30 with the committed output unchanged; `npm ci` and `npm run check:ui` with Edge 64 of 64. The workflow itself has not run on GitHub yet: it only triggers on a pull request. No horizontal scroll at 390 px on any of the seven tabs, one h1 per page, every focus stop shows a 2 px ring, and reduced motion still shortens transitions to about 0.001 ms.

## Tick labels, map markers and CI hardening (follow-up to the independent check)

- The y-axis labels of the two horizontal bar charts are now 12 px (the tick minimum). Labels longer than 44 characters, or 24 below 520 px viewport width, are cut with an ellipsis; the tooltip keeps the full name.
- The airport markers on the map are 34 px with a 12 px bold code. This is glyph-like map labelling; it stays below the 13 px text minimum on purpose and its contrast is 4.99:1.
- The pull-request workflow pins each action to a full commit SHA (tag in a comment), does not persist checkout credentials, has a 20-minute timeout per job and pins the three Python packages.
