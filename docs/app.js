"use strict";
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : Number(x).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d }));
const usd = (x, d = 1) => `USD ${fmt(x, d)}M`;
const COL = { s1: "#3987e5", s2: "#d95926", s3: "#199e70", s4: "#c98500", text: "#ffffff", text2: "#cfdbe3", muted: "#94a9b8", grid: "#27445f" };
const SURFACE = "#10233a";
const ROLE = { farm: COL.s3, depot: COL.s4, ref: COL.s2, air: COL.s1 };
const AIRPORTS = ["PNK", "PKN", "BPN", "TRK"];
const REDUCED = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
// Scenarios built on public data. The assumption register labels them as reality checks only.
const REALITY_CHECK = new Set(["road_distance", "real_blend"]);
// Strength of the evidence behind a result. Shape and words carry the meaning, colour only supports it.
const EV = {
  exact: ["exact", "Exact within target", "The solver proved the result lies within its target gap."],
  bound: ["bound", "Feasible within a proven gap", "Feasible, with a proven lower bound on cost. The gap is the distance to that bound."],
  local: ["local", "Refined coordinates: local refinement, no global proof", "Plants were moved off the candidate sites by a local search, so the coordinates are a local optimum."],
  heur: ["heur", "Heuristic, no optimality proof", "A rule-based design. It is feasible and audited, but no bound shows it is the cheapest."],
  est: ["est", "Reality check, public data", "Uses public data outside the official inputs. Treat it as an unverified estimate."],
  none: ["none", "No feasible network", "The solver found no network that meets every constraint."],
};
const TABS = [["overview", "Overview"], ["map", "Network map"], ["optimise", "Optimisation"], ["scenarios", "Scenario analysis"], ["insights", "Decision support"], ["evaluation", "Evaluation"], ["reports", "Reports"]];
const DEFAULTS = {
  demand: [300, 300, 300, 300], demand_multiplier: 1, biomass_multiplier: 1, yield_saf: 0.2, retention: 1, depot_mode: "colocated", field_radius_km: 60,
  depot_capex: [2.25, 4.5], depot_cap: [150, 300], depot_var: [5, 4], refinery_capex: [480, 765], refinery_cap: [500, 1087], refinery_var: [60, 55],
  tariff_fd: 0.1, tariff_dr: 0.12, tariff_ra: 0.08, distance_basis: "great_circle", road_factor: 1.3, capex_years: 20, fixed_opex_frac: 0.05, max_refineries: 0, forbid: [], refine: true, time_limit_s: 12, gap_target: 0.002,
};
const ASSUMPTIONS = [
  ["Biomass per site", "80 sites, 6,800 kt", "Official", "Airbus CSV", "Validated: 22.84 to 99.90 kt per site, sum 6,800.00 kt."],
  ["Capacity basis", "Biomass intake", "Official", "Update, 31 Oct 12:45", "Applies to depots and refineries."],
  ["Yield", "0.20 t SAF per t biomass", "Official", "Update, 31 Oct 12:45", "The update places this inside a 15 to 25% range."],
  ["Depot mass loss", "0%", "Official", "Update, 31 Oct 12:45", "Moisture loss ignored by instruction."],
  ["Demand", "300 kt SAF per airport per year", "Official", "challenge3_airports_4.csv", "1,200 kt total, needs 6,000 kt biomass."],
  ["Cost basis", "One year, CapEx / 20, fixed OpEx 5%", "Official", "Update, 31 Oct 12:45", "No interest."],
  ["Variable OpEx", "Depot 5 / 4, refinery 60 / 55 USD/t in", "Official", "challenge3_parameters.xlsx", "Small / large."],
  ["Distance", "Great-circle x 1.3", "Official", "Update, 31 Oct 12:45", "Our OSRM sample suggests 1.9 in practice, tested as a scenario."],
  ["Tarakan leg", "Barge at 0.08 USD/t/km", "Official", "Update, 31 Oct 12:45", "Same tariff, no fixed cost."],
  ["Refinery candidates", "80 biomass sites, PNK, PKN, BPN", "Ours", "Modelling choice", "Tarakan is excluded because biomass cannot reach the island. Continuous refinement then moves plants off these points."],
  ["Depot placement", "At the refinery", "Derived", "Triangle inequality and HiGHS check", "Needs second-leg tariff x retention at or above the first-leg tariff. HiGHS confirmed it on the base fleet with depots free to go anywhere."],
  ["One refinery per site", "At most one", "Ours", "Modelling choice", "Depot modules may share a site."],
  ["Real jet uplift", "About 100 kt/yr across the four", "Public", "Pertamina press 2024; DGCA and BPS passengers", "Reality check only. PKN and TRK are scaled from passengers."],
  ["Blend reality check", "5% of real uplift", "Public", "Singapore 3 to 5% by 2030", "Reality check only. Indonesia's 1% from 2027 covers Jakarta and Bali departures."],
  ["Road distance check", "OSRM road km", "Public", "OpenStreetMap via OSRM, scripts/build_data.py", "Reality check only."],
];

const EVIDENCE = [
  ["Airbus's Singapore office was reported working with IPB University on Indonesian biomass, logistics, supply chain mapping and factory siting to cut transport cost.", "QC Intelligence", "https://www.qcintel.com/biofuels/article/airbus-and-indonesia-team-up-on-biomass-based-saf-reports-46429.html", "Aug 2025", "Secondary report"],
  ["SAF was about 1.9 Mt in 2025, only 0.6% of jet fuel.", "IATA", "https://www.iata.org/en/pressroom/2025-releases/2025-12-09-04/", "9 Dec 2025", "Industry body"],
  ["Indonesia's 1% SAF requirement from 2027 covers international flights from its two busiest airports, so Kalimantan's airports fall outside it.", "Fuels and Lubes", "https://www.fuelsandlubes.com/indonesia-to-require-1-saf-blend-from-2027/", "Jul 2026", "Trade press"],
  ["A gasification Fischer-Tropsch plant failed on equipment and liquidity, showing how exposed these projects are.", "Waste Dive", "https://www.wastedive.com/news/fulcrum-bioenergy-chapter-11-bankruptcy-nevada/726555/", "Sep 2024", "Trade press"],
  ["Pertamina's first SAF was used cooking oil co-processed at Cilacap, about 32 kL for Pelita Air. Biomass-based routes remain ahead.", "Hydrocarbon Engineering", "https://www.hydrocarbonengineering.com/clean-fuels/13082025/kilang-pertamina-delivers-saf/", "Aug 2025", "Trade press"],
  ["Southeast Asian feedstock could yield about 45.7 Mt of SAF a year by 2050, with palm residues at 11.8%.", "RSB and Boeing", "https://rsb.org/2024/09/03/rsb-launches-study-with-boeing-on-sustainable-feedstock-potential-in-southeast-asia/", "Sep 2024", "Industry study"],
  ["An ASEAN study found Fischer-Tropsch and Alcohol-to-Jet the most viable routes for regional wastes.", "GHD", "https://ghd.com/projects/promoting-sustainable-aviation-fuels-across-southeast-asian-nations", "2025", "Industry study"],
  ["A preliminary national estimate puts Indonesian SAF potential near 37 million m3 a year, with palm residues about 77%.", "Inayah et al.", "https://journals.aau.dk/index.php/sepm/article/view/10615", "2026", "Journal article"],
  ["Biomass transport was 13.5 to 30% of plant supply cost in one Serbian case, depending on site and mode.", "UNS repository", "https://open.uns.ac.rs/handle/123456789/1798", "Not confirmed", "Study-specific"],
  ["Central Kalimantan palm freight split about evenly between road and river, with intermodal routes the cheapest generalised option.", "Jurnal Transportasi", "https://journal.unpar.ac.id/index.php/jurnaltransportasi/article/view/412", "About 2010 to 2012", "Journal article, dated"],
];

const state = { keys: [], sols: {}, names: {}, cur: "official_base", other: "field_depots", net: null, base: null, ladder: null, sens: null, highs: null, charts: {}, maps: {}, chat: [], customN: 0, siteSort: { k: "id", dir: 1 }, siteRole: "all", sel: null };

const pending = new Map();
let rpcId = 0;
function makeWorker() {
  const w = new Worker("worker.js?v=4");
  w.onmessage = (e) => {
    const { id, ok, text, error } = e.data;
    const done = pending.get(id);
    if (!done) return;
    pending.delete(id);
    ok ? done.res(JSON.parse(text)) : done.rej(new Error(error));
  };
  return w;
}
let worker = makeWorker();
// The engine cannot be interrupted from inside the worker, so cancelling replaces the worker.
function cancelSolve() {
  worker.terminate();
  worker = makeWorker();
  pending.forEach((p) => p.rej(new Error("cancelled")));
  pending.clear();
}
const rpc = (cmd, payload) => new Promise((res, rej) => {
  const id = ++rpcId;
  pending.set(id, { res, rej });
  worker.postMessage({ id, cmd, body: JSON.stringify(payload) });
});

