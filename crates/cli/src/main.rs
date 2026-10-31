//! Batch runner: solves every scenario and writes the JSON the web app reads.
//!
//!     saf all [seconds]     scenarios, baselines, ladder and sensitivity
//!     saf lp <file>         exports the candidate-site MILP for an independent solver
use saf_engine::params::*;
use saf_engine::problem::Instance;
use saf_engine::solution::Solution;
use saf_engine::{baseline, run, scenarios};
use serde_json::{json, Value};
use std::fmt::Write as _;
use std::fs;
use std::path::Path;

const OUT: &str = "docs/data";

fn save(name: &str, v: &Value) {
    fs::create_dir_all(OUT).unwrap();
    fs::write(Path::new(OUT).join(format!("{name}.json")), serde_json::to_string(v).unwrap()).unwrap();
}

fn parallel<T: Send, F: Fn(usize) -> T + Sync>(n: usize, f: F) -> Vec<T> {
    std::thread::scope(|s| {
        let hs: Vec<_> = (0..n).map(|i| { let f = &f; s.spawn(move || f(i)) }).collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    })
}

fn brief(s: &Solution) -> Value {
    json!({
        "status": s.status, "objective": s.objective, "unit": s.kpis.unit_cost_usd_t, "gap": s.gap, "gap_to_bound": s.gap_to_bound,
        "n_ref": s.kpis.n_refineries, "n_large": s.kpis.n_refineries_large, "n_small": s.kpis.n_refineries_small,
        "n_dep": s.kpis.n_depots, "saf": s.kpis.saf_kt, "biomass": s.kpis.biomass_used_kt, "logistics": s.costs.logistics_total,
        "util": s.kpis.mean_refinery_utilisation, "truck_km_m": s.kpis.truck_km_m, "tonne_km_bn": s.kpis.tonne_km_bn,
    })
}

fn network_json() {
    let n = saf_engine::data::network();
    let land = saf_engine::data::sites_on_land();
    let sites: Vec<Value> = n.sites.iter().enumerate().map(|(i, s)| json!({"id": s.id, "province": s.province, "district": s.district, "kt": s.kt, "lat": s.lat, "lon": s.lon, "on_land": land[i]})).collect();
    let airports: Vec<Value> = n.airports.iter().map(|a| json!({"iata": a.iata, "name": a.name, "city": a.city, "lat": a.lat, "lon": a.lon, "demand": a.demand})).collect();
    save("network", &json!({"sites": sites, "airports": airports}));
}

