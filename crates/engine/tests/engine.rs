//! Every test here runs the real engine on the official data.
use saf_engine::data::{haversine, network, on_land};
use saf_engine::explain::{answer, parse_change};
use saf_engine::flow::Mcf;
use saf_engine::params::*;
use saf_engine::problem::*;
use saf_engine::solution::Solution;
use saf_engine::validate::{all_passed, check};
use saf_engine::{baseline, diag, run, scenarios};
use std::sync::OnceLock;

fn base() -> &'static Solution {
    static S: OnceLock<Solution> = OnceLock::new();
    S.get_or_init(|| run(&Params { time_limit_s: 8.0, ..Default::default() }))
}

#[test]
fn official_dataset_matches_the_brief() {
    let n = network();
    assert_eq!(n.sites.len(), 80);
    let total: f64 = n.sites.iter().map(|s| s.kt).sum();
    assert!((total - 6800.0).abs() < 0.01);
    assert!(n.sites.iter().all(|s| s.kt >= 20.0 && s.kt <= 100.0));
    assert_eq!(n.airports.iter().map(|a| a.iata.as_str()).collect::<Vec<_>>(), AIRPORTS.to_vec());
    assert!(n.airports.iter().all(|a| a.demand == 300.0));
    assert_eq!(n.airports[1].city, "Pangkalan Bun");
}

#[test]
fn defaults_match_the_official_workbook() {
    let p = Params::default();
    assert_eq!(p.depot_capex, [2.25, 4.5]);
    assert_eq!(p.depot_cap, [150.0, 300.0]);
    assert_eq!(p.depot_var, [5.0, 4.0]);
    assert_eq!(p.refinery_capex, [480.0, 765.0]);
    assert_eq!(p.refinery_cap, [500.0, 1087.0]);
    assert_eq!(p.refinery_var, [60.0, 55.0]);
    assert_eq!((p.tariff_fd, p.tariff_dr, p.tariff_ra), (0.10, 0.12, 0.08));
    assert_eq!((p.yield_saf, p.retention, p.road_factor), (0.20, 1.0, 1.3));
    assert!((p.annual_factor() - 0.10).abs() < 1e-12);
    assert!((p.raw_need() - 6000.0).abs() < 1e-9);
    assert_eq!(p.depot_mode, "colocated");
}

#[test]
fn haversine_matches_a_known_distance() {
    let n = network();
    let (a, b) = (&n.airports[0], &n.airports[3]);
    let km = haversine(a.lat, a.lon, b.lat, b.lon);
    assert!((km - 986.0).abs() < 2.0);
}

#[test]
fn land_mask_separates_land_from_sea() {
    assert!(on_land(-0.5, 114.0));
    assert!(!on_land(-3.0, 118.5));
}

#[test]
fn min_cost_flow_picks_the_cheaper_path() {
    let mut g = Mcf::new(4);
    let a = g.add(0, 1, 5.0, 1.0);
    let b = g.add(0, 2, 5.0, 3.0);
    g.add(1, 3, 5.0, 1.0);
    g.add(2, 3, 5.0, 1.0);
    let (sent, cost) = g.run(0, 3, 7.0);
    assert!((sent - 7.0).abs() < 1e-9);
    assert!((cost - (5.0 * 2.0 + 2.0 * 4.0)).abs() < 1e-9);
    assert!((g.flow(a) - 5.0).abs() < 1e-9);
    assert!((g.flow(b) - 2.0).abs() < 1e-9);
}

#[test]
fn depot_mix_prefers_large_and_covers_throughput() {
    let p = Params::default();
    let m = depot_mix(1000.0, &p);
    let cap = m.n[0] as f64 * 150.0 + m.n[1] as f64 * 300.0;
    assert!(cap >= 1000.0);
    assert_eq!(m.n[1], 3);
    assert!((m.through[0] + m.through[1] - 1000.0).abs() < 1e-9);
}

#[test]
fn base_case_meets_every_constraint() {
    let s = base();
    let p = Params::default();
    assert!(s.has_network());
    assert!(all_passed(&s.validation), "{:?}", s.validation);
    assert_eq!(s.kpis.n_refineries_large, 6);
    assert!((s.kpis.biomass_used_kt - 6000.0).abs() < 1e-3);
    assert!((s.kpis.saf_kt - 1200.0).abs() < 1e-3);
    assert_eq!(s.kpis.sites_used + s.kpis.sites_skipped.len(), 80);
    for a in 0..4 {
        assert!((s.kpis.delivered_by_airport[a] - p.demand[a]).abs() < 1e-3);
    }
}

#[test]
fn proven_gap_is_small_and_bound_is_below_cost() {
    let s = base();
    assert!(s.gap.unwrap() < 0.02, "gap {:?}", s.gap);
    assert!(s.bound.unwrap() <= s.discrete_objective.unwrap() + 1e-6);
}

#[test]
fn refinement_never_costs_more_than_candidate_sites() {
    let s = base();
    assert!(s.objective.unwrap() <= s.discrete_objective.unwrap() + 1e-6);
    assert!(s.refine_saving.unwrap() >= 0.0);
}

#[test]
fn objective_is_the_sum_of_its_parts() {
    let s = base();
    let c = &s.costs;
    let parts = c.annual_capex + c.opex_fixed + c.opex_variable + c.logistics_total;
    assert!((parts - s.objective.unwrap()).abs() < 1e-6);
    assert!((c.annual_capex - c.capex_total / 20.0).abs() < 1e-9);
    assert!((c.opex_fixed - c.capex_total * 0.05).abs() < 1e-9);
}

