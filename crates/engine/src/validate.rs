//! Independent audit of a finished network.
//!
//! It reads only flow records, facility records and official inputs. Nothing here
//! shares code with the solver, so a modelling slip cannot pass in both places.
use crate::data::{haversine, network, on_land};
use crate::params::*;
use crate::solution::*;
use std::collections::BTreeMap;

const TOL: f64 = 1e-3;

pub fn check(sol: &Solution, p: &Params) -> Vec<Check> {
    let net = network();
    let mut out = vec![];
    let mut rec = |name: &str, worst: f64, limit: f64| {
        out.push(Check { check: name.into(), passed: worst <= limit, worst, limit });
    };
    let supply: BTreeMap<&str, f64> = net.sites.iter().map(|s| (s.id.as_str(), s.kt * p.biomass_multiplier)).collect();
    let mut shipped: BTreeMap<&str, f64> = BTreeMap::new();
    let (mut dep_in, mut dep_out, mut ref_in, mut ref_out): (BTreeMap<&str, f64>, BTreeMap<&str, f64>, BTreeMap<&str, f64>, BTreeMap<&str, f64>) = Default::default();
    let mut air_in = [0.0; 4];
    for f in &sol.flows_fd {
        *shipped.entry(&f.src).or_default() += f.kt;
        *dep_in.entry(&f.dst).or_default() += f.kt;
    }
    for f in &sol.flows_dr {
        *dep_out.entry(&f.src).or_default() += f.kt;
        *ref_in.entry(&f.dst).or_default() += f.kt;
    }
    for f in &sol.flows_ra {
        *ref_out.entry(&f.src).or_default() += f.kt;
        let a = AIRPORTS.iter().position(|x| *x == f.dst).unwrap();
        air_in[a] += f.kt;
    }
    let over = shipped.iter().map(|(k, q)| q - supply.get(k).copied().unwrap_or(0.0)).fold(0.0, f64::max);
    rec("Biomass availability at each site (kt over)", over, TOL);

    let mut dep_cap: BTreeMap<&str, f64> = BTreeMap::new();
    for d in &sol.depots {
        let s = SIZES.iter().position(|x| *x == d.size).unwrap();
        *dep_cap.entry(&d.id).or_default() += d.count as f64 * p.depot_cap[s];
    }
    let mut refs: BTreeMap<&str, f64> = BTreeMap::new();
    for r in &sol.refineries {
        let s = SIZES.iter().position(|x| *x == r.size).unwrap();
        *refs.entry(&r.id).or_default() += p.refinery_cap[s];
    }
    let closed = dep_in.keys().filter(|k| !dep_cap.contains_key(*k)).count() + ref_in.keys().filter(|k| !refs.contains_key(*k)).count();
    rec("Flows only through opened facilities (count)", closed as f64, 0.0);

    let over = dep_in.iter().map(|(k, q)| q - dep_cap.get(k).copied().unwrap_or(0.0)).fold(0.0, f64::max);
    rec("Depot capacity (kt over)", over, TOL);
    let bal = dep_in.iter().map(|(k, q)| (dep_out.get(k).copied().unwrap_or(0.0) - p.retention * q).abs()).fold(0.0, f64::max);
    rec("Depot mass balance, zero loss (kt residual)", bal, TOL);
    let over = ref_in.iter().map(|(k, q)| q - refs.get(k).copied().unwrap_or(0.0)).fold(0.0, f64::max);
    rec("Refinery capacity on biomass intake (kt over)", over, TOL);
    let bal = ref_in.iter().map(|(k, q)| (ref_out.get(k).copied().unwrap_or(0.0) - p.yield_saf * q).abs()).fold(0.0, f64::max);
    rec("Refinery yield balance (kt residual)", bal, TOL);
    let short = (0..4).map(|a| p.demand[a] * p.demand_multiplier - air_in[a]).fold(0.0, f64::max);
    rec("Airport demand met at all four (kt short)", short, TOL);

    let offland = sol.refineries.iter().filter(|r| !net.sites.iter().any(|s| s.id == r.id) && !on_land(r.lat, r.lon) && !AIRPORTS.contains(&r.id.as_str())).count();
    rec("Refined sites on land (count off land)", offland as f64, 0.0);
    let island = sol.refineries.iter().filter(|r| r.id == AIRPORTS[ISLAND_AIRPORT]).count();
    rec("No refinery on Tarakan island (count)", island as f64, 0.0);

    if p.distance_basis == "great_circle" {
        let mut worst: f64 = 0.0;
        for f in sol.flows_fd.iter().chain(&sol.flows_dr).chain(&sol.flows_ra) {
            let (a, b) = (sol.node_coords[&f.src], sol.node_coords[&f.dst]);
            worst = worst.max((haversine(a[0], a[1], b[0], b[1]) * p.road_factor - f.km).abs());
        }
        rec("Route km equal great-circle x road factor (km residual)", worst, TOL);
    }

    let capex: f64 = sol.depots.iter().map(|d| d.count as f64 * p.depot_capex[SIZES.iter().position(|x| *x == d.size).unwrap()]).sum::<f64>()
        + sol.refineries.iter().map(|r| p.refinery_capex[SIZES.iter().position(|x| *x == r.size).unwrap()]).sum::<f64>();
    let var: f64 = sol.depots.iter().map(|d| d.throughput * p.depot_var[SIZES.iter().position(|x| *x == d.size).unwrap()]).sum::<f64>() / 1000.0
        + sol.refineries.iter().map(|r| r.biomass_in * p.refinery_var[SIZES.iter().position(|x| *x == r.size).unwrap()]).sum::<f64>() / 1000.0;
    let leg = |v: &Vec<Flow>, t: f64| v.iter().map(|f| f.kt * f.km * t).sum::<f64>() / 1000.0;
    let total = capex / p.capex_years + capex * p.fixed_opex_frac + var + leg(&sol.flows_fd, p.tariff_fd) + leg(&sol.flows_dr, p.tariff_dr) + leg(&sol.flows_ra, p.tariff_ra);
    let diff = (total - sol.objective.unwrap_or(0.0)).abs() / total.max(1.0);
    rec("Objective recomputed from flows (relative difference)", diff, 1e-6);
    out
}

pub fn all_passed(v: &[Check]) -> bool {
    v.iter().all(|c| c.passed)
}
