"use strict";
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : Number(x).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d }));
const usd = (x, d = 1) => `USD ${fmt(x, d)}M`;
const COL = { s1: "#3987e5", s2: "#d95926", s3: "#199e70", s4: "#c98500", text: "#f0efec", text2: "#c3c2b7", muted: "#8f8e85", grid: "#2e2d2a" };
const ROLE = { farm: COL.s3, depot: COL.s4, ref: COL.s2, air: COL.s1 };
const AIRPORTS = ["PNK", "PKN", "BPN", "TRK"];
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
  ["Depot placement", "At the refinery", "Derived", "Triangle inequality", "Holds when second-leg tariff x retention is at least the first-leg tariff."],
  ["One refinery per site", "At most one", "Ours", "Modelling choice", "Depot modules may share a site."],
  ["Real jet uplift", "About 100 kt/yr across the four", "Public", "Pertamina press 2024; DGCA and BPS passengers", "Reality check only. PKN and TRK are scaled from passengers."],
  ["Blend reality check", "5% of real uplift", "Public", "Singapore 3 to 5% by 2030", "Reality check only. Indonesia's 1% from 2027 covers Jakarta and Bali departures."],
  ["Road distance check", "OSRM road km", "Public", "OpenStreetMap via OSRM, scripts/build_data.py", "Reality check only."],
];

const state = { keys: [], sols: {}, names: {}, cur: "official_base", other: "field_depots", net: null, base: null, ladder: null, sens: null, highs: null, charts: {}, maps: {}, chat: [], customN: 0 };

const worker = new Worker("worker.js");
const pending = new Map();
let rpcId = 0;
worker.onmessage = (e) => {
  const { id, ok, text, error } = e.data;
  const done = pending.get(id);
  pending.delete(id);
  ok ? done.res(JSON.parse(text)) : done.rej(new Error(error));
};
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

function chart(id, cfg) {
  if (state.charts[id]) state.charts[id].destroy();
  const el = document.getElementById(id);
  if (!el) return;
  Chart.defaults.color = COL.text2;
  Chart.defaults.font.family = 'Inter, "Segoe UI", Arial, sans-serif';
  state.charts[id] = new Chart(el, cfg);
}

function tile(v, l) { return `<div class="tile"><b>${v}</b><span>${l}</span></div>`; }

function renderOverview() {
  const s = sol();
  const el = $("#overview");
  if (!s.refineries.length) {
    el.innerHTML = `<h2>${esc(s.params.name)}</h2><div class="card">${statusPill(s)}<p>${esc(s.message)}</p>${diagHtml(s)}</div>`;
    return;
  }
  const k = s.kpis, c = s.costs;
  const b = state.sols.official_base;
  const f = state.sols.field_depots;
  el.innerHTML = `
  <div class="row between"><h2>${esc(s.params.name)}</h2>${statusPill(s)}</div>
  <div class="tiles">
    ${tile(usd(s.objective), "Total annual cost")}
    ${tile(`USD ${fmt(k.unit_cost_usd_t)}/t`, "Cost per tonne SAF")}
    ${tile(`${k.n_refineries} <small>(${k.n_refineries_large}L, ${k.n_refineries_small}S)</small>`, "Refineries")}
    ${tile(`${k.n_depots} <small>(${k.n_depots_large}L, ${k.n_depots_small}S)</small>`, "Depots")}
    ${tile(`${fmt(k.biomass_used_kt)} kt`, `Biomass used, ${fmt(100 * k.biomass_used_share, 1)}% of supply`)}
    ${tile(`${fmt(k.saf_kt)} kt`, "SAF delivered per year")}
    ${tile(`${fmt(100 * k.fill_rate, 1)}%`, "Demand met")}
    ${tile(s.gap === null ? "n/a" : `${fmt(100 * s.gap, 2)}%`, "Proven gap on candidate sites")}
  </div>
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
      <li>Depots belong at the refinery under these inputs. The second leg costs more per tonne-km than the first and depots lose no mass, so any depot in the field adds cost.</li>
      <li>Field depots with a 60 km gathering radius cost ${usd(f.objective - b.objective)} more per year (+${fmt(100 * (f.objective / b.objective - 1), 1)}%) and cut truck-km by ${fmt(100 * (1 - f.kpis.truck_km_m / b.kpis.truck_km_m), 0)}%, because large trucks do the long haul. That is the trade-off to weigh.</li>
      <li>${b.kpis.sites_skipped.length} of 80 sites are left unused, which accounts for the ${fmt(6800 - b.kpis.biomass_used_kt)} kt not needed.</li>
    </ul></div>`;
  chart("costStack", {
    type: "bar",
    data: { labels: ["Annual cost"], datasets: [
      { label: "Annualised CapEx", data: [c.annual_capex], backgroundColor: COL.s1 },
      { label: "Fixed OpEx", data: [c.opex_fixed], backgroundColor: COL.s2 },
      { label: "Variable OpEx", data: [c.opex_variable], backgroundColor: COL.s3 },
      { label: "Transport", data: [c.logistics_total], backgroundColor: COL.s4 },
    ].map((d) => ({ ...d, borderColor: "#1a1a19", borderWidth: 2, barThickness: 34 })) },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } }, tooltip: { callbacks: { label: (t) => `${t.dataset.label}: USD ${fmt(t.raw, 1)}M (${fmt(100 * t.raw / c.total_annual, 1)}%)` } } },
      scales: { x: { stacked: true, grid: { color: COL.grid }, title: { display: true, text: "USD M per year" } }, y: { stacked: true, display: false } } },
  });
}