async function getJson(name) {
  const r = await fetch(`data/${name}.json`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

function sol() { return state.sols[state.cur]; }

function statusPill(s) {
  const map = { optimal: ["good", "Optimal within target"], feasible_gap: ["warn", "Feasible, gap reported"], heuristic: ["warn", "Heuristic, no proof"], infeasible: ["bad", "Infeasible"] };
  const [c, t] = map[s.status] || ["", s.status];
  return `<span class="pill ${c}">${t}</span>`;
}

function evBadge(k) { return `<span class="ev ${EV[k][0]}" title="${esc(EV[k][2])}">${esc(EV[k][1])}</span>`; }

function evidenceKinds(s) {
  const out = [s.status === "optimal" ? "exact" : s.status === "feasible_gap" ? "bound" : s.status === "heuristic" ? "heur" : "none"];
  if (s.refineries.length && s.params.refine) out.push("local");
  if (REALITY_CHECK.has(s.key)) out.push("est");
  return out;
}

function evidenceHtml(s) { return `<span class="evs">${evidenceKinds(s).map(evBadge).join("")}</span>`; }

// The key that separates strength of evidence from the source of an answer.
function keyHtml(open) {
  return `<details class="card keybox" id="resultKey"${open ? " open" : ""}><summary>How to read the result labels</summary>
  <div class="keygrid" style="margin-top:10px">
    <div><h3>Strength of the evidence</h3><dl>${["exact", "bound", "local", "heur", "est"].map((k) => `<dt>${evBadge(k)}</dt><dd>${esc(EV[k][2])}</dd>`).join("")}</dl></div>
    <div><h3>Where an answer comes from</h3><dl>
      <dt><span class="src-tag solver">Solver result</span></dt><dd>Deterministic. Computed by the Rust engine on the stated inputs and checked by a separate audit module. Used on Overview, Network map, Scenario analysis and Evaluation.</dd>
      <dt><span class="src-tag rules">Rule-based recommendation</span></dt><dd>Decision support tab. Questions route by fixed rules to solver records, with no language model, and each answer lists the fields it read.</dd>
      <dt><span class="src-tag ai">Language-model explanation</span></dt><dd>Optional Ask Claude panel. Written by a language model from a snapshot of solver data. Lines with a figure that is not in the data are removed. The wording and the reasoning are not verified.</dd>
    </dl></div>
  </div></details>`;
}

function chartLabel(id, cfg) {
  const el = document.getElementById(id);
  const card = el && el.closest(".card");
  const h = card && card.querySelector("h3");
  const title = h ? h.textContent : "Chart";
  const labels = (cfg.data && cfg.data.labels) || [];
  const sets = (cfg.data && cfg.data.datasets) || [];
  if (labels.length && labels.length * sets.length <= 24) {
    // Semicolons separate the items because category names and formatted numbers can contain commas.
    return `${title}. Categories: ${labels.join("; ")}. ${sets.map((d) => `${d.label}: ${d.data.map((v) => (v === null || v === undefined ? "n/a" : fmt(v, 1))).join("; ")}`).join(". ")}.`;
  }
  if (labels.length) return `${title}. Bar chart with ${labels.length} categories and ${sets.length} series: ${sets.map((d) => d.label).join(", ")}.`;
  return `${title}. Line chart of ${sets.reduce((a, d) => a + d.data.length, 0)} points.`;
}

function chart(id, cfg) {
  if (state.charts[id]) state.charts[id].destroy();
  const el = document.getElementById(id);
  if (!el) return;
  Chart.defaults.color = COL.text2;
  Chart.defaults.font.family = 'Inter, "Segoe UI", Arial, sans-serif';
  if (REDUCED) cfg.options = Object.assign({}, cfg.options, { animation: false });
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", chartLabel(id, cfg));
  state.charts[id] = new Chart(el, cfg);
}

// Idempotent accessibility pass over rendered markup: column scopes, scrollable regions, new-tab links.
function markScrollable() {
  document.querySelectorAll(".scroll").forEach((el) => {
    const over = el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1;
    if (over) {
      const sec = el.closest("section");
      const h = el.closest(".card") && el.closest(".card").querySelector("h3");
      const name = (h && h.textContent) || (sec && sec.querySelector("h2") && sec.querySelector("h2").textContent) || "Table";
      el.tabIndex = 0;
      el.setAttribute("role", "region");
      el.setAttribute("aria-label", `${name.trim()}, scrollable`);
    } else if (el.getAttribute("role") === "region") {
      el.removeAttribute("tabindex");
      el.removeAttribute("role");
      el.removeAttribute("aria-label");
    }
  });
}

function enhance() {
  document.querySelectorAll("main th:not([scope])").forEach((th) => th.setAttribute("scope", "col"));
  document.querySelectorAll('main a[target="_blank"]:not([data-nt])').forEach((a) => {
    a.dataset.nt = "1";
    a.insertAdjacentHTML("beforeend", '<span class="sr"> (opens in a new tab)</span>');
  });
  markScrollable();
}

let enhanceQueued = false;
function queueEnhance(muts) {
  if (muts && muts.every((m) => m.target.closest && m.target.closest(".mapbox"))) return;
  if (enhanceQueued) return;
  enhanceQueued = true;
  requestAnimationFrame(() => { enhanceQueued = false; enhance(); });
}

function tile(v, l) { return `<div class="tile"><b>${v}</b><span>${l}</span></div>`; }

function renderOverview() {
  const s = sol();
  const el = $("#overview");
  if (!s.refineries.length) {
    el.innerHTML = `<h2>${esc(s.params.name)}</h2><div class="card"><div class="evs">${statusPill(s)}${evidenceHtml(s)}</div><p>${esc(s.message)}</p>${diagHtml(s)}</div>${keyHtml(false)}`;
    return;
  }
  const k = s.kpis, c = s.costs;
  const b = state.sols.official_base;
  const f = state.sols.field_depots;
  el.innerHTML = `
  <div class="row between"><h2>${esc(s.params.name)} <span class="src-tag solver">Solver result</span></h2><div class="evs">${statusPill(s)}${evidenceHtml(s)}</div></div>
  <div class="tiles">
    ${tile(usd(s.objective), "Total annual cost")}
    ${tile(`USD ${fmt(k.unit_cost_usd_t)}/t`, "Cost per tonne SAF")}
    ${tile(`${k.n_refineries} <small>(${k.n_refineries_large}L, ${k.n_refineries_small}S)</small>`, "Refineries")}
    ${tile(`${k.n_depots} <small>(${k.n_depots_large}L, ${k.n_depots_small}S)</small>`, "Depots")}
    ${tile(`${fmt(k.biomass_used_kt)} kt`, `Biomass used, ${fmt(100 * k.biomass_used_share, 1)}% of supply`)}
    ${tile(`${fmt(k.saf_kt)} kt`, "SAF delivered per year")}
    ${tile(`${fmt(100 * k.fill_rate, 1)}%`, "Demand met")}
    ${s.gap === null ? tile(`${fmt(100 * s.gap_to_bound, 2)}%`, "Above proven bound, heuristic") : tile(`${fmt(100 * s.gap, 2)}%`, "Proven gap on candidate sites")}
  </div>
  ${feasHtml(s)}
  ${keyHtml(true)}
  <div class="grid2">
    <div class="card"><h3>Where the money goes</h3><div class="chart short"><canvas id="costStack"></canvas></div>
      <p class="note">CapEx ${usd(c.capex_total, 0)}, straight-line over ${s.params.capex_years} years. Refineries are ${fmt(100 * c.capex_refineries / c.capex_total, 1)}% of it.</p></div>
    <div class="card"><h3>What this tool is for</h3>
      <p>A SAF network planner must decide where to commit about ${usd(b.costs.capex_total / 1000, 1).replace("M", "B")} of plant capital before engineering starts. Today that means comparing a few hand-drawn layouts in a spreadsheet. Here a planner changes an assumption, reruns the search and sees the network, the cost and every constraint check.</p>
      <p class="note">The planner decides. The tool shows cost, flows and capacity, and it declines questions outside that scope.</p></div>
  </div>
  <div class="card"><h3>What the numbers say</h3>
    <ul>
      <li>Refineries drive the decision. At 6,000 kt of intake, ${b.kpis.n_refineries_large} large plants is the cheapest fleet, and transport is only ${fmt(100 * b.costs.logistics_total / b.costs.total_annual, 1)}% of cost.</li>
      <li>Depots sit at the refineries under these inputs, because the second leg costs more per tonne-km and depots lose no mass. On the base fleet HiGHS confirmed no cheaper depot layout exists. Real wet feedstock could change this.</li>
      <li>Field depots cost ${usd(f.objective - b.objective)} more per year (+${fmt(100 * (f.objective / b.objective - 1), 1)}%). They move ${fmt(100 * (f.kpis.tonne_km_bn / b.kpis.tonne_km_bn - 1), 1)}% more tonne-km but need an estimated ${fmt(100 * (1 - f.kpis.truck_km_m / b.kpis.truck_km_m), 0)}% fewer truck-km, since larger trucks carry the long leg. That is the trade-off to weigh.</li>
      <li>The network costs ${usd(state.base.greedy.saving_usd_m, 0)} to ${usd(state.base.airport_first.saving_usd_m, 0)} a year less than two simple heuristic layouts. A strong k-means benchmark, handed the same six-plant fleet and our refinement, reaches our network at best and sits ${usd(state.base.kmeans.median_saving_usd_m)} above it at median, because transport is a small share of cost. KASCO's value is the proven bound, the fleet and size choice in each scenario, and the limits it exposes.</li>
      <li>${b.kpis.sites_skipped.length} of 80 sites are left unused, which accounts for the ${fmt(6800 - b.kpis.biomass_used_kt)} kt not needed.</li>
    </ul></div>
  <div class="card"><h3>Why this is a real planning problem</h3>
    <ul>${EVIDENCE.slice(0, 4).map((e) => `<li>${e[0]} <a href="${e[2]}" target="_blank" rel="noopener">${esc(e[1])}</a></li>`).join("")}</ul>
    <p class="note">The 80 biomass sites, the 300 kt demand and all costs are official challenge inputs, and they are modelling values. Sources and their limits are under Reports.</p></div>`;
  chart("costStack", {
    type: "bar",
    data: { labels: ["Annual cost"], datasets: [
      { label: "Annualised CapEx", data: [c.annual_capex], backgroundColor: COL.s1 },
      { label: "Fixed OpEx", data: [c.opex_fixed], backgroundColor: COL.s2 },
      { label: "Variable OpEx", data: [c.opex_variable], backgroundColor: COL.s3 },
      { label: "Transport", data: [c.logistics_total], backgroundColor: COL.s4 },
    ].map((d) => ({ ...d, borderColor: SURFACE, borderWidth: 2, barThickness: 34 })) },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } }, tooltip: { callbacks: { label: (t) => `${t.dataset.label}: USD ${fmt(t.raw, 1)}M (${fmt(100 * t.raw / c.total_annual, 1)}%)` } } },
      scales: { x: { stacked: true, grid: { color: COL.grid }, title: { display: true, text: "USD M per year" } }, y: { stacked: true, display: false } } },
  });
}

// Feasibility and constraint summary, built only from fields the solver already returns.
function feasHtml(s) {
  const v = s.validation || [];
  const passed = v.filter((c) => c.passed).length;
  const k = s.kpis;
  const mu = Math.max(0, ...s.refineries.map((r) => r.utilisation));
  const row = (l, val) => `<li><span>${l}</span><b>${val}</b></li>`;
  return `<div class="card"><h3>Feasibility and constraint summary</h3><ul class="sumlist">
    ${row("Demand met", `${fmt(100 * k.fill_rate, 1)}%`)}
    ${row("Independent constraint audit", v.length ? `<span class="pill ${passed === v.length ? "good" : "bad"}">${passed === v.length ? "Pass" : "Fail"}</span> ${passed} of ${v.length} checks` : "n/a")}
    ${row("Biomass used", `${fmt(k.biomass_used_kt)} of ${fmt(k.biomass_available_kt)} kt`)}
    ${row("Highest refinery use", `${fmt(100 * mu, 1)}%`)}
    ${row("Optimality gap", gapText(s))}
    ${row("Plants and depots", `${k.n_refineries} refineries, ${k.n_depots} depot modules`)}
  </ul><p class="note">These are the solver's own records. Checks are recomputed from the flows by a separate module, listed in full under Evaluation.</p></div>`;
}