fn all(secs: f64) {
    network_json();
    let list = scenarios::all();
    let solved = parallel(list.len(), |i| {
        let (key, p) = &list[i];
        let mut s = run(&Params { time_limit_s: secs, ..p.clone() });
        s.key = key.to_string();
        println!("{key}: {} obj {:?} gap {:?} t {:.1}s", s.status, s.objective, s.gap, s.runtime_s);
        s
    });
    let mut index = vec![];
    for s in &solved {
        save(&s.key, &serde_json::to_value(s).unwrap());
        let mut b = brief(s);
        b["key"] = json!(s.key);
        b["name"] = json!(s.params.as_ref().unwrap().name);
        b["runtime_s"] = json!(s.runtime_s);
        b["valid"] = json!(s.validation.iter().all(|c| c.passed));
        b["reason"] = json!(s.diagnostics.first().map(|f| f.reason.clone()));
        index.push(b);
    }
    save("index", &json!(index));

    let base = solved.iter().find(|s| s.key == "official_base").unwrap();
    let o = base.objective.unwrap();
    let p0 = Params::default();
    let cmp = |b: Option<Solution>| {
        let b = b.unwrap();
        let c = b.objective.unwrap();
        let mut v = brief(&b);
        v["message"] = json!(b.message);
        v["valid"] = json!(b.validation.iter().all(|x| x.passed));
        v["saving_usd_m"] = json!(c - o);
        v["saving_pct"] = json!(100.0 * (c - o) / c);
        v
    };
    let field = solved.iter().find(|s| s.key == "field_depots").unwrap();
    let mut fv = brief(field);
    fv["saving_usd_m"] = json!(field.objective.unwrap() - o);
    fv["saving_pct"] = json!(100.0 * (field.objective.unwrap() - o) / field.objective.unwrap());
    let km = baseline::kmeans(&p0, 50).unwrap();
    let share = |c: f64| 100.0 * (c - o) / c;
    save("baselines", &json!({
        "optimised": brief(base),
        "discrete": base.discrete_objective,
        "bound": base.bound,
        "greedy": cmp(baseline::greedy(&p0)),
        "airport_first": cmp(baseline::airport_first(&p0)),
        "field": fv,
        "kmeans": {
            "restarts": km.restarts, "best": km.best, "median": km.median, "worst": km.worst, "valid": km.best_valid,
            "n_ref": km.best_refineries, "n_dep": km.best_depots,
            "best_saving_usd_m": km.best - o, "best_saving_pct": share(km.best),
            "median_saving_usd_m": km.median - o, "median_saving_pct": share(km.median),
        },
    }));
    println!("baselines done");
    marginal(secs);

    let levels = [5.0, 25.0, 50.0, 100.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1360.0];
    let ladder = parallel(levels.len(), |i| {
        let each = levels[i] / 4.0;
        let s = run(&Params { demand: [each; 4], time_limit_s: (secs * 0.6).max(10.0), ..Default::default() });
        let mut b = brief(&s);
        b["level"] = json!(levels[i]);
        b
    });
    save("ladder", &json!(ladder));
    println!("ladder done");

    type Tweak = fn(&Params, f64) -> Params;
    let cases: Vec<(&str, Tweak)> = vec![
        ("Refinery CapEx", |p, f| Params { refinery_capex: p.refinery_capex.map(|v| v * f), ..p.clone() }),
        ("Refinery variable OpEx", |p, f| Params { refinery_var: p.refinery_var.map(|v| v * f), ..p.clone() }),
        ("Transport tariffs", |p, f| Params { tariff_fd: p.tariff_fd * f, tariff_dr: p.tariff_dr * f, tariff_ra: p.tariff_ra * f, ..p.clone() }),
        ("Road factor", |p, f| Params { road_factor: p.road_factor * f, ..p.clone() }),
        ("Fixed OpEx share", |p, f| Params { fixed_opex_frac: p.fixed_opex_frac * f, ..p.clone() }),
        ("SAF yield", |p, f| Params { yield_saf: p.yield_saf * f, ..p.clone() }),
        ("Biomass supply", |p, f| Params { biomass_multiplier: p.biomass_multiplier * f, ..p.clone() }),
    ];
    let rows = parallel(cases.len(), |i| {
        let (name, tw) = cases[i];
        let t = (secs * 0.5).max(8.0);
        let lo = run(&Params { time_limit_s: t, ..tw(&p0, 0.8) });
        let hi = run(&Params { time_limit_s: t, ..tw(&p0, 1.2) });
        json!({"name": name, "low": brief(&lo), "high": brief(&hi), "low_finding": lo.diagnostics.first().map(|f| f.reason.clone())})
    });
    save("sensitivity", &json!({"base": o, "base_unit": base.kpis.unit_cost_usd_t, "rows": rows}));
    println!("sensitivity done");
}

/// Stress test of the candidate restriction: adds a land grid of extra refinery sites.
fn grid(secs: f64) {
    use saf_engine::data::{haversine, network, on_land};
    use saf_engine::problem::Cand;
    let net = network();
    let p = Params { time_limit_s: secs, refine: false, ..Default::default() };
    let mut inst = Instance::new(&p);
    let before = inst.cand.len();
    let (mut lat, mut added) = (-4.2, 0);
    while lat < 3.2 {
        let mut lon = 109.0;
        while lon < 118.0 {
            let near = net.sites.iter().map(|s| haversine(lat, lon, s.lat, s.lon)).fold(f64::INFINITY, f64::min);
            if near < 90.0 && on_land(lat, lon) {
                inst.push_cand(Cand { id: format!("G{added}"), lat, lon });
                added += 1;
            }
            lon += 0.2;
        }
        lat += 0.2;
    }
    let o = saf_engine::solver::optimise(&inst).unwrap();
    let r = saf_engine::location::refine(&mut inst, &o.open, &o.alloc);
    save("grid_check", &json!({"candidates": before, "grid_added": added, "spacing_deg": 0.2, "candidate_cost": o.ub, "bound": o.lb, "refined_cost": r.cost}));
    println!("grid: {before}+{added} candidates, cost {:.3}, refined {:.3}, bound {:.3}", o.ub, r.cost, o.lb);
}

