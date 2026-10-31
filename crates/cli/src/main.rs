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
        "status": s.status, "objective": s.objective, "unit": s.kpis.unit_cost_usd_t, "gap": s.gap,
        "n_ref": s.kpis.n_refineries, "n_large": s.kpis.n_refineries_large, "n_small": s.kpis.n_refineries_small,
        "n_dep": s.kpis.n_depots, "saf": s.kpis.saf_kt, "biomass": s.kpis.biomass_used_kt, "logistics": s.costs.logistics_total,
        "util": s.kpis.mean_refinery_utilisation, "truck_km_m": s.kpis.truck_km_m,
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
    save("baselines", &json!({
        "optimised": brief(base),
        "discrete": base.discrete_objective,
        "bound": base.bound,
        "greedy": cmp(baseline::greedy(&p0)),
        "airport_first": cmp(baseline::airport_first(&p0)),
        "field": fv,
    }));
    println!("baselines done");

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

/// Writes the strong candidate-site formulation in CPLEX LP format, for the official case.
fn lp(path: &str) {
    let p = Params::default();
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
        Some("lp") => lp(args.get(2).map_or("model.lp", String::as_str)),
        Some("network") => network_json(),
        _ => all(args.get(2).and_then(|a| a.parse().ok()).unwrap_or(30.0)),
    }
}