function diagHtml(s) {
  if (!s.diagnostics || !s.diagnostics.length) return "";
  return `<table><tr><th>Limit</th><th class="n">Available</th><th class="n">Required</th><th>Why</th><th>What would fix it</th></tr>${s.diagnostics.map((f) => `<tr><td>${esc(f.limit)}</td><td class="n">${fmt(f.available)}</td><td class="n">${fmt(f.required)}</td><td>${esc(f.reason)}</td><td>${esc(f.fix)}</td></tr>`).join("")}</table>`;
}

function popTable(rows) { return `<table class="pop-t">${rows.map(([a, b]) => `<tr><td>${a}</td><td>${b}</td></tr>`).join("")}</table>`; }
function bar(u) { return `<div class="bar"><i style="width:${Math.min(100, 100 * u).toFixed(0)}%"></i></div>`; }

function initMap(id) {
  if (state.maps[id]) return state.maps[id];
  const m = L.map(id, { zoomControl: true, zoomAnimation: !REDUCED, fadeAnimation: !REDUCED, markerZoomAnimation: !REDUCED }).setView([-0.9, 113.6], 6);
  // Leaflet closes a popup on Escape only while the map container itself has focus. This also covers a focused marker.
  m.getContainer().addEventListener("keydown", (e) => { if (e.key === "Escape") m.closePopup(); });
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", { attribution: "Tiles &copy; Esri, HERE, Garmin, OpenStreetMap contributors", maxZoom: 12 }).addTo(m);
  const lg = L.control({ position: "bottomleft" });
  lg.onAdd = () => {
    const e = L.DomUtil.create("div", "legend");
    e.setAttribute("role", "group");
    e.setAttribute("aria-label", "Map legend");
    e.innerHTML = `<b>Places</b><br><i style="background:${ROLE.farm};border-radius:50%"></i>Biomass site, faded if unused<br><i style="background:${ROLE.depot};transform:rotate(45deg)"></i>Depot<br><i style="background:${ROLE.ref}"></i>Refinery<br><i style="background:${ROLE.air};border-radius:50%"></i>Airport<hr><b>Flows, line width shows kt per year</b><br><span class="ln" style="border-color:${ROLE.farm}"></span>Biomass, site to depot<br><span class="ln" style="border-color:${ROLE.depot}"></span>Biomass, depot to refinery<br><span class="ln" style="border-color:${ROLE.air}"></span>SAF, refinery to airport`;
    L.DomEvent.disableClickPropagation(e);
    return e;
  };
  lg.addTo(m);
  state.maps[id] = { map: m, groups: [], control: null };
  return state.maps[id];
}

function drawNetwork(id, s) {
  const h = initMap(id);
  h.groups.forEach((g) => h.map.removeLayer(g));
  if (h.control) h.map.removeControl(h.control);
  const lay = { farm: L.layerGroup(), depot: L.layerGroup(), ref: L.layerGroup(), air: L.layerGroup(), fd: L.layerGroup(), dr: L.layerGroup(), ra: L.layerGroup() };
  const pos = s.node_coords && Object.keys(s.node_coords).length ? s.node_coords : state.net.coords;
  const used = {};
  s.flows_fd.forEach((f) => { used[f.src] = (used[f.src] || 0) + f.kt; });
  const mx = Math.max(1e-9, ...s.flows_fd.map((f) => f.kt), ...s.flows_dr.map((f) => f.kt));
  const mxs = Math.max(1e-9, ...s.flows_ra.map((f) => f.kt));
  const w = (kt, m) => Math.max(1, Math.min(7, 0.8 + 6 * Math.sqrt(kt / m)));
  const line = (f, c, g, leg, m) => {
    const a = pos[f.src], b = pos[f.dst];
    if (!a || !b || f.km <= 0) return;
    L.polyline([a, b], { color: c, weight: w(f.kt, m), opacity: 0.72 }).bindPopup(`<div class="pop-h">${f.src} to ${f.dst}</div><div class="pop-s">${leg}${f.mode === "truck then barge" ? ", barge on the last leg" : ""}</div>${popTable([["Flow", `${fmt(f.kt, 1)} kt/yr`], ["Distance", `${fmt(f.km)} km`], ["Cost", `USD ${fmt(f.usd_m, 2)}M/yr`]])}`).addTo(g);
  };
  s.flows_fd.forEach((f) => line(f, ROLE.farm, lay.fd, "Biomass, site to depot", mx));
  s.flows_dr.forEach((f) => line(f, ROLE.depot, lay.dr, "Pre-processed biomass, depot to refinery", mx));
  s.flows_ra.forEach((f) => line(f, ROLE.air, lay.ra, "SAF, refinery to airport", mxs));
  // Every selectable location is registered so the site list and the details panel reach the same popup.
  const reg = {};
  h.reg = reg;
  const track = (key, title, content, mk) => {
    reg[key] = { mk, title, content };
    if (id === "map1") mk.on("popupopen", () => showDetail(key, false));
  };
  state.net.sites.forEach((x) => {
    const q = used[x.id] || 0;
    const content = `<div class="pop-h">${x.id}</div><div class="pop-s">${esc(x.district)}, ${esc(x.province)}</div>${popTable([["Available", `${fmt(x.kt, 1)} kt/yr`], ["Shipped", `${fmt(q, 1)} kt/yr`]])}${bar(q / x.kt)}`;
    const mk = L.circleMarker([x.lat, x.lon], { radius: 2.5 + x.kt / 20, color: ROLE.farm, weight: 1, fillColor: ROLE.farm, fillOpacity: q > 0 ? 0.8 : 0.16 }).bindPopup(content).addTo(lay.farm);
    track(`site:${x.id}`, `Biomass site ${x.id}`, content, mk);
  });
  const byId = {};
  s.depots.forEach((d) => { (byId[d.id] = byId[d.id] || []).push(d); });
  Object.entries(byId).forEach(([id2, list]) => {
    const co = list[0].colocated;
    const n = list.reduce((a, d) => a + d.count, 0);
    const txt = list.map((d) => `${d.count} ${d.size}`).join(", ");
    const thr = list.reduce((a, d) => a + d.throughput, 0), cap = list.reduce((a, d) => a + d.capacity, 0);
    const pop = `<div class="pop-h">${id2} depots</div><div class="pop-s">${txt}, ${list[0].lat.toFixed(4)}, ${list[0].lon.toFixed(4)}${co ? ", at the refinery" : ""}</div>${popTable([["Capacity", `${fmt(cap)} kt/yr`], ["Throughput", `${fmt(thr, 1)} kt/yr`], ["Utilisation", `${fmt(100 * thr / cap, 1)}%`]])}${bar(thr / cap)}`;
    const size = list.some((d) => d.size === "large") ? 9 : 6;
    for (let i = 0; i < (co ? n : 1); i++) {
      const ang = (2 * Math.PI * i) / Math.max(1, n), r = co ? 20 : 0;
      const ax = size - r * Math.cos(ang), ay = size - r * Math.sin(ang);
      const dt = `Depot at ${id2}: ${txt}`;
      const mk = L.marker([list[0].lat, list[0].lon], { title: dt, alt: dt, keyboard: i === 0, icon: L.divIcon({ className: "", html: `<div style="width:${size * 1.4}px;height:${size * 1.4}px;background:${ROLE.depot};border:1px solid #fff;transform:rotate(45deg)"></div>`, iconSize: [size * 2, size * 2], iconAnchor: [ax, ay] }) }).bindPopup(pop).addTo(lay.depot);
      if (i === 0) track(`depot:${id2}`, `Depot at ${id2}`, pop, mk);
    }
  });
  s.refineries.forEach((r) => {
    const z = r.size === "large" ? 11 : 8;
    const d = (byId[r.id] || []).map((x) => `${x.count} ${x.size}`).join(", ");
    const content = `<div class="pop-h">${r.id} refinery</div><div class="pop-s">${r.size}, ${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}<br>${esc(r.near)}</div>${popTable([["Capacity", `${fmt(r.capacity)} kt/yr`], ["Biomass in", `${fmt(r.biomass_in, 1)} kt/yr`], ["SAF out", `${fmt(r.saf_kt, 1)} kt/yr`], ["Utilisation", `${fmt(100 * r.utilisation, 1)}%`]].concat(d ? [["Depots here", d]] : []))}${bar(r.utilisation)}`;
    const rt = `Refinery ${r.id}, ${r.size}`;
    const mk = L.marker([r.lat, r.lon], { zIndexOffset: 900, title: rt, alt: rt, icon: L.divIcon({ className: "", html: `<div style="width:${z * 2}px;height:${z * 2}px;border-radius:3px;background:${ROLE.ref};border:2px solid #fff"></div>`, iconSize: [z * 2, z * 2], iconAnchor: [z, z] }) }).bindPopup(content).addTo(lay.ref);
    track(`ref:${r.id}`, rt, content, mk);
  });
  state.net.airports.forEach((a, i) => {
    const content = `<div class="pop-h">${esc(a.name)}</div><div class="pop-s">${esc(a.city)}${i === 3 ? ", island, barge last leg" : ""}</div>${popTable([["SAF demand", `${fmt(s.kpis.demand_by_airport ? s.kpis.demand_by_airport[i] : 0, 1)} kt/yr`], ["SAF delivered", `${fmt(s.kpis.delivered_by_airport ? s.kpis.delivered_by_airport[i] : 0, 1)} kt/yr`]])}`;
    const at = `Airport ${a.iata}, ${a.name}`;
    const mk = L.marker([a.lat, a.lon], { zIndexOffset: 1000, title: at, alt: at, icon: L.divIcon({ className: "", html: `<div style="width:30px;height:30px;border-radius:50%;background:${ROLE.air};border:2px solid #fff;color:#fff;font:700 10px/26px Arial;text-align:center">${a.iata}</div>`, iconSize: [30, 30], iconAnchor: [15, 15] }) }).bindPopup(content).addTo(lay.air);
    track(`air:${a.iata}`, at, content, mk);
  });
  h.groups = Object.values(lay);
  h.groups.forEach((g) => g.addTo(h.map));
  h.control = L.control.layers(null, { "Biomass sites": lay.farm, Depots: lay.depot, Refineries: lay.ref, Airports: lay.air, "Site to depot": lay.fd, "Depot to refinery": lay.dr, "Refinery to airport": lay.ra }, { collapsed: true, position: "topright" }).addTo(h.map);
  setTimeout(() => h.map.invalidateSize(), 60);
}