/// Finite-difference planning estimates on candidate sites. Integer plant decisions mean
/// these are not shadow prices, and a step in cost is expected at capacity thresholds.
fn marginal(secs: f64) {
    let p0 = Params { refine: false, ..Default::default() };
    let t = (secs * 0.5).max(10.0);
    let base = run(&Params { time_limit_s: secs, ..p0.clone() });
    let c0 = base.objective.unwrap();
    let cases: Vec<(String, f64, Params)> = [10.0, 25.0, 50.0, 100.0, 104.0, 105.0, 120.0, 150.0]
        .iter()
        .map(|&d| (format!("Demand +{d:.0} kt"), d, Params { demand: [300.0 + d / 4.0; 4], ..p0.clone() }))
        .chain([
            ("Large refinery capacity +100 kt".to_string(), 0.0, Params { refinery_cap: [500.0, 1187.0], ..p0.clone() }),
            ("Biomass supply -5%".to_string(), 0.0, Params { biomass_multiplier: 0.95, ..p0.clone() }),
            ("Biomass supply -10%".to_string(), 0.0, Params { biomass_multiplier: 0.90, ..p0.clone() }),
            ("Biomass supply -12%".to_string(), 0.0, Params { biomass_multiplier: 0.88, ..p0.clone() }),
            ("Transport tariffs +10%".to_string(), 0.0, Params { tariff_fd: 0.11, tariff_dr: 0.132, tariff_ra: 0.088, ..p0.clone() }),
            ("Transport tariffs +20%".to_string(), 0.0, Params { tariff_fd: 0.12, tariff_dr: 0.144, tariff_ra: 0.096, ..p0.clone() }),
        ])
        .collect();
    let rows = parallel(cases.len(), |i| {
        let (label, d, p) = &cases[i];
        let s = run(&Params { time_limit_s: t, ..p.clone() });
        let c = s.objective;
        json!({
            "label": label, "extra_kt": d, "cost": c, "delta": c.map(|x| x - c0), "usd_per_t": c.filter(|_| *d > 0.0).map(|x| (x - c0) * 1000.0 / d),
            "n_large": s.kpis.n_refineries_large, "n_small": s.kpis.n_refineries_small, "n_dep": s.kpis.n_depots,
            "gap": s.gap, "status": s.status, "reason": s.diagnostics.first().map(|f| f.reason.clone()),
        })
    });
    save("marginal", &json!({"base": c0, "base_gap": base.gap, "rows": rows}));
    println!("marginal done");
}