function diagHtml(s) {
  if (!s.diagnostics || !s.diagnostics.length) return "";
  return `<table><tr><th>Limit</th><th class="n">Available</th><th class="n">Required</th><th>Why</th><th>What would fix it</th></tr>${s.diagnostics.map((f) => `<tr><td>${esc(f.limit)}</td><td class="n">${fmt(f.available)}</td><td class="n">${fmt(f.required)}</td><td>${esc(f.reason)}</td><td>${esc(f.fix)}</td></tr>`).join("")}</table>`;
}

function popTable(rows) { return `<table class="pop-t">${rows.map(([a, b]) => `<tr><td>${a}</td><td>${b}</td></tr>`).join("")}</table>`; }
function bar(u) { return `<div class="bar"><i style="width:${Math.min(100, 100 * u).toFixed(0)}%"></i></div>`; }

function initMap(id) {
  if (state.maps[id]) return state.maps[id];
  const m = L.map(id, { zoomControl: true }).setView([-0.9, 113.6], 6);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", { attribution: "Tiles &copy; Esri, HERE, Garmin, OpenStreetMap contributors", maxZoom: 12 }).addTo(m);
  const lg = L.control({ position: "bottomleft" });
  lg.onAdd = () => {
    const e = L.DomUtil.create("div", "legend");
    e.innerHTML = `<i style="background:${ROLE.farm};border-radius:50%"></i>Biomass site<br><i style="background:${ROLE.depot};transform:rotate(45deg)"></i>Depot<br><i style="background:${ROLE.ref}"></i>Refinery<br><i style="background:${ROLE.air};border-radius:50%"></i>Airport`;
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
  state.net.sites.forEach((x) => {
    const q = used[x.id] || 0;
    L.circleMarker([x.lat, x.lon], { radius: 2.5 + x.kt / 20, color: ROLE.farm, weight: 1, fillColor: ROLE.farm, fillOpacity: q > 0 ? 0.8 : 0.16 }).bindPopup(`<div class="pop-h">${x.id}</div><div class="pop-s">${esc(x.district)}, ${esc(x.province)}</div>${popTable([["Available", `${fmt(x.kt, 1)} kt/yr`], ["Shipped", `${fmt(q, 1)} kt/yr`]])}${bar(q / x.kt)}`).addTo(lay.farm);
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
      L.marker([list[0].lat, list[0].lon], { icon: L.divIcon({ className: "", html: `<div style="width:${size * 1.4}px;height:${size * 1.4}px;background:${ROLE.depot};border:1px solid #fff;transform:rotate(45deg)"></div>`, iconSize: [size * 2, size * 2], iconAnchor: [ax, ay] }) }).bindPopup(pop).addTo(lay.depot);
    }
  });
  s.refineries.forEach((r) => {
    const z = r.size === "large" ? 11 : 8;
    const d = (byId[r.id] || []).map((x) => `${x.count} ${x.size}`).join(", ");
    L.marker([r.lat, r.lon], { zIndexOffset: 900, icon: L.divIcon({ className: "", html: `<div style="width:${z * 2}px;height:${z * 2}px;border-radius:3px;background:${ROLE.ref};border:2px solid #fff"></div>`, iconSize: [z * 2, z * 2], iconAnchor: [z, z] }) }).bindPopup(`<div class="pop-h">${r.id} refinery</div><div class="pop-s">${r.size}, ${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}<br>${esc(r.near)}</div>${popTable([["Capacity", `${fmt(r.capacity)} kt/yr`], ["Biomass in", `${fmt(r.biomass_in, 1)} kt/yr`], ["SAF out", `${fmt(r.saf_kt, 1)} kt/yr`], ["Utilisation", `${fmt(100 * r.utilisation, 1)}%`]].concat(d ? [["Depots here", d]] : []))}${bar(r.utilisation)}`).addTo(lay.ref);
  });
  state.net.airports.forEach((a, i) => {
    L.marker([a.lat, a.lon], { zIndexOffset: 1000, icon: L.divIcon({ className: "", html: `<div style="width:30px;height:30px;border-radius:50%;background:${ROLE.air};border:2px solid #fff;color:#fff;font:700 10px/26px Arial;text-align:center">${a.iata}</div>`, iconSize: [30, 30], iconAnchor: [15, 15] }) }).bindPopup(`<div class="pop-h">${esc(a.name)}</div><div class="pop-s">${esc(a.city)}${i === 3 ? ", island, barge last leg" : ""}</div>${popTable([["SAF demand", `${fmt(s.kpis.demand_by_airport ? s.kpis.demand_by_airport[i] : 0, 1)} kt/yr`], ["SAF delivered", `${fmt(s.kpis.delivered_by_airport ? s.kpis.delivered_by_airport[i] : 0, 1)} kt/yr`]])}`).addTo(lay.air);
  });
  h.groups = Object.values(lay);
  h.groups.forEach((g) => g.addTo(h.map));
  h.control = L.control.layers(null, { "Biomass sites": lay.farm, Depots: lay.depot, Refineries: lay.ref, Airports: lay.air, "Site to depot": lay.fd, "Depot to refinery": lay.dr, "Refinery to airport": lay.ra }, { collapsed: true, position: "topright" }).addTo(h.map);
  setTimeout(() => h.map.invalidateSize(), 60);
}