// Locations of the selected scenario, one row per place, for the keyboard-accessible site list.
function siteRows(s) {
  const used = {};
  s.flows_fd.forEach((f) => { used[f.src] = (used[f.src] || 0) + f.kt; });
  const rows = state.net.sites.map((x) => ({ key: `site:${x.id}`, id: x.id, role: "Biomass site", where: `${x.district}, ${x.province}`, cap: x.kt, flow: used[x.id] || 0, util: x.kt ? (used[x.id] || 0) / x.kt : null }));
  const dep = {};
  s.depots.forEach((d) => {
    const r = dep[d.id] || (dep[d.id] = { key: `depot:${d.id}`, id: d.id, role: "Depot", where: `${d.lat.toFixed(2)}, ${d.lon.toFixed(2)}`, cap: 0, flow: 0 });
    r.cap += d.capacity;
    r.flow += d.throughput;
  });
  Object.values(dep).forEach((r) => { r.util = r.cap ? r.flow / r.cap : null; rows.push(r); });
  s.refineries.forEach((r) => rows.push({ key: `ref:${r.id}`, id: r.id, role: "Refinery", where: r.near, cap: r.capacity, flow: r.biomass_in, util: r.utilisation }));
  state.net.airports.forEach((a, i) => rows.push({ key: `air:${a.iata}`, id: a.iata, role: "Airport", where: a.city, cap: s.kpis.demand_by_airport ? s.kpis.demand_by_airport[i] : 0, flow: s.kpis.delivered_by_airport ? s.kpis.delivered_by_airport[i] : 0, util: null }));
  return rows;
}

const SITE_COLS = [["id", "Name", false], ["role", "Role", false], ["where", "Where", false], ["cap", "Supply or capacity, kt/yr", true], ["flow", "Flow, kt/yr", true], ["util", "Use, %", true]];

function siteTableHtml() {
  const all = siteRows(sol());
  const sort = state.siteSort;
  const role = state.siteRole;
  const rows = all.filter((r) => role === "all" || r.role === role);
  const dir = sort.dir;
  rows.sort((p, q) => {
    const a = p[sort.k], b = q[sort.k];
    if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
    if (b === null || b === undefined) return -1;
    return (typeof a === "number" ? a - b : String(a).localeCompare(String(b), "en", { numeric: true })) * dir;
  });
  const head = SITE_COLS.map(([k, l, n]) => `<th class="${n ? "n" : ""}" scope="col" aria-sort="${sort.k === k ? (dir > 0 ? "ascending" : "descending") : "none"}"><button type="button" class="sort" data-k="${k}">${l}</button></th>`).join("");
  const body = rows.map((r) => `<tr data-k="${r.key}"${state.sel === r.key ? ' class="sel" aria-current="true"' : ""}><td><button type="button" class="pick-row" data-k="${r.key}">${esc(r.id)}<span class="sr"> (show details on the map)</span></button></td><td>${r.role}</td><td>${esc(r.where)}</td><td class="n">${fmt(r.cap, 1)}</td><td class="n">${fmt(r.flow, 1)}</td><td class="n">${r.util === null ? "n/a" : fmt(100 * r.util, 1)}</td></tr>`).join("");
  return `<div class="scroll tall"><table id="siteList"><caption class="sr">Locations in the selected scenario, sortable. Airports show SAF demand and delivery, all other rows show biomass.</caption><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div><p class="note" id="siteCount" role="status">${rows.length} of ${all.length} locations. Airports show SAF demand and delivery in kt/yr, all other rows show biomass.</p>`;
}

function siteBoxHtml() {
  const roles = ["all", "Biomass site", "Depot", "Refinery", "Airport"];
  const plural = { all: "All locations", "Biomass site": "Biomass sites", Depot: "Depots", Refinery: "Refineries", Airport: "Airports" };
  return `<div class="card"><h3>Selected location</h3><div id="selDetail" class="detail" aria-live="polite"><p class="note">Nothing selected. Click a marker, or choose a name in the site list below.</p></div></div>
  <div class="card" id="siteBox"><h3>Site list</h3>
    <p class="note">The same locations as the map, for keyboard use. Choose a name to show its figures above and centre the map on it. The column buttons sort the list.</p>
    <div class="filters"><label>Show <select id="siteRole">${roles.map((r) => `<option value="${r}"${state.siteRole === r ? " selected" : ""}>${plural[r]}</option>`).join("")}</select></label></div>
    <div id="siteTable">${siteTableHtml()}</div></div>`;
}

function showDetail(key, move) {
  const h = state.maps.map1;
  const r = h && h.reg && h.reg[key];
  const box = $("#selDetail");
  state.sel = r ? key : null;
  if (box) box.innerHTML = r ? `<h4 style="margin:0 0 4px;font-size:15px">${esc(r.title)}</h4>${r.content.replace(/<div class="pop-h">.*?<\/div>/, "")}` : '<p class="note">Nothing selected. Click a marker, or choose a name in the site list below.</p>';
  document.querySelectorAll("#siteList tbody tr").forEach((tr) => {
    const on = r && tr.dataset.k === key;
    tr.classList.toggle("sel", !!on);
    if (on) tr.setAttribute("aria-current", "true"); else tr.removeAttribute("aria-current");
  });
  if (move && r) {
    h.map.setView(r.mk.getLatLng(), Math.max(h.map.getZoom(), 8), { animate: !REDUCED });
    r.mk.openPopup();
  }
}

function wireSiteBox() {
  const box = $("#siteBox");
  if (!box) return;
  const redraw = (focusSel) => {
    $("#siteTable").innerHTML = siteTableHtml();
    if (focusSel) { const b = $(focusSel); if (b) b.focus(); }
  };
  box.onclick = (e) => {
    const sb = e.target.closest("button.sort");
    if (sb) {
      const k = sb.dataset.k;
      state.siteSort = state.siteSort.k === k ? { k, dir: -state.siteSort.dir } : { k, dir: 1 };
      redraw(`button.sort[data-k="${k}"]`);
      return;
    }
    const pb = e.target.closest("button.pick-row");
    if (pb) showDetail(pb.dataset.k, true);
  };
  $("#siteRole").onchange = (e) => { state.siteRole = e.target.value; redraw(null); };
  showDetail(state.sel, false);
}

function renderMap() {
  const s = sol();
  drawNetwork("map1", s);
  const cmp = $("#compare").checked;
  $("#map2").hidden = !cmp;
  if (cmp) drawNetwork("map2", state.sols[state.other]);
  const skip = s.kpis.sites_skipped || [];
  $("#facilityTables").innerHTML = siteBoxHtml() + (s.refineries.length ? `
  <div class="grid2">
    <div class="card"><div class="row between"><h3>Refineries, optimal coordinates</h3><button class="btn ghost" id="csv">Download flows CSV</button></div><div class="scroll"><table>
      <tr><th>Id</th><th>Size</th><th class="n">Lat</th><th class="n">Lon</th><th class="n">Biomass kt</th><th class="n">SAF kt</th><th class="n">Used</th></tr>
      ${s.refineries.map((r) => `<tr><td>${r.id}</td><td>${r.size}</td><td class="n">${r.lat.toFixed(4)}</td><td class="n">${r.lon.toFixed(4)}</td><td class="n">${fmt(r.biomass_in)}</td><td class="n">${fmt(r.saf_kt)}</td><td class="n">${fmt(100 * r.utilisation, 1)}%</td></tr>`).join("")}
    </table></div></div>
    <div class="card"><h3>Depots</h3><div class="scroll"><table>
      <tr><th>Site</th><th>Modules</th><th class="n">Lat</th><th class="n">Lon</th><th class="n">Throughput kt</th><th class="n">Used</th></tr>
      ${s.depots.slice(0, 40).map((d) => `<tr><td>${d.id}</td><td>${d.count} ${d.size}</td><td class="n">${d.lat.toFixed(4)}</td><td class="n">${d.lon.toFixed(4)}</td><td class="n">${fmt(d.throughput)}</td><td class="n">${fmt(100 * d.utilisation, 1)}%</td></tr>`).join("")}
    </table></div></div>
  </div>
  <div class="card"><h3>Sites left unused</h3><p>${skip.length ? skip.join(", ") : "None. Every site ships biomass."}</p></div>` : `<div class="card"><div class="evs">${statusPill(s)}${evidenceHtml(s)}</div> ${esc(s.message)}${diagHtml(s)}</div>`);
  wireSiteBox();
  const b = $("#csv");
  if (b) b.onclick = () => {
    const rows = [["leg", "from", "to", "kt_per_year", "km", "usd_m_per_year", "mode"]];
    [["farm_depot", s.flows_fd], ["depot_refinery", s.flows_dr], ["refinery_airport", s.flows_ra]].forEach(([l, v]) => v.forEach((f) => rows.push([l, f.src, f.dst, f.kt.toFixed(4), f.km.toFixed(2), f.usd_m.toFixed(5), f.mode])));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" }));
    a.download = `kasco_${state.cur}_flows.csv`;
    a.click();
  };
}

// Inputs grouped by purpose. Each field: label, id, official value, step, unit.
const GROUPS = [
  ["Demand", "SAF delivered to each airport per year.", [
    ["PNK demand", "d0", 300, 1, "kt SAF per year"], ["PKN demand", "d1", 300, 1, "kt SAF per year"],
    ["BPN demand", "d2", 300, 1, "kt SAF per year"], ["TRK demand", "d3", 300, 1, "kt SAF per year"],
  ]],
  ["Feedstock and conversion", "Biomass supply and the SAF made from it.", [
    ["Yield", "yield_saf", 0.2, 0.01, "t SAF per t biomass"], ["Biomass availability", "biomass_multiplier", 1, 0.05, "multiple of the official supply"],
    ["Depot mass retention", "retention", 1, 0.01, "fraction kept, 1 for no loss"],
  ]],
  ["Plants and capital", "Size and cost of refineries and depots.", [
    ["Refinery CapEx", "rc", 1, 0.05, "multiple of the official CapEx"], ["Depot CapEx", "dc", 1, 0.05, "multiple of the official CapEx"],
    ["Large refinery capacity", "cap_l", 1087, 1, "kt biomass per year"], ["Small refinery capacity", "cap_s", 500, 1, "kt biomass per year"],
    ["CapEx years", "capex_years", 20, 1, "years, straight line"], ["Fixed OpEx share", "fixed_opex_frac", 0.05, 0.005, "fraction of CapEx per year"],
    ["Max refineries", "max_refineries", 0, 1, "count, 0 for no limit"],
  ]],
  ["Transport", "Tariffs and distances.", [
    ["Farm to depot tariff", "tariff_fd", 0.1, 0.01, "USD per t per km"], ["Depot to refinery tariff", "tariff_dr", 0.12, 0.01, "USD per t per km"],
    ["Refinery to airport tariff", "tariff_ra", 0.08, 0.01, "USD per t per km"], ["Road factor", "road_factor", 1.3, 0.05, "multiple of great-circle distance"],
  ]],
];
const FIELDS = GROUPS.flatMap((g) => g[2]).concat([["Solver time limit", "time_limit_s", 12, 1, "seconds"]]);
const SELECTS = [["mode", "Depot design", "colocated", [["colocated", "At the refinery"], ["field", "In the field"]]], ["basis", "Distances", "great_circle", [["great_circle", "Great-circle x road factor"], ["road", "OSRM road km"]]]];