/// Writes the strong candidate-site formulation in CPLEX LP format, for the official case.
fn lp(path: &str, demand: f64) {
    let p = Params { demand: [demand; 4], ..Default::default() };
    let inst = Instance::new(&p);
    let (nf, nk) = (inst.farm_kt.len(), inst.cand.len());
    let mut s = String::from("Minimize\n obj:");
    let f = p.annual_factor();
    for k in 0..nk {
        for t in 0..2 {
            write!(s, " + {:.8} z{k}_{t} + {:.8} n{k}_{t}", f * p.refinery_capex[t], f * p.depot_capex[t]).unwrap();
            write!(s, " + {:.8} t{k}_{t} + {:.8} r{k}_{t}", p.depot_var[t] / 1000.0, p.refinery_var[t] / 1000.0).unwrap();
        }
        for i in 0..nf {
            write!(s, " + {:.8} x{i}_{k}", inst.c(i, k)).unwrap();
        }
        for a in 0..4 {
            write!(s, " + {:.8} v{k}_{a}", p.tariff_ra * inst.d_ca[k][a] / 1000.0).unwrap();
        }
        s.push('\n');
    }
    s.push_str("Subject To\n");
    for i in 0..nf {
        let row: Vec<String> = (0..nk).map(|k| format!("x{i}_{k}")).collect();
        writeln!(s, " sup{i}: {} <= {:.6}", row.join(" + "), inst.farm_kt[i]).unwrap();
    }
    for k in 0..nk {
        let row: Vec<String> = (0..nf).map(|i| format!("x{i}_{k}")).collect();
        writeln!(s, " dep{k}: {} - t{k}_0 - t{k}_1 = 0", row.join(" + ")).unwrap();
        writeln!(s, " bal{k}: t{k}_0 + t{k}_1 - r{k}_0 - r{k}_1 = 0").unwrap();
        writeln!(s, " one{k}: z{k}_0 + z{k}_1 <= 1").unwrap();
        for t in 0..2 {
            writeln!(s, " dc{k}_{t}: t{k}_{t} - {:.1} n{k}_{t} <= 0", p.depot_cap[t]).unwrap();
            writeln!(s, " rc{k}_{t}: r{k}_{t} - {:.1} z{k}_{t} <= 0", p.refinery_cap[t]).unwrap();
        }
        writeln!(s, " con{k}: v{k}_0 + v{k}_1 + v{k}_2 + v{k}_3 - {y} r{k}_0 - {y} r{k}_1 = 0", y = p.yield_saf).unwrap();
        for i in 0..nf {
            writeln!(s, " lx{i}_{k}: x{i}_{k} - {b:.6} z{k}_0 - {b:.6} z{k}_1 <= 0", b = inst.farm_kt[i]).unwrap();
        }
        for a in 0..4 {
            writeln!(s, " lv{k}_{a}: v{k}_{a} - {d} z{k}_0 - {d} z{k}_1 <= 0", d = p.demand[a]).unwrap();
        }
    }
    for a in 0..4 {
        let row: Vec<String> = (0..nk).map(|k| format!("v{k}_{a}")).collect();
        writeln!(s, " dem{a}: {} >= {}", row.join(" + "), p.demand[a]).unwrap();
    }
    s.push_str("Bounds\n");
    for k in 0..nk {
        for t in 0..2 {
            writeln!(s, " 0 <= n{k}_{t} <= 8").unwrap();
        }
    }
    s.push_str("General\n");
    for k in 0..nk {
        for t in 0..2 {
            writeln!(s, " n{k}_{t}").unwrap();
        }
    }
    s.push_str("Binary\n");
    for k in 0..nk {
        for t in 0..2 {
            writeln!(s, " z{k}_{t}").unwrap();
        }
    }
    s.push_str("End\n");
    fs::write(path, s).unwrap();
    println!("wrote {path}: {nk} candidates, {nf} sites");
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("lp") => lp(args.get(2).map_or("model.lp", String::as_str), args.get(3).and_then(|a| a.parse().ok()).unwrap_or(300.0)),
        Some("network") => network_json(),
        Some("marginal") => marginal(args.get(2).and_then(|a| a.parse().ok()).unwrap_or(30.0)),
        Some("grid") => grid(args.get(2).and_then(|a| a.parse().ok()).unwrap_or(100.0)),
        Some("params") => save("params", &serde_json::to_value(Params::default()).unwrap()),
        Some("bound") => {
            // Reports the Rust cost and bound for one demand level, for comparison with HiGHS.
            let d: f64 = args.get(2).and_then(|a| a.parse().ok()).unwrap_or(300.0);
            let t: f64 = args.get(3).and_then(|a| a.parse().ok()).unwrap_or(30.0);
            let s = run(&Params { demand: [d; 4], refine: false, time_limit_s: t, ..Default::default() });
            println!("{}", json!({"demand_each": d, "status": s.status, "objective": s.objective, "bound": s.bound, "gap": s.gap, "runtime_s": s.runtime_s}));
        }
        _ => all(args.get(2).and_then(|a| a.parse().ok()).unwrap_or(30.0)),
    }
}