function renderMap() {
  const s = sol();
  drawNetwork("map1", s);
  const cmp = $("#compare").checked;
  $("#map2").hidden = !cmp;
  if (cmp) drawNetwork("map2", state.sols[state.other]);
  const skip = s.kpis.sites_skipped || [];
  $("#facilityTables").innerHTML = s.refineries.length ? `
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
  <div class="card"><h3>Sites left unused</h3><p>${skip.length ? skip.join(", ") : "None. Every site ships biomass."}</p></div>` : `<div class="card">${statusPill(s)} ${esc(s.message)}${diagHtml(s)}</div>`;
  const b = $("#csv");
  if (b) b.onclick = () => {
    const rows = [["leg", "from", "to", "kt_per_year", "km", "usd_m_per_year", "mode"]];
    [["farm_depot", s.flows_fd], ["depot_refinery", s.flows_dr], ["refinery_airport", s.flows_ra]].forEach(([l, v]) => v.forEach((f) => rows.push([l, f.src, f.dst, f.kt.toFixed(4), f.km.toFixed(2), f.usd_m.toFixed(5), f.mode])));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" }));
    a.download = `${state.cur}_flows.csv`;
    a.click();
  };
}

const FIELDS = [
  ["PNK demand, kt SAF", "d0", 300], ["PKN demand, kt SAF", "d1", 300], ["BPN demand, kt SAF", "d2", 300], ["TRK demand, kt SAF", "d3", 300],
  ["Yield, t SAF per t biomass", "yield_saf", 0.2, 0.01], ["Biomass availability, x", "biomass_multiplier", 1, 0.05], ["Depot mass retention", "retention", 1, 0.01],
  ["Refinery CapEx, x", "rc", 1, 0.05], ["Depot CapEx, x", "dc", 1, 0.05], ["Large refinery capacity, kt", "cap_l", 1087], ["Small refinery capacity, kt", "cap_s", 500],
  ["Farm to depot, USD/t/km", "tariff_fd", 0.1, 0.01], ["Depot to refinery, USD/t/km", "tariff_dr", 0.12, 0.01], ["Refinery to airport, USD/t/km", "tariff_ra", 0.08, 0.01],
  ["Road factor", "road_factor", 1.3, 0.05], ["Fixed OpEx share", "fixed_opex_frac", 0.05, 0.005], ["CapEx years", "capex_years", 20], ["Max refineries, 0 for none", "max_refineries", 0], ["Solver time limit, s", "time_limit_s", 12],
];