// Input checks. A field passes when it is a number inside the stated bounds. The warning is advisory and never blocks a run.
const POS = "Enter a number above 0.";
const RULES = {
  d0: { min: 0, msg: "Enter zero or more kt SAF per year." }, d1: { min: 0, msg: "Enter zero or more kt SAF per year." },
  d2: { min: 0, msg: "Enter zero or more kt SAF per year." }, d3: { min: 0, msg: "Enter zero or more kt SAF per year." },
  yield_saf: { gt: 0, max: 1, msg: "Enter a yield above 0 and at most 1 t SAF per t biomass.", warn: (v) => (v < 0.15 || v > 0.25 ? "Outside the 15 to 25% range in the Airbus update. The solver still runs." : "") },
  biomass_multiplier: { gt: 0, msg: POS },
  retention: { gt: 0, max: 1, msg: "Enter a fraction above 0 and at most 1." },
  rc: { gt: 0, msg: POS }, dc: { gt: 0, msg: POS },
  cap_l: { gt: 0, msg: "Enter a capacity above 0 kt." },
  cap_s: { gt: 0, msg: "Enter a capacity above 0 kt.", warn: (v) => (v > parseFloat($("#f_cap_l").value) ? "Above the large refinery capacity. Check the two values." : "") },
  capex_years: { min: 1, msg: "Enter at least 1 year." },
  fixed_opex_frac: { min: 0, max: 1, msg: "Enter a fraction from 0 to 1." },
  max_refineries: { min: 0, msg: "Enter a whole number, 0 for no limit.", warn: (v) => (Number.isInteger(v) ? "" : `Will be rounded to ${Math.max(0, Math.round(v))}.`) },
  tariff_fd: { min: 0, msg: "Enter zero or more USD per t per km." }, tariff_dr: { min: 0, msg: "Enter zero or more USD per t per km." }, tariff_ra: { min: 0, msg: "Enter zero or more USD per t per km." },
  road_factor: { gt: 0, msg: POS, warn: (v) => (v < 1 ? "Below 1 makes road distance shorter than the straight line." : "") },
  time_limit_s: { min: 1, max: 300, msg: "Enter a time limit from 1 to 300 s." },
};

function checkField(id) {
  const rule = RULES[id];
  const el = $(`#f_${id}`);
  if (!rule || !el) return "";
  const v = parseFloat(el.value);
  let err = "", warn = "";
  if (el.value.trim() === "" || !Number.isFinite(v)) err = "Enter a number.";
  else if ((rule.min !== undefined && v < rule.min) || (rule.gt !== undefined && v <= rule.gt) || (rule.max !== undefined && v > rule.max)) err = rule.msg;
  else if (rule.warn) warn = rule.warn(v);
  const m = $(`#f_${id}_m`);
  m.textContent = err || warn;
  m.className = err ? "fmsg" : "fmsg warnmsg";
  el.setAttribute("aria-invalid", err ? "true" : "false");
  return err;
}

function validateAll() {
  return FIELDS.map(([l, id]) => ({ id, label: l, err: checkField(id) })).filter((x) => x.err);
}

// A necessary condition only: the biomass that would be needed to make the demanded SAF against the biomass on offer.
function screenState() {
  const v = (id) => parseFloat($(`#f_${id}`).value);
  const demand = [0, 1, 2, 3].reduce((a, i) => a + v(`d${i}`), 0);
  const supply = state.net.sites.reduce((a, x) => a + x.kt, 0) * v("biomass_multiplier");
  const y = v("yield_saf");
  if (![demand, supply, y].every(Number.isFinite) || y <= 0) return { cls: "", html: "Enter valid demand, yield and biomass availability to see the mass-balance screen." };
  const need = demand / y;
  const pass = need <= supply + 1e-9;
  return { cls: pass ? "pass" : "fail", html: `<b>Mass-balance screen: ${pass ? "passes" : "fails"}.</b> ${fmt(demand)} kt SAF at a yield of ${fmt(y, 3)} needs at least ${fmt(need)} kt of biomass, and ${fmt(supply)} kt is on offer. ${pass ? "This is a necessary condition only. Capacity, the refinery limit and depot losses can still make the solver report infeasible." : "No network can meet this demand. Raise the yield or the biomass availability, or lower the demand."}` };
}

function updateForm() {
  validateAll();
  const sc = screenState();
  const box = $("#screen");
  box.className = `screen ${sc.cls}`;
  box.innerHTML = sc.html;
  const changed = [];
  FIELDS.forEach(([l, id, v]) => {
    const on = parseFloat($(`#f_${id}`).value) !== v;
    $(`#w_${id}`).classList.toggle("changed", on);
    if (on) changed.push(l);
  });
  SELECTS.forEach(([id, l, v]) => {
    const on = $(`#f_${id}`).value !== v;
    $(`#w_${id}`).classList.toggle("changed", on);
    if (on) changed.push(l);
  });
  $("#chgState").textContent = changed.length ? `${changed.length} input${changed.length > 1 ? "s" : ""} changed from the official inputs: ${changed.join(", ")}.` : "All inputs match the official inputs.";
}

function renderOptimise() {
  const fld = ([l, id, v, step, unit]) => `<div class="fld" id="w_${id}"><label for="f_${id}">${l}</label><input type="number" id="f_${id}" value="${v}" step="${step}" inputmode="decimal" aria-describedby="f_${id}_u f_${id}_m"><span class="unit" id="f_${id}_u">${unit}</span><span class="fmsg" id="f_${id}_m"></span></div>`;
  const sel = ([id, l, , opts]) => `<div class="fld" id="w_${id}"><label for="f_${id}">${l}</label><select id="f_${id}">${opts.map(([val, t]) => `<option value="${val}">${t}</option>`).join("")}</select></div>`;
  const grp = (name, note, body) => `<fieldset class="grp"><legend>${name}</legend><p class="note">${note}</p><div class="form">${body}</div></fieldset>`;
  $("#optimise").innerHTML = `
  <h2>Run the optimiser <span class="src-tag solver">Solver result</span></h2>
  <p class="note">The solver runs in your browser. Change any input and press Run. Results join the scenario list above. Inputs that differ from the official values are outlined.</p>
  <div class="card">
    ${grp("Demand", GROUPS[0][1], GROUPS[0][2].map(fld).join(""))}
    ${grp("Feedstock and conversion", GROUPS[1][1], GROUPS[1][2].map(fld).join(""))}
    ${grp("Plants and capital", GROUPS[2][1], GROUPS[2][2].map(fld).join("") + sel(SELECTS[0]))}
    ${grp("Transport", GROUPS[3][1], GROUPS[3][2].map(fld).join("") + sel(SELECTS[1]))}
    ${grp("Run settings", "How long the search may run, and what the result is called.", fld(["Solver time limit", "time_limit_s", 12, 1, "seconds"]) + `<div class="fld"><label for="f_name">Name this run</label><input type="text" id="f_name" value="Custom run"></div>`)}
    <div id="screen" class="screen"></div>
    <p id="chgState" class="note"></p>
    <div class="runbar"><button class="btn" id="run" type="button">Run solver</button><button class="btn danger" id="cancel" type="button" hidden>Cancel run</button><button class="btn ghost" id="reset" type="button">Reset to official inputs</button>
      <span class="runtimer" id="runTimer" hidden aria-hidden="true"><progress id="runProg" max="1" value="0"></progress> <span id="runClock" class="note"></span></span></div>
    <p id="runState" class="note" role="status" aria-live="polite"></p>
  </div>
  <div id="runResult"></div>`;
  $("#run").onclick = runCustom;
  $("#cancel").onclick = cancelSolve;
  $("#reset").onclick = () => {
    FIELDS.forEach(([, id, v]) => { $(`#f_${id}`).value = v; });
    SELECTS.forEach(([id, , v]) => { $(`#f_${id}`).value = v; });
    $("#f_name").value = "Custom run";
    $("#runState").textContent = "Inputs reset to the official values.";
    updateForm();
  };
  $("#optimise").addEventListener("input", updateForm);
  $("#optimise").addEventListener("change", updateForm);
  updateForm();
}

function formParams() {
  const v = (id) => parseFloat($(`#f_${id}`).value);
  const p = JSON.parse(JSON.stringify(DEFAULTS));
  p.name = $("#f_name").value || "Custom run";
  p.demand = [v("d0"), v("d1"), v("d2"), v("d3")];
  ["yield_saf", "biomass_multiplier", "retention", "tariff_fd", "tariff_dr", "tariff_ra", "road_factor", "fixed_opex_frac", "capex_years", "time_limit_s"].forEach((k) => { p[k] = v(k); });
  p.max_refineries = Math.max(0, Math.round(v("max_refineries")));
  p.refinery_capex = DEFAULTS.refinery_capex.map((x) => x * v("rc"));
  p.depot_capex = DEFAULTS.depot_capex.map((x) => x * v("dc"));
  p.refinery_cap = [v("cap_s"), v("cap_l")];
  p.depot_mode = $("#f_mode").value;
  p.distance_basis = $("#f_basis").value;
  p.refine = p.distance_basis === "great_circle";
  return p;
}

async function runCustom() {
  const errs = validateAll();
  if (errs.length) {
    $("#runState").textContent = `Fix ${errs.length} input${errs.length > 1 ? "s" : ""} before running: ${errs.map((e) => e.label).join(", ")}.`;
    $(`#f_${errs[0].id}`).focus();
    return;
  }
  const b = $("#run"), c = $("#cancel"), tm = $("#runTimer");
  const p = formParams();
  b.disabled = true;
  c.hidden = false;
  tm.hidden = false;
  $("#runResult").setAttribute("aria-busy", "true");
  $("#runState").textContent = `Solver running, up to ${p.time_limit_s} s. You can cancel the run.`;
  const t0 = performance.now();
  const tick = () => {
    const el = (performance.now() - t0) / 1000;
    $("#runProg").value = Math.min(1, el / p.time_limit_s);
    $("#runClock").textContent = `${fmt(el, 1)} s of up to ${p.time_limit_s} s`;
  };
  tick();
  const timer = setInterval(tick, 200);
  try {
    const s = await rpc(1, p);
    const key = `custom_${++state.customN}`;
    s.key = key;
    state.sols[key] = s;
    state.keys.push(key);
    state.names[key] = `${p.name} #${state.customN}`;
    fillPickers();
    $("#runState").textContent = `Finished in ${fmt((performance.now() - t0) / 1000, 1)} s. ${s.refineries.length ? "A network was found." : "No feasible network was found."} Result added to the scenario list.`;
    const k = s.kpis;
    const gapTile = s.gap !== null ? tile(`${fmt(100 * s.gap, 2)}%`, "Proven gap") : tile(s.gap_to_bound === null ? "n/a" : `${fmt(100 * s.gap_to_bound, 2)}%`, "Above proven bound, heuristic, no proof");
    $("#runResult").innerHTML = `<div class="card"><div class="row between"><h3>${esc(p.name)} <span class="src-tag solver">Solver result</span></h3><div class="evs">${statusPill(s)}${evidenceHtml(s)}</div></div>
      ${s.refineries.length ? `<div class="tiles">${tile(usd(s.objective), "Total annual cost")}${tile(`USD ${fmt(k.unit_cost_usd_t)}/t`, "Cost per tonne SAF")}${tile(k.n_refineries, "Refineries")}${tile(k.n_depots, "Depots")}${gapTile}${tile(s.validation.every((c) => c.passed) ? "All passed" : "Failed", "Constraint audit")}</div><button class="btn ghost" id="showRun">Show on map</button>` : `<p>${esc(s.message)}</p>${diagHtml(s)}`}</div>`;
    const sh = $("#showRun");
    if (sh) sh.onclick = () => { state.cur = key; $("#scenario").value = key; showTab("map"); refresh(); };
  } catch (e) {
    $("#runState").textContent = e.message === "cancelled" ? "Run cancelled. No result was added." : `The solver stopped: ${e.message}`;
  }
  clearInterval(timer);
  tm.hidden = true;
  const lost = document.activeElement === c || document.activeElement === document.body;
  c.hidden = true;
  b.disabled = false;
  if (lost) b.focus();
  $("#runResult").removeAttribute("aria-busy");
}

