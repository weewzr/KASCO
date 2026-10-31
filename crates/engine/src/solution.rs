//! Result records. Every cost and KPI is computed here from flows and facility lists.
use crate::data::network;
use crate::params::*;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Flow {
    pub src: String,
    pub dst: String,
    pub kt: f64,
    pub km: f64,
    pub usd_m: f64,
    pub mode: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct DepotRec {
    pub id: String,
    pub size: String,
    pub count: usize,
    pub lat: f64,
    pub lon: f64,
    pub capacity: f64,
    pub throughput: f64,
    pub utilisation: f64,
    pub colocated: bool,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct RefRec {
    pub id: String,
    pub size: String,
    pub lat: f64,
    pub lon: f64,
    pub capacity: f64,
    pub throughput: f64,
    pub biomass_in: f64,
    pub saf_kt: f64,
    pub utilisation: f64,
    pub near: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Costs {
    pub capex_depots: f64,
    pub capex_refineries: f64,
    pub capex_total: f64,
    pub annual_capex: f64,
    pub opex_fixed: f64,
    pub opex_var_depots: f64,
    pub opex_var_refineries: f64,
    pub opex_variable: f64,
    pub logistics_farm_depot: f64,
    pub logistics_depot_refinery: f64,
    pub logistics_refinery_airport: f64,
    pub logistics_total: f64,
    pub total_annual: f64,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Kpis {
    pub biomass_used_kt: f64,
    pub biomass_available_kt: f64,
    pub biomass_used_share: f64,
    pub gate_biomass_kt: f64,
    pub saf_kt: f64,
    pub demand_kt: f64,
    pub demand_by_airport: [f64; 4],
    pub delivered_by_airport: [f64; 4],
    pub fill_rate: f64,
    pub n_depots: usize,
    pub n_depots_small: usize,
    pub n_depots_large: usize,
    pub n_refineries: usize,
    pub n_refineries_small: usize,
    pub n_refineries_large: usize,
    pub unit_cost_usd_t: f64,
    pub mean_refinery_utilisation: f64,
    pub mean_depot_utilisation: f64,
    pub mean_km_farm_depot: f64,
    pub mean_km_depot_refinery: f64,
    pub mean_km_refinery_airport: f64,
    /// Million km driven by large trucks, the lower traffic estimate.
    pub truck_km_m: f64,
    pub sites_used: usize,
    pub sites_skipped: Vec<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Trip {
    pub leg: String,
    pub tonnes: f64,
    pub small_t: f64,
    pub large_t: f64,
    pub trips_small: f64,
    pub trips_large: f64,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Check {
    pub check: String,
    pub passed: bool,
    pub worst: f64,
    pub limit: f64,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Finding {
    pub limit: String,
    pub available: f64,
    pub required: f64,
    pub unit: String,
    pub reason: String,
    pub fix: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Solution {
    pub key: String,
    pub params: Option<Params>,
    /// optimal, feasible_gap, heuristic or infeasible.
    pub status: String,
    pub message: String,
    pub objective: Option<f64>,
    pub bound: Option<f64>,
    pub gap: Option<f64>,
    pub runtime_s: f64,
    pub nodes: usize,
    pub iterations: usize,
    pub discrete_objective: Option<f64>,
    pub refine_saving: Option<f64>,
    pub colocation_dominant: bool,
    pub depots: Vec<DepotRec>,
    pub refineries: Vec<RefRec>,
    pub flows_fd: Vec<Flow>,
    pub flows_dr: Vec<Flow>,
    pub flows_ra: Vec<Flow>,
    pub costs: Costs,
    pub kpis: Kpis,
    pub validation: Vec<Check>,
    pub trips: Vec<Trip>,
    pub diagnostics: Vec<Finding>,
    pub node_coords: BTreeMap<String, [f64; 2]>,
}

impl Solution {
    pub fn has_network(&self) -> bool {
        !self.refineries.is_empty()
    }
}

/// Raw design parts, shared by the solver, field mode and the baselines.
#[derive(Default)]
pub struct Design {
    pub refs: Vec<(String, f64, f64, usize)>,
    pub deps: Vec<(String, f64, f64, [usize; 2], [f64; 2], bool)>,
    /// farm index, depot id, raw kt, km
    pub ff: Vec<(usize, String, f64, f64)>,
    /// depot id, refinery id, kt at gate, km
    pub fr: Vec<(String, String, f64, f64)>,
    /// refinery id, airport index, SAF kt, km
    pub fa: Vec<(String, usize, f64, f64)>,
}

fn nearest_site(lat: f64, lon: f64) -> String {
    let net = network();
    let mut best = (f64::INFINITY, 0);
    for (i, s) in net.sites.iter().enumerate() {
        let d = crate::data::haversine(lat, lon, s.lat, s.lon);
        if d < best.0 {
            best = (d, i);
        }
    }
    let s = &net.sites[best.1];
    format!("{:.0} km from {} ({}, {})", best.0, s.id, s.district, s.province)
}

/// Turns a design into a complete Solution. All totals are computed from scratch.
pub fn assemble(p: &Params, d: &Design) -> Solution {
    let net = network();
    let mut sol = Solution { params: Some(p.clone()), colocation_dominant: p.colocation_dominant(), ..Default::default() };
    let mut rin: BTreeMap<&str, f64> = BTreeMap::new();
    let mut rout: BTreeMap<&str, f64> = BTreeMap::new();
    let mut used = vec![0.0; net.sites.len()];
    for (i, dst, q, km) in &d.ff {
        used[*i] += q;
        sol.flows_fd.push(Flow { src: net.sites[*i].id.clone(), dst: dst.clone(), kt: *q, km: *km, usd_m: q * p.tariff_fd * km / 1000.0, mode: "truck".into() });
    }
    for (src, dst, q, km) in &d.fr {
        *rin.entry(dst.as_str()).or_default() += q;
        sol.flows_dr.push(Flow { src: src.clone(), dst: dst.clone(), kt: *q, km: *km, usd_m: q * p.tariff_dr * km / 1000.0, mode: "truck".into() });
    }
    let mut deliv = [0.0; 4];
    for (src, a, q, km) in &d.fa {
        *rout.entry(src.as_str()).or_default() += q;
        deliv[*a] += q;
        let mode = if *a == ISLAND_AIRPORT { "truck then barge" } else { "truck" };
        sol.flows_ra.push(Flow { src: src.clone(), dst: AIRPORTS[*a].into(), kt: *q, km: *km, usd_m: q * p.tariff_ra * km / 1000.0, mode: mode.into() });
    }

    let f = p.annual_factor();
    let (mut capex_d, mut capex_r, mut var_d, mut var_r) = (0.0, 0.0, 0.0, 0.0);
    for (id, lat, lon, n, thr, co) in &d.deps {
        sol.node_coords.insert(id.clone(), [*lat, *lon]);
        for s in 0..2 {
            if n[s] == 0 {
                continue;
            }
            let cap = n[s] as f64 * p.depot_cap[s];
            capex_d += n[s] as f64 * p.depot_capex[s];
            var_d += thr[s] * p.depot_var[s] / 1000.0;
            sol.depots.push(DepotRec { id: id.clone(), size: SIZES[s].into(), count: n[s], lat: *lat, lon: *lon, capacity: cap, throughput: thr[s], utilisation: thr[s] / cap, colocated: *co });
        }
    }
    for (id, lat, lon, s) in &d.refs {
        sol.node_coords.insert(id.clone(), [*lat, *lon]);
        let cap = p.refinery_cap[*s];
        capex_r += p.refinery_capex[*s];
        let gate = rin.get(id.as_str()).copied().unwrap_or(0.0);
        var_r += gate * p.refinery_var[*s] / 1000.0;
        sol.refineries.push(RefRec {
            id: id.clone(), size: SIZES[*s].into(), lat: *lat, lon: *lon, capacity: cap, throughput: gate, biomass_in: gate,
            saf_kt: rout.get(id.as_str()).copied().unwrap_or(0.0), utilisation: gate / cap, near: nearest_site(*lat, *lon),
        });
    }
    let sum = |v: &Vec<Flow>| v.iter().map(|x| x.usd_m).sum::<f64>();
    let (l1, l2, l3) = (sum(&sol.flows_fd), sum(&sol.flows_dr), sum(&sol.flows_ra));
    let capex = capex_d + capex_r;
    let annual_capex = capex / p.capex_years;
    let opex_fixed = capex * p.fixed_opex_frac;
    let total = annual_capex + opex_fixed + var_d + var_r + l1 + l2 + l3;
    debug_assert!((capex * f - annual_capex - opex_fixed).abs() < 1e-9);
    sol.costs = Costs {
        capex_depots: capex_d, capex_refineries: capex_r, capex_total: capex, annual_capex, opex_fixed,
        opex_var_depots: var_d, opex_var_refineries: var_r, opex_variable: var_d + var_r,
        logistics_farm_depot: l1, logistics_depot_refinery: l2, logistics_refinery_airport: l3,
        logistics_total: l1 + l2 + l3, total_annual: total,
    };
    sol.objective = Some(total);

    let tkm = |v: &Vec<Flow>| v.iter().map(|x| x.kt * x.km).sum::<f64>();
    let raw: f64 = sol.flows_fd.iter().map(|x| x.kt).sum();
    let gate: f64 = sol.flows_dr.iter().map(|x| x.kt).sum();
    let saf: f64 = sol.flows_ra.iter().map(|x| x.kt).sum();
    let avail = net.sites.iter().map(|s| s.kt).sum::<f64>() * p.biomass_multiplier;
    let demand: [f64; 4] = std::array::from_fn(|a| p.demand[a] * p.demand_multiplier);
    let mean = |x: f64, y: f64| if y > 0.0 { x / y } else { 0.0 };
    // One loaded trip per truck, doubled for the empty return.
    let tkm_truck: f64 = 2000.0 * (tkm(&sol.flows_fd) / TRUCKS_T[0][1] + tkm(&sol.flows_dr) / TRUCKS_T[1][1] + tkm(&sol.flows_ra) / TRUCKS_T[2][1]);
    let count = |s: &str| sol.depots.iter().filter(|x| x.size == s).map(|x| x.count).sum::<usize>();
    let cref = |s: &str| sol.refineries.iter().filter(|x| x.size == s).count();
    let nd: usize = sol.depots.iter().map(|x| x.count).sum();
    sol.kpis = Kpis {
        biomass_used_kt: raw, biomass_available_kt: avail, biomass_used_share: mean(raw, avail), gate_biomass_kt: gate, saf_kt: saf,
        demand_kt: demand.iter().sum(), demand_by_airport: demand, delivered_by_airport: deliv,
        fill_rate: mean(saf, demand.iter().sum::<f64>()).min(1.0),
        n_depots: nd, n_depots_small: count("small"), n_depots_large: count("large"),
        n_refineries: sol.refineries.len(), n_refineries_small: cref("small"), n_refineries_large: cref("large"),
        unit_cost_usd_t: mean(total * 1000.0, saf),
        mean_refinery_utilisation: mean(sol.refineries.iter().map(|r| r.utilisation).sum(), sol.refineries.len() as f64),
        mean_depot_utilisation: mean(sol.depots.iter().map(|r| r.throughput).sum(), sol.depots.iter().map(|r| r.capacity).sum()),
        mean_km_farm_depot: mean(tkm(&sol.flows_fd), raw), mean_km_depot_refinery: mean(tkm(&sol.flows_dr), gate),
        mean_km_refinery_airport: mean(tkm(&sol.flows_ra), saf), truck_km_m: tkm_truck / 1e6,
        sites_used: used.iter().filter(|q| **q > 1e-6).count(),
        sites_skipped: net.sites.iter().enumerate().filter(|(i, _)| used[*i] <= 1e-6).map(|(_, s)| s.id.clone()).collect(),
    };
    let legs = [("Farm to depot", raw * 1000.0, 0), ("Depot to refinery", gate * 1000.0, 1), ("Refinery to airport", saf * 1000.0, 2)];
    sol.trips = legs
        .iter()
        .map(|&(leg, t, i)| Trip { leg: leg.into(), tonnes: t, small_t: TRUCKS_T[i][0], large_t: TRUCKS_T[i][1], trips_small: (t / TRUCKS_T[i][0]).ceil(), trips_large: (t / TRUCKS_T[i][1]).ceil() })
        .collect();
    for s in &net.sites {
        sol.node_coords.insert(s.id.clone(), [s.lat, s.lon]);
    }
    for a in &net.airports {
        sol.node_coords.insert(a.iata.clone(), [a.lat, a.lon]);
    }
    sol
}