function renderOptimise() {
  $("#optimise").innerHTML = `
  <h2>Run the optimiser</h2>
  <p class="note">The solver runs in your browser. Change any input and press Run. Results join the scenario list above.</p>
  <div class="card"><div class="form">
    ${FIELDS.map(([l, id, v, step]) => `<label>${l}<input type="number" id="f_${id}" value="${v}" step="${step || 1}"></label>`).join("")}
    <label>Depot design<select id="f_mode"><option value="colocated">At the refinery</option><option value="field">In the field</option></select></label>
    <label>Distances<select id="f_basis"><option value="great_circle">Great-circle x road factor</option><option value="road">OSRM road km</option></select></label>
    <label>Name this run<input type="text" id="f_name" value="Custom run"></label>
  </div>
  <div class="row" style="margin-top:12px"><button class="btn" id="run">Run solver</button><button class="btn ghost" id="reset">Reset to official inputs</button><span id="runState" class="note"></span></div></div>
  <div id="runResult"></div>`;
  $("#run").onclick = runCustom;
  $("#reset").onclick = () => FIELDS.forEach(([, id, v]) => { $(`#f_${id}`).value = v; });
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
  const b = $("#run");
  const p = formParams();
  b.disabled = true;
  $("#runState").textContent = `Solving, up to ${p.time_limit_s} s...`;
  const t0 = performance.now();
  try {
    const s = await rpc(1, p);
    const key = `custom_${++state.customN}`;
    s.key = key;
    state.sols[key] = s;
    state.keys.push(key);
    state.names[key] = `${p.name} #${state.customN}`;
    fillPickers();
    $("#runState").textContent = `Finished in ${fmt((performance.now() - t0) / 1000, 1)} s.`;
    const k = s.kpis;
    $("#runResult").innerHTML = `<div class="card"><div class="row between"><h3>${esc(p.name)}</h3>${statusPill(s)}</div>
      ${s.refineries.length ? `<div class="tiles">${tile(usd(s.objective), "Total annual cost")}${tile(`USD ${fmt(k.unit_cost_usd_t)}/t`, "Cost per tonne SAF")}${tile(k.n_refineries, "Refineries")}${tile(k.n_depots, "Depots")}${tile(`${fmt(100 * (s.gap || 0), 2)}%`, "Proven gap")}${tile(s.validation.every((c) => c.passed) ? "All passed" : "Failed", "Constraint audit")}</div><button class="btn ghost" id="showRun">Show on map</button>` : `<p>${esc(s.message)}</p>${diagHtml(s)}`}</div>`;
    const sh = $("#showRun");
    if (sh) sh.onclick = () => { state.cur = key; $("#scenario").value = key; showTab("map"); refresh(); };
  } catch (e) {
    $("#runState").textContent = `The solver stopped: ${e.message}`;
  }
  b.disabled = false;
}

function compareRows(a, b) {
  const g = (s, f) => (s.refineries.length ? f(s) : null);
  const rows = [
    ["Total annual cost, USD M", (s) => s.objective, 1], ["Cost per tonne SAF, USD", (s) => s.kpis.unit_cost_usd_t, 0], ["Refineries", (s) => s.kpis.n_refineries, 0], ["Depots", (s) => s.kpis.n_depots, 0],
    ["Biomass used, kt", (s) => s.kpis.biomass_used_kt, 0], ["SAF delivered, kt", (s) => s.kpis.saf_kt, 0], ["CapEx, USD M", (s) => s.costs.capex_total, 0], ["Transport, USD M/yr", (s) => s.costs.logistics_total, 1],
    ["Mean refinery use, %", (s) => 100 * s.kpis.mean_refinery_utilisation, 1], ["Truck km, millions/yr", (s) => s.kpis.truck_km_m, 1],
  ];
  return rows.map(([l, f, d]) => {
    const x = g(a, f), y = g(b, f);
    const diff = x !== null && y !== null ? y - x : null;
    return `<tr><td>${l}</td><td class="n">${fmt(x, d)}</td><td class="n">${fmt(y, d)}</td><td class="n">${diff === null ? "n/a" : (diff >= 0 ? "+" : "") + fmt(diff, d)}</td></tr>`;
  }).join("");
}