function compareRows(a, b) {
  const g = (s, f) => (s.refineries.length ? f(s) : null);
  const rows = [
    ["Total annual cost, USD M", (s) => s.objective, 1], ["Cost per tonne SAF, USD", (s) => s.kpis.unit_cost_usd_t, 0], ["Refineries", (s) => s.kpis.n_refineries, 0], ["Depots", (s) => s.kpis.n_depots, 0],
    ["Biomass used, kt", (s) => s.kpis.biomass_used_kt, 0], ["SAF delivered, kt", (s) => s.kpis.saf_kt, 0], ["Demand met, %", (s) => 100 * s.kpis.fill_rate, 1], ["CapEx, USD M", (s) => s.costs.capex_total, 0],
    ["Annualised CapEx, USD M/yr", (s) => s.costs.annual_capex, 1], ["Fixed OpEx, USD M/yr", (s) => s.costs.opex_fixed, 1], ["Variable OpEx, USD M/yr", (s) => s.costs.opex_variable, 1], ["Transport, USD M/yr", (s) => s.costs.logistics_total, 1],
    ["Mean refinery use, %", (s) => 100 * s.kpis.mean_refinery_utilisation, 1], ["Tonne-km, billions/yr", (s) => s.kpis.tonne_km_bn, 3], ["Estimated truck-km, millions/yr", (s) => s.kpis.truck_km_m, 1, true],
  ];
  const fleet = (s) => (s.refineries.length ? `${s.kpis.n_refineries_large} large, ${s.kpis.n_refineries_small} small` : "n/a");
  const depots = (s) => (s.refineries.length ? `${s.kpis.n_depots_large} large, ${s.kpis.n_depots_small} small, ${s.params.depot_mode === "field" ? "in the field" : "at the refinery"}` : "n/a");
  const text = [
    ["Status and evidence", (s) => `<span class="evs">${statusPill(s)}${evidenceHtml(s)}</span>`, (s) => evidenceKinds(s).join() + s.status],
    ["Optimality gap", gapText, gapText],
    ["Refinery fleet", fleet, fleet],
    ["Depot modules", depots, depots],
  ];
  const head = text.map(([l, show, same]) => `<tr><td>${l}</td><td class="n">${show(a)}</td><td class="n">${show(b)}</td><td class="n">${same(a) === same(b) ? "Same" : "Differs"}</td></tr>`).join("");
  return head + rows.map(([l, f, d, est]) => {
    const x = g(a, f), y = g(b, f);
    const diff = x !== null && y !== null ? y - x : null;
    return `<tr><td>${l}${est ? ` <span class="ev est" title="${esc(EV.est[2])}">Estimate</span>` : ""}</td><td class="n">${fmt(x, d)}</td><td class="n">${fmt(y, d)}</td><td class="n">${diff === null ? "n/a" : (diff >= 0 ? "+" : "") + fmt(diff, d)}</td></tr>`;
  }).join("");
}

// A cost difference is only a proven saving when both results carry the same strength of proof.
function compareNote(a, b) {
  const notes = [];
  if (a.status === "heuristic" || b.status === "heuristic") notes.push("At least one result is a heuristic, so its cost has no optimality proof and a difference is not a proven saving.");
  else if (a.status !== b.status) notes.push("The two results carry different proof, so read the cost difference with that in mind.");
  if (!a.refineries.length || !b.refineries.length) notes.push("One scenario has no feasible network, so its figures are n/a.");
  return notes.length ? `<p class="cmpnote">${notes.join(" ")}</p>` : "";
}

function gapText(s) {
  if (s.gap !== null) return `${fmt(100 * s.gap, 2)}%`;
  return s.gap_to_bound === null ? "n/a" : `No proof, ${fmt(100 * s.gap_to_bound, 2)}% above bound`;
}

function renderScenarios() {
  const a = sol(), b = state.sols[state.other];
  const list = state.keys.map((k) => state.sols[k]);
  const ok = list.filter((s) => s.refineries.length && s.objective > 200);
  $("#scenarios").innerHTML = `
  <h2>Scenario analysis <span class="src-tag solver">Solver result</span></h2>
  ${keyHtml(false)}
  <div class="card scroll"><table>
    <tr><th>Scenario</th><th>Status</th><th>Evidence</th><th class="n">Annual cost, USD M</th><th class="n">USD/t SAF</th><th class="n">Refineries</th><th class="n">Depots</th><th class="n">Gap</th></tr>
    ${list.map((s) => `<tr><td>${esc(state.names[s.key])}</td><td>${statusPill(s)}</td><td>${evidenceHtml(s)}</td><td class="n">${fmt(s.objective, 1)}</td><td class="n">${s.refineries.length ? fmt(s.kpis.unit_cost_usd_t) : "n/a"}</td><td class="n">${s.refineries.length ? s.kpis.n_refineries : "n/a"}</td><td class="n">${s.refineries.length ? s.kpis.n_depots : "n/a"}</td><td class="n">${gapText(s)}</td></tr>`).join("")}
  </table></div>
  <div class="grid2">
    <div class="card"><h3>Side by side</h3><div class="row" style="margin-bottom:8px"><span class="note">${esc(state.names[a.key])}</span> vs <select id="cmpPick" aria-label="Scenario to compare with">${state.keys.map((k) => `<option value="${k}" ${k === state.other ? "selected" : ""}>${esc(state.names[k])}</option>`).join("")}</select></div>
      <div class="scroll"><table><tr><th>Measure</th><th class="n">Selected</th><th class="n">Compared</th><th class="n">Change</th></tr>${compareRows(a, b)}</table></div>${compareNote(a, b)}</div>
    <div class="card"><h3>Cost by scenario, USD M per year</h3><div class="chart tall"><canvas id="scenCost"></canvas></div></div>
  </div>`;
  $("#cmpPick").onchange = (e) => { state.other = e.target.value; $("#scenario2").value = e.target.value; renderScenarios(); };
  const set = (label, f, color) => ({ label, data: ok.map(f), backgroundColor: color, borderColor: SURFACE, borderWidth: 2 });
  chart("scenCost", {
    type: "bar",
    data: { labels: ok.map((s) => state.names[s.key].slice(0, 34)), datasets: [set("Annualised CapEx", (s) => s.costs.annual_capex, COL.s1), set("Fixed OpEx", (s) => s.costs.opex_fixed, COL.s2), set("Variable OpEx", (s) => s.costs.opex_variable, COL.s3), set("Transport", (s) => s.costs.logistics_total, COL.s4)] },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } }, scales: { x: { stacked: true, grid: { color: COL.grid } }, y: { stacked: true, grid: { display: false }, ticks: { font: { size: 11 } } } } },
  });
}

function md(t) {
  const safe = esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  const out = [];
  let list = null;
  const flush = () => { if (list) { out.push(`<${list.tag}>${list.items.join("")}</${list.tag}>`); list = null; } };
  safe.split("\n").forEach((l) => {
    const u = l.match(/^- (.*)/), o = l.match(/^\d+\. (.*)/);
    if (u || o) {
      const tag = u ? "ul" : "ol";
      if (!list || list.tag !== tag) { flush(); list = { tag, items: [] }; }
      list.items.push(`<li>${(u || o)[1]}</li>`);
    } else { flush(); if (l.trim()) out.push(`<p>${l}</p>`); }
  });
  flush();
  return out.join("");
}

const EXAMPLES = ["Why was this refinery selected?", "Which routes are most expensive?", "Why are large depots preferable?", "Why are some sites unused?", "What happens if SAF demand increases by 10% while refinery CapEx increases by 15%?", "What happens if demand increases by 20%?", "Which facilities are near capacity?", "How much does this improve on the baseline?", "Show the cost breakdown", "What is the lifecycle CO2 of this network?"];

function renderInsights() {
  $("#insights").innerHTML = `
  <h2>Decision support <span class="src-tag rules">Rule-based recommendation</span></h2>
  <p class="note">This panel uses no language model. Questions route by rule to solver records, and every answer lists the fields it read. A what-if can change several inputs at once, and it runs only when every part maps to a validated input. Questions outside the model are declined. Answers apply to the selected scenario: ${esc(state.names[state.cur])}.</p>
  <div class="card">
    <div class="chips">${EXAMPLES.map((e) => `<button class="chip">${esc(e)}</button>`).join("")}</div>
    <div class="ask"><input type="text" id="q" aria-label="Question about this network" placeholder="Ask about this network"><button class="btn" id="askBtn">Ask</button></div>
    <div id="chat" role="log" aria-live="polite" aria-label="Answers">${state.chat.join("")}</div>
  </div>`;
  document.querySelectorAll(".chip").forEach((b) => { b.onclick = () => ask(b.textContent); });
  $("#askBtn").onclick = () => ask($("#q").value);
  $("#q").onkeydown = (e) => { if (e.key === "Enter") ask($("#q").value); };
}

