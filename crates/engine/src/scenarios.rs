//! Named scenarios shipped with the app. Every one is solved, none is hard-coded.
use crate::params::Params;

const UPLIFT: &str = include_str!("../../../data/real_uplift.csv");

/// Estimated real jet uplift in kt/yr, derived by scripts/fetch_context.py. Used only
/// in the labelled reality-check scenario.
pub fn real_uplift_kt() -> [f64; 4] {
    let v: Vec<f64> = UPLIFT.lines().skip(1).filter_map(|l| l.trim().split(',').nth(1)?.parse().ok()).collect();
    [v[0], v[1], v[2], v[3]]
}

pub fn all() -> Vec<(&'static str, Params)> {
    let base = Params::default;
    let named = |name: &str, p: Params| Params { name: name.into(), ..p };
    vec![
        ("official_base", base()),
        ("field_depots", named("Field depots, 60 km gathering radius", Params { depot_mode: "field".into(), ..base() })),
        ("high_demand", named("High demand, +10%", Params { demand_multiplier: 1.10, ..base() })),
        ("high_transport", named("High transport cost, +50%", Params { tariff_fd: 0.15, tariff_dr: 0.18, tariff_ra: 0.12, ..base() })),
        ("infeasible_demand", named("Infeasible: demand +20%", Params { demand_multiplier: 1.20, ..base() })),
        ("low_yield", named("Infeasible: yield 0.15", Params { yield_saf: 0.15, ..base() })),
        ("max_five_refineries", named("Infeasible: at most 5 refineries", Params { max_refineries: 5, ..base() })),
        ("all_feedstock", named("All 6,800 kt used, 340 kt per airport", Params { demand: [340.0; 4], ..base() })),
        ("road_distance", named("Reality check: OSRM road distances", Params { distance_basis: "road".into(), refine: false, ..base() })),
        ("real_blend", named("Reality check: real uplift at 5% blend", Params { demand: real_uplift_kt().map(|u| u * 0.05), ..base() })),
    ]
}

/// The four cases the brief asks to compare side by side.
pub const CORE: [&str; 4] = ["official_base", "high_demand", "high_transport", "infeasible_demand"];