function renderScenarios() {
  const a = sol(), b = state.sols[state.other];
  const list = state.keys.map((k) => state.sols[k]);
  const ok = list.filter((s) => s.refineries.length && s.objective > 200);
  $("#scenarios").innerHTML = `
  <h2>Scenario analysis</h2>
  <div class="card scroll"><table>
    <tr><th>Scenario</th><th>Status</th><th class="n">Annual cost, USD M</th><th class="n">USD/t SAF</th><th class="n">Refineries</th><th class="n">Depots</th><th class="n">Gap</th></tr>
    ${list.map((s) => `<tr><td>${esc(state.names[s.key])}</td><td>${statusPill(s)}</td><td class="n">${fmt(s.objective, 1)}</td><td class="n">${s.refineries.length ? fmt(s.kpis.unit_cost_usd_t) : "n/a"}</td><td class="n">${s.refineries.length ? s.kpis.n_refineries : "n/a"}</td><td class="n">${s.refineries.length ? s.kpis.n_depots : "n/a"}</td><td class="n">${s.gap === null ? "n/a" : fmt(100 * s.gap, 2) + "%"}</td></tr>`).join("")}
  </table></div>
  <div class="grid2">
    <div class="card"><h3>Side by side</h3><div class="row" style="margin-bottom:8px"><span class="note">${esc(state.names[a.key])}</span> vs <select id="cmpPick">${state.keys.map((k) => `<option value="${k}" ${k === state.other ? "selected" : ""}>${esc(state.names[k])}</option>`).join("")}</select></div>
      <div class="scroll"><table><tr><th>Measure</th><th class="n">Selected</th><th class="n">Compared</th><th class="n">Change</th></tr>${compareRows(a, b)}</table></div></div>
    <div class="card"><h3>Cost by scenario, USD M per year</h3><div class="chart tall"><canvas id="scenCost"></canvas></div></div>
  </div>`;
  $("#cmpPick").onchange = (e) => { state.other = e.target.value; $("#scenario2").value = e.target.value; renderScenarios(); };
  const set = (label, f, color) => ({ label, data: ok.map(f), backgroundColor: color, borderColor: "#1a1a19", borderWidth: 2 });
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

const EXAMPLES = ["Why was this refinery selected?", "Which routes are most expensive?", "Why are large depots preferable?", "What happens if demand increases by 10%?", "What happens if demand increases by 20%?", "Which facilities are near capacity?", "How much does this improve on the baseline?", "Show the cost breakdown", "What is the lifecycle CO2 of this network?"];

function renderInsights() {
  $("#insights").innerHTML = `
  <h2>Decision support</h2>
  <p class="note">No language model is used. Questions route by rule to solver records, what-if requests rerun the solver, and every answer lists the fields it read. Questions outside the model are declined. Answers apply to the selected scenario: ${esc(state.names[state.cur])}.</p>
  <div class="card">
    <div class="chips">${EXAMPLES.map((e) => `<button class="chip">${esc(e)}</button>`).join("")}</div>
    <div class="ask"><input type="text" id="q" placeholder="Ask about this network"><button class="btn" id="askBtn">Ask</button></div>
    <div id="chat">${state.chat.join("")}</div>
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
    const html = `<div class="msg q">${esc(q)}</div><div class="msg ${a.declined ? "no" : ""}">${a.declined ? '<span class="pill warn">Declined</span>' : ""}${md(a.text)}${a.sources.length ? `<div class="src">Read from: ${esc(a.sources.join(", "))}</div>` : ""}</div>`;
    state.chat.unshift(html);
    wait.remove();
    box.innerHTML = state.chat.join("");
  } catch (e) {
    wait.textContent = `The engine stopped: ${e.message}`;
  }
  btn.disabled = false;
}

function renderEvaluation() {
  const s = sol(), B = state.base, H = state.highs;
  const rows = [["Optimised, refineries with depots", B.optimised], ["Field depots, 60 km radius", B.field], ["Greedy heuristic", B.greedy], ["Airport-first", B.airport_first]];
  const fails = state.keys.map((k) => state.sols[k]).filter((x) => x.status === "infeasible");
  const v = s.validation || [];
  $("#evaluation").innerHTML = `
  <h2>Evaluation</h2>
  <div class="grid2">
    <div class="card"><h3>Against baselines, same demand and cost basis</h3><div class="chart short"><canvas id="baseChart"></canvas></div>
      <div class="scroll"><table><tr><th>Design</th><th class="n">USD M/yr</th><th class="n">Saving vs this</th><th class="n">Ref</th><th class="n">Dep</th></tr>
      ${rows.map(([l, r], i) => `<tr><td>${l}</td><td class="n">${fmt(r.objective, 1)}</td><td class="n">${i ? `${fmt(r.saving_usd_m, 1)} (${fmt(r.saving_pct, 1)}%)` : "n/a"}</td><td class="n">${r.n_ref}</td><td class="n">${r.n_dep}</td></tr>`).join("")}</table></div>
      <p class="note">Baselines are measured runs of simple planner rules, not estimates of current industry practice.</p></div>
    <div class="card"><h3>How far to trust the optimum</h3><div class="scroll"><table>
      <tr><td>Rust cost, candidate sites</td><td class="n">${usd(B.discrete, 2)}</td></tr>
      <tr><td>Rust proven lower bound</td><td class="n">${usd(B.bound, 2)}</td></tr>
      <tr><td>Cost after continuous refinement</td><td class="n">${usd(B.optimised.objective, 2)}</td></tr>
      ${H ? `<tr><td>${esc(H.solver)} cost, same model</td><td class="n">${usd(H.objective, 2)}</td></tr><tr><td>${esc(H.solver)} lower bound</td><td class="n">${usd(H.bound, 2)}</td></tr>` : ""}
    </table></div>
    <p class="note">The bound applies to the candidate-site problem. Continuous refinement finds a local optimum with no global proof.${H ? " HiGHS is an independent solver reading the same model from a plain LP file." : ""}</p></div>
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
    data: { labels: rows.map((r) => r[0]), datasets: [{ label: "USD M per year", data: rows.map((r) => r[1].objective), backgroundColor: rows.map((_, i) => (i ? COL.muted : COL.s1)), borderRadius: 4, barThickness: 16 }] },
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
  $("#reports").innerHTML = `
  <h2>Reports and data</h2>
  <div class="grid2">
    <div class="card"><h3>Documents</h3><ul>
      <li><a href="reports/Kalimantan_SAF_Technical_Report.pdf">Technical report (PDF)</a></li>
      <li><a href="reports/Kalimantan_SAF_Pitch.pptx">Pitch deck (PowerPoint)</a></li>
      <li><a href="reports/Kalimantan_SAF_Pitch.pdf">Pitch deck (PDF)</a></li>
    </ul></div>
    <div class="card"><h3>Results as data</h3><ul>
      ${state.keys.filter((k) => !k.startsWith("custom")).map((k) => `<li><a href="data/${k}.json">${esc(state.names[k])}</a></li>`).join("")}
    </ul></div>
  </div>
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
  document.querySelectorAll("#tabs button").forEach((b) => b.setAttribute("aria-selected", b.dataset.t === id));
  state.tab = id;
  refresh();
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
  $("#tabs").innerHTML = TABS.map(([id, l]) => `<button role="tab" data-t="${id}">${l}</button>`).join("");
  document.querySelectorAll("#tabs button").forEach((b) => { b.onclick = () => showTab(b.dataset.t); });
  const [index, net, base, ladder, sens, highs] = await Promise.all(["index", "network", "baselines", "ladder", "sensitivity", "highs_check"].map(getJson));
  Object.assign(state, { net, base, ladder, sens, highs });
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
  showTab("overview");
}
start();