#[test]
fn validator_catches_tampering() {
    let p = Params::default();
    let mut s = base().clone();
    s.flows_fd[0].kt += 500.0;
    assert!(!all_passed(&check(&s, &p)));
    let mut s = base().clone();
    s.flows_ra[0].kt -= 50.0;
    assert!(!all_passed(&check(&s, &p)));
    let mut s = base().clone();
    s.objective = Some(s.objective.unwrap() * 0.9);
    assert!(!all_passed(&check(&s, &p)));
}

#[test]
fn colocation_is_dominant_only_when_the_second_leg_costs_more() {
    assert!(Params::default().colocation_dominant());
    assert!(!Params { retention: 0.8, ..Default::default() }.colocation_dominant());
    assert!(!Params { tariff_dr: 0.09, ..Default::default() }.colocation_dominant());
}

#[test]
fn field_depots_cost_more_than_colocated_when_dominant() {
    let s = run(&Params { depot_mode: "field".into(), time_limit_s: 6.0, ..Default::default() });
    assert!(all_passed(&s.validation), "{:?}", s.validation);
    assert!(s.objective.unwrap() >= base().discrete_objective.unwrap() - 1e-6);
    assert!(s.flows_fd.iter().all(|f| f.km <= 60.0 * 1.4001));
}

#[test]
fn changing_inputs_changes_the_answer() {
    let dear = run(&Params { tariff_ra: 0.24, time_limit_s: 4.0, ..Default::default() });
    assert!(dear.objective.unwrap() > base().objective.unwrap());
    let less = run(&Params { demand_multiplier: 0.5, time_limit_s: 4.0, ..Default::default() });
    assert!(less.kpis.biomass_used_kt < 3000.5);
    assert!(less.objective.unwrap() < base().objective.unwrap());
}

#[test]
fn higher_yield_needs_less_biomass() {
    let s = run(&Params { yield_saf: 0.25, time_limit_s: 4.0, ..Default::default() });
    assert!((s.kpis.biomass_used_kt - 4800.0).abs() < 1e-3);
    assert!(all_passed(&s.validation));
}

#[test]
fn demand_above_feedstock_is_infeasible_and_explained() {
    let s = run(&Params { demand_multiplier: 1.2, ..Default::default() });
    assert_eq!(s.status, "infeasible");
    assert_eq!(s.diagnostics[0].limit, "Biomass supply");
    assert!(s.diagnostics[0].fix.contains("5.6"));
}

#[test]
fn yield_below_threshold_is_infeasible() {
    assert_eq!(run(&Params { yield_saf: 0.15, ..Default::default() }).status, "infeasible");
    let ok = Params { yield_saf: 0.18, time_limit_s: 3.0, ..Default::default() };
    assert!(diag::diagnose(&ok).is_empty());
}

#[test]
fn too_few_refineries_is_infeasible() {
    let s = run(&Params { max_refineries: 5, ..Default::default() });
    assert_eq!(s.status, "infeasible");
    assert_eq!(s.diagnostics[0].limit, "Refinery count");
}

#[test]
fn baselines_are_valid_and_cost_more() {
    let p = Params::default();
    let o = base().objective.unwrap();
    for b in [baseline::greedy(&p).unwrap(), baseline::airport_first(&p).unwrap()] {
        assert!(all_passed(&b.validation), "{:?}", b.validation);
        assert!(b.objective.unwrap() > o);
    }
}

#[test]
fn every_scenario_name_is_unique_and_core_exists() {
    let all = scenarios::all();
    for k in scenarios::CORE {
        assert!(all.iter().any(|t| t.0 == k));
    }
    let mut names: Vec<_> = all.iter().map(|t| t.0).collect();
    names.sort();
    names.dedup();
    assert_eq!(names.len(), all.len());
}

#[test]
fn explainer_quotes_solver_numbers() {
    let s = base();
    let a = answer("Which routes are most expensive?", s);
    let top = s.flows_fd.iter().chain(&s.flows_ra).max_by(|x, y| x.usd_m.partial_cmp(&y.usd_m).unwrap()).unwrap();
    assert!(a.text.contains(&top.src) && !a.declined);
}

#[test]
fn explainer_declines_what_the_model_cannot_know() {
    let a = answer("What is the lifecycle CO2 of this network?", base());
    assert!(a.declined);
    assert_eq!(a.intent, "declined");
    assert!(answer("Tell me a joke", base()).declined);
}

#[test]
fn explainer_reruns_the_solver_for_what_if() {
    let a = answer("What happens if demand increases by 10%?", base());
    assert_eq!(a.intent, "what_if");
    assert!(a.text.contains("reran"));
    let b = answer("What happens if demand increases by 20%?", base());
    assert!(b.text.contains("infeasible"));
}

#[test]
fn what_if_parser_maps_to_inputs() {
    let p = Params::default();
    let (n, _) = parse_change("transport up 30%", &p).unwrap();
    assert!((n.tariff_fd - 0.13).abs() < 1e-9);
    let (n, _) = parse_change("biomass down 10%", &p).unwrap();
    assert!((n.biomass_multiplier - 0.9).abs() < 1e-9);
    let (n, _) = parse_change("what if yield 0.25", &p).unwrap();
    assert_eq!(n.yield_saf, 0.25);
    assert!(parse_change("hello", &p).is_none());
}