async function ask(q) {
  if (!q.trim()) return;
  const box = $("#chat");
  const btn = $("#askBtn");
  btn.disabled = true;
  const wait = document.createElement("div");
  wait.className = "msg";
  wait.textContent = "Working from solver records...";
  box.prepend(wait);
  try {
    const a = await rpc(2, { question: q, solution: sol() });
    const html = `<div class="msg q">${esc(q)}</div><div class="msg ${a.declined ? "no" : ""}"><span class="src-tag rules">Rule-based, no language model</span> ${a.declined ? '<span class="pill warn">Declined</span>' : ""}${md(a.text)}${a.sources.length ? `<div class="src">Read from: ${esc(a.sources.join(", "))}</div>` : ""}</div>`;
    state.chat.unshift(html);
    wait.remove();
    box.innerHTML = state.chat.join("");
  } catch (e) {
    wait.textContent = `The engine stopped: ${e.message}`;
  }
  btn.disabled = false;
}

function renderEvaluation() {
  const s = sol(), B = state.base, H = state.highs, KM = B.kmeans, DC = state.depots;
  const rows = [["Optimised", B.optimised], ["Field depots, 60 km radius", B.field], ["Greedy heuristic", B.greedy], ["Airport-first", B.airport_first]];
  const kmRows = [[`K-means, same fleet and refinement, best of ${KM.restarts}`, KM.best, Math.max(0, KM.best_saving_usd_m), Math.max(0, KM.best_saving_pct)], ["K-means, same fleet and refinement, median", KM.median, KM.median_saving_usd_m, KM.median_saving_pct]];
  const chartRows = [["Optimised", B.optimised.objective], ["K-means, best", KM.best], ["K-means, median", KM.median], ["Field depots", B.field.objective], ["Greedy heuristic", B.greedy.objective], ["Airport-first", B.airport_first.objective]];
  const fails = state.keys.map((k) => state.sols[k]).filter((x) => x.status === "infeasible");
  const v = s.validation || [];
  const A = state.sols.official_base, F = state.sols.field_depots;
  const ab = [
    ["Annual total, USD M", (x) => x.objective, 2], ["CapEx, USD M", (x) => x.costs.capex_total, 1], ["Annualised CapEx plus fixed OpEx, USD M/yr", (x) => x.costs.annual_capex + x.costs.opex_fixed, 1], ["Variable OpEx, USD M/yr", (x) => x.costs.opex_variable, 1], ["Logistics, USD M/yr", (x) => x.costs.logistics_total, 1],
    ["Depots", (x) => x.kpis.n_depots, 0], ["Refineries", (x) => x.kpis.n_refineries, 0], ["Biomass, kt/yr", (x) => x.kpis.biomass_used_kt, 0], ["SAF, kt/yr", (x) => x.kpis.saf_kt, 0], ["Demand met, %", (x) => 100 * x.kpis.fill_rate, 0],
    ["Freight moved, billion tonne-km", (x) => x.kpis.tonne_km_bn, 3], ["Estimated truck-km, millions", (x) => x.kpis.truck_km_m, 1],
  ];
  const M = state.marginal;
  const cliff = 6 * 1087 * 0.2;
  $("#evaluation").innerHTML = `
  <h2>Evaluation <span class="src-tag solver">Solver result</span></h2>
  ${keyHtml(false)}
  <div class="grid2">
    <div class="card"><h3>Against baselines, same demand and cost basis</h3><div class="chart"><canvas id="baseChart"></canvas></div>
      <div class="scroll"><table><tr><th>Design</th><th class="n">USD M/yr</th><th class="n">Extra cost vs optimised</th><th class="n">Ref</th><th class="n">Dep</th></tr>
      ${rows.map(([l, r], i) => `<tr><td>${l}</td><td class="n">${fmt(r.objective, 1)}</td><td class="n">${i ? `${fmt(r.saving_usd_m, 1)} (${fmt(r.saving_pct, 1)}%)` : "n/a"}</td><td class="n">${r.n_ref}</td><td class="n">${r.n_dep}</td></tr>`).join("")}
      ${kmRows.map((r) => `<tr><td>${r[0]}</td><td class="n">${fmt(r[1], 1)}</td><td class="n">${fmt(r[2], 1)} (${fmt(r[3], 1)}%)</td><td class="n">${KM.n_ref}</td><td class="n">${KM.n_dep}</td></tr>`).join("")}</table></div>
      <p class="note">These are measured model runs, not savings against real planners. The greedy and airport rules are simple heuristics. The k-means benchmark is deliberately strong: it is handed the cheapest fleet, exact flows and our refinement. Its best run reaches our network, which is independent support for the result and also shows the site search adds little once the fleet is known. Transport is a small share of cost, so the objective is flat near the optimum.</p></div>
    <div class="card"><h3>How far to trust the optimum</h3><div class="scroll"><table>
      <tr><td>Rust cost, candidate sites</td><td class="n">${usd(B.discrete, 2)}</td></tr>
      <tr><td>Rust proven lower bound</td><td class="n">${usd(B.bound, 2)}</td></tr>
      <tr><td>Cost after continuous refinement</td><td class="n">${usd(B.optimised.objective, 2)}</td></tr>
      ${H ? `<tr><td>${esc(H.solver)} cost, same co-located model</td><td class="n">${usd(H.objective, 2)}</td></tr><tr><td>${esc(H.solver)} lower bound at ${fmt(H.time_limit_s)} s</td><td class="n">${usd(H.bound, 2)}</td></tr>` : ""}
      ${DC ? `<tr><td>Depots free to go anywhere, base fleet, HiGHS proven</td><td class="n">${usd(DC.free_depot_cost, 2)}</td></tr>` : ""}
    </table></div>
    <p class="note">Status: the base case is feasible within a proven ${fmt(100 * B.optimised.gap, 2)}% on candidate sites. That bound comes almost entirely from the root relaxation, since biomass sites are near-substitutes and branching barely moves it. Refined coordinates are a local optimum with no global proof, and the field design is a heuristic. HiGHS reads the exported LP file, which covers co-located depots.${DC ? " The depot row tests the wider three-tier model on this fleet only." : ""}</p>
    ${state.check ? `<h3 style="margin-top:12px">Is the Rust bound valid?</h3><p class="note">On smaller demand levels HiGHS proves the optimum, so the Rust bound must sit at or below it.</p><div class="scroll"><table><tr><th class="n">Demand, kt</th><th class="n">Rust cost</th><th class="n">Rust bound</th><th class="n">HiGHS optimum</th><th>Result</th></tr>${state.check.map((r) => `<tr><td class="n">${fmt(r.total_demand_kt)}</td><td class="n">${fmt(r.rust_cost, 3)}</td><td class="n">${fmt(r.rust_bound, 3)}</td><td class="n">${fmt(r.highs_cost, 3)}</td><td><span class="pill ${r.bound_valid ? "good" : "bad"}">${r.bound_valid ? "Valid" : "Invalid"}</span></td></tr>`).join("")}</table></div>` : ""}</div>
  </div>
  <div class="grid2">
    <div class="card"><h3>Depots at the refinery or in the field</h3><div class="scroll"><table><tr><th>Measure</th><th class="n">A: at refinery, optimised</th><th class="n">B: in field, heuristic</th><th class="n">Change</th></tr>
      ${ab.map(([l, f, d]) => { const x = f(A), y = f(F), c = y - x; return `<tr><td>${l}</td><td class="n">${fmt(x, d)}</td><td class="n">${fmt(y, d)}</td><td class="n">${c >= 0 ? "+" : ""}${fmt(c, d)}</td></tr>`; }).join("")}</table></div>
      <p class="note">B gathers biomass within 60 km, then hauls the long leg in larger trucks. So B moves more freight in fewer truck journeys. Truck-km is an estimate that assumes large trucks and empty returns, and it includes the barge portion to Tarakan. A tonne-km tariff cannot see this benefit. The official inputs favour A, and real moisture loss could favour B.</p></div>
    <div class="card"><h3>What extra demand costs</h3><div class="scroll"><table><tr><th>Change</th><th class="n">USD M/yr</th><th class="n">USD per extra t</th><th>Fleet</th><th class="n">Gap</th></tr>
      ${M.rows.map((r) => `<tr><td>${esc(r.label)}</td><td class="n">${r.delta === null ? "Infeasible" : `${r.delta >= 0 ? "+" : ""}${fmt(r.delta, 1)}`}</td><td class="n">${r.usd_per_t === null ? "n/a" : fmt(r.usd_per_t)}</td><td>${r.delta === null ? "n/a" : `${r.n_large} large${r.n_small ? `, ${r.n_small} small` : ""}`}</td><td class="n">${r.gap === null ? "n/a" : `${fmt(100 * r.gap, 2)}%`}</td></tr>`).join("")}</table></div>
      <p class="note">Each row is a full re-solve against the candidate-site base of ${usd(M.base, 2)}. These are planning estimates and not shadow prices, as plant decisions are whole units. Six large plants reach their limit at ${fmt(cliff, 1)} kt of SAF, and the next kilotonne needs a seventh plant, so cost steps up sharply there. Small differences can sit inside the solver gap.</p></div>
  </div>
  <div class="grid2">
    <div class="card"><h3>Change in annual cost when one input moves 20%</h3><div class="chart tall"><canvas id="tornado"></canvas></div>
      <p class="note">Blue is the input at -20%, orange at +20%. Missing bars are infeasible runs, listed under where it fails.</p></div>
    <div class="card"><h3>Cost per tonne falls with scale</h3><div class="chart tall"><canvas id="ladder"></canvas></div>
      <p class="note">Each point is a full solve. The vertical scale is logarithmic. The smallest plant takes 500 kt of biomass, so low demand leaves most of it idle.</p></div>
  </div>
  <div class="card"><h3>Where it fails, and how you would know</h3><div class="scroll"><table><tr><th>Scenario</th><th>Reason shown to the planner</th><th>Fix offered</th></tr>
    ${fails.map((x) => `<tr><td>${esc(state.names[x.key])}</td><td>${esc((x.diagnostics[0] || {}).reason || x.message)}</td><td>${esc((x.diagnostics[0] || {}).fix || "")}</td></tr>`).join("")}</table></div>
    <p class="note">Demand can rise by at most ${fmt(100 * (6800 / 6000 - 1), 1)}% before feedstock runs out. Yield below ${fmt(1200 / 6800, 3)} makes 1,200 kt unreachable. The update allows a 15 to 25% yield range, so the low end of that range cannot meet demand.</p></div>
  <div class="card"><h3>Constraint audit, ${esc(state.names[state.cur])}</h3>${v.length ? `<p class="note">Recomputed from flow records by a separate module that shares no code with the solver.</p><div class="scroll"><table><tr><th>Check</th><th>Result</th><th class="n">Worst value</th><th class="n">Limit</th></tr>${v.map((c) => `<tr><td>${esc(c.check)}</td><td><span class="pill ${c.passed ? "good" : "bad"}">${c.passed ? "Pass" : "Fail"}</span></td><td class="n">${c.worst.toExponential(2)}</td><td class="n">${c.limit}</td></tr>`).join("")}</table></div>` : "<p>No network to audit in this scenario.</p>"}</div>
  ${s.trips && s.trips.length ? `<div class="card"><h3>Truck trips per year</h3><p class="note">Cost per tonne-km is the same for both truck sizes, so size changes traffic and leaves cost untouched.</p><div class="scroll"><table><tr><th>Leg</th><th class="n">Tonnes</th><th class="n">Small truck, t</th><th class="n">Trips</th><th class="n">Large truck, t</th><th class="n">Trips</th></tr>${s.trips.map((t) => `<tr><td>${t.leg}</td><td class="n">${fmt(t.tonnes)}</td><td class="n">${t.small_t}</td><td class="n">${fmt(t.trips_small)}</td><td class="n">${t.large_t}</td><td class="n">${fmt(t.trips_large)}</td></tr>`).join("")}</table></div></div>` : ""}`;
  chart("baseChart", {
    type: "bar",
    data: { labels: chartRows.map((r) => r[0]), datasets: [{ label: "USD M per year", data: chartRows.map((r) => r[1]), backgroundColor: chartRows.map((_, i) => (i ? COL.muted : COL.s1)), borderRadius: 4, barThickness: 16 }] },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { min: 0, grid: { color: COL.grid } }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } } },
  });
  const base = state.sens.base;
  const sr = state.sens.rows;
  const d = (r) => (r && r.objective ? r.objective - base : null);
  chart("tornado", {
    type: "bar",
    data: { labels: sr.map((r) => r.name), datasets: [{ label: "-20%", data: sr.map((r) => d(r.low)), backgroundColor: COL.s1, borderRadius: 3 }, { label: "+20%", data: sr.map((r) => d(r.high)), backgroundColor: COL.s2, borderRadius: 3 }] },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } }, tooltip: { callbacks: { label: (t) => `${t.dataset.label}: ${t.raw === null ? "infeasible" : `USD ${t.raw >= 0 ? "+" : ""}${fmt(t.raw, 1)}M/yr`}` } } }, scales: { x: { stacked: true, grid: { color: COL.grid }, title: { display: true, text: "USD M per year against base" } }, y: { stacked: true, grid: { display: false } } } },
  });
  const pts = state.ladder.filter((p) => p.objective);
  chart("ladder", {
    type: "line",
    data: { datasets: [{ label: "USD per tonne SAF", data: pts.map((p) => ({ x: p.level, y: p.unit, r: p.n_ref })), borderColor: COL.s1, backgroundColor: COL.s1, borderWidth: 2, pointRadius: 4, tension: 0 }] },
    options: { maintainAspectRatio: false, parsing: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (t) => `${fmt(t.raw.x)} kt SAF: USD ${fmt(t.raw.y)}/t, ${t.raw.r} refineries` } } }, scales: { x: { type: "linear", grid: { color: COL.grid }, title: { display: true, text: "Total SAF demand, kt per year" } }, y: { type: "logarithmic", grid: { color: COL.grid }, title: { display: true, text: "USD per tonne SAF" }, ticks: { callback: (v) => ([500, 1000, 2000, 5000, 10000, 20000].includes(v) ? fmt(v) : "") } } } },
  });
}

function renderReports() {
  const SC = state.screen, OC = state.official;
  $("#reports").innerHTML = `
  <h2>Reports and data</h2>
  <div class="grid2">
    <div class="card"><h3>Documents</h3><ul>
      <li><a href="reports/KASCO_Technical_Report.pdf">KASCO technical report (PDF)</a></li>
      <li><a href="reports/KASCO_Pitch.pptx">KASCO pitch deck (PowerPoint)</a></li>
      <li><a href="reports/KASCO_Pitch.pdf">KASCO pitch deck (PDF)</a></li>
    </ul></div>
    <div class="card"><h3>Results as data</h3><ul>
      ${state.keys.filter((k) => !k.startsWith("custom")).map((k) => `<li><a href="data/${k}.json">${esc(state.names[k])}</a></li>`).join("")}
    </ul></div>
  </div>
  <div class="card"><h3>Real-world evidence</h3><div class="scroll"><table><tr><th>Finding</th><th>Source</th><th>Date</th><th>Type</th></tr>
    ${EVIDENCE.map((e) => `<tr><td>${e[0]}</td><td><a href="${e[2]}" target="_blank" rel="noopener">${esc(e[1])}</a></td><td>${esc(e[3])}</td><td><span class="pill">${esc(e[4])}</span></td></tr>`).join("")}
  </table></div><p class="note">Several items are secondary reports, and the Airbus and IPB details vary between them. We found no Kalimantan-wide residue tonnage and no public cost for an Indonesian Fischer-Tropsch plant. The planner workflow described on the Overview is our reasoned assumption.</p></div>
  <div class="card"><h3>About the biomass data</h3><p>The 80 points are official modelling inputs, not surveyed production sites. ${SC ? `${SC.offshore_points.length} of them, holding ${fmt(SC.offshore_points.reduce((a, p) => a + p.kt, 0))} kt, fall off the Natural Earth coastline, up to ${fmt(Math.max(...SC.offshore_points.map((p) => p.km_to_land)), 1)} km from it. We keep them as biomass sources because the coordinates are official, and we do not place plants on them.` : ""}</p></div>
  ${SC ? `<div class="card"><h3>Preliminary site screening, ${SC.radius_km} km radius</h3><div class="scroll"><table><tr><th>Plant</th><th>Near</th><th class="n">To road, m</th><th>Named rivers</th><th class="n">Ports, piers</th><th class="n">Industrial</th><th>Protected nearby</th></tr>
    ${SC.sites.map((r) => `<tr><td>${r.id}</td><td>${esc(r.near)}</td><td class="n">${r.road_m === null ? "n/a" : fmt(r.road_m)}</td>${r.screened ? `<td>${esc(r.rivers.join(", ") || "None mapped")}</td><td class="n">${r.ports}</td><td class="n">${r.industrial}</td><td>${esc(r.protected.join(", ") || "None mapped")}</td>` : '<td colspan="4">Not screened, map service unavailable</td>'}</tr>`).join("")}
  </table></div><p class="note">${esc(SC.note)} Land tenure, peat and forest status are unchecked. This table adds no constraint to the optimiser, which keeps the official great-circle x 1.3 distances.</p></div>` : ""}
  ${OC ? `<div class="card"><h3>Official value check</h3><p>${OC.n} engine inputs were compared with the official workbook and airport file by <code>scripts/check_official.py</code>: <span class="pill ${OC.all_passed ? "good" : "bad"}">${OC.all_passed ? "All match" : "Mismatch found"}</span></p><p class="note">Source: ${esc(OC.source)}. Public data appears only in labelled reality-check scenarios and never in the base case.</p></div>` : ""}
  <div class="card"><h3>Assumption register</h3><div class="scroll"><table><tr><th>Input</th><th>Value</th><th>Status</th><th>Source</th><th>What to check</th></tr>
    ${ASSUMPTIONS.map((r) => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td><span class="pill">${esc(r[2])}</span></td><td>${esc(r[3])}</td><td>${esc(r[4])}</td></tr>`).join("")}
  </table></div><p class="note">Official inputs come from the Airbus update of 31 October 2026, 12:45. Public inputs appear only in labelled reality-check scenarios and never in the base case.</p></div>`;
}

function fillPickers() {
  const opts = state.keys.map((k) => `<option value="${k}">${esc(state.names[k])}</option>`).join("");
  ["#scenario", "#scenario2"].forEach((s) => { $(s).innerHTML = opts; });
  $("#scenario").value = state.cur;
  $("#scenario2").value = state.other;
}

function showTab(id) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.id === id));
  document.querySelectorAll("#tabs button").forEach((b) => {
    const on = b.dataset.t === id;
    b.setAttribute("aria-selected", on);
    b.tabIndex = on ? 0 : -1;
  });
  state.tab = id;
  try { if (location.hash.slice(1) !== id) history.replaceState(null, "", `#${id}`); } catch (e) { /* the address bar is optional */ }
  refresh();
}

// Roving focus for the tab strip: arrows move focus, Enter or Space opens the tab.
function tabKeys(e) {
  const btns = [...document.querySelectorAll("#tabs button")];
  const i = btns.indexOf(document.activeElement);
  if (i < 0) return;
  const to = { ArrowRight: (i + 1) % btns.length, ArrowLeft: (i + btns.length - 1) % btns.length, Home: 0, End: btns.length - 1 }[e.key];
  if (to === undefined) return;
  e.preventDefault();
  btns[to].focus();
}

function refresh() {
  const s = sol();
  const banner = $("#banner");
  banner.hidden = s.status !== "infeasible";
  if (!banner.hidden) banner.textContent = `No feasible network. ${s.message}`;
  const t = state.tab;
  if (t === "overview") renderOverview();
  if (t === "map") renderMap();
  if (t === "scenarios") renderScenarios();
  if (t === "insights") renderInsights();
  if (t === "evaluation") renderEvaluation();
  if (t === "reports") renderReports();
}

async function start() {
  $("#tabs").innerHTML = TABS.map(([id, l]) => `<button role="tab" id="tab-${id}" data-t="${id}" aria-controls="${id}" aria-selected="false" tabindex="-1">${l}</button>`).join("");
  $("#tabs").onkeydown = tabKeys;
  document.querySelectorAll("#tabs button").forEach((b) => { b.onclick = () => showTab(b.dataset.t); });
  const [index, net, base, ladder, sens, highs, check, marginal, depots, screen, official] = await Promise.all(["index", "network", "baselines", "ladder", "sensitivity", "highs_check", "bound_check", "marginal", "depot_check", "site_screen", "official_check"].map(getJson));
  Object.assign(state, { net, base, ladder, sens, highs, check, marginal, depots, screen, official });
  state.net.coords = {};
  net.sites.forEach((s) => { state.net.coords[s.id] = [s.lat, s.lon]; });
  net.airports.forEach((a) => { state.net.coords[a.iata] = [a.lat, a.lon]; });
  const sols = await Promise.all(index.map((i) => getJson(i.key)));
  sols.forEach((s, i) => { s.key = index[i].key; state.sols[s.key] = s; state.names[s.key] = index[i].name; state.keys.push(s.key); });
  fillPickers();
  renderOptimise();
  $("#scenario").onchange = (e) => { state.cur = e.target.value; refresh(); };
  $("#scenario2").onchange = (e) => { state.other = e.target.value; refresh(); };
  $("#compare").onchange = refresh;
  window.addEventListener("hashchange", () => { const w = location.hash.slice(1); if (w !== state.tab && TABS.some(([id]) => id === w)) showTab(w); });
  new MutationObserver(queueEnhance).observe($("main"), { childList: true, subtree: true });
  window.addEventListener("resize", () => queueEnhance());
  const wanted = location.hash.slice(1);
  showTab(TABS.some(([id]) => id === wanted) ? wanted : "overview");
  enhance();
}
start();
