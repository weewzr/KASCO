//! Deterministic decision support. No language model is involved.
//!
//! A question maps to an intent by keywords. Each intent reads fields from a solver
//! result, what-if requests rerun the real solver, and questions the model cannot
//! answer are declined with a reason.
use crate::params::*;
use crate::solution::Solution;
use crate::{baseline, diag, run};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Answer {
    pub intent: String,
    pub text: String,
    pub sources: Vec<String>,
    pub declined: bool,
}

fn say(intent: &str, text: String, sources: &[&str]) -> Answer {
    Answer { intent: intent.into(), text, sources: sources.iter().map(|s| s.to_string()).collect(), declined: false }
}

fn status_line(s: &Solution) -> String {
    match s.status.as_str() {
        "optimal" => format!("Solver status: optimal on candidate sites, gap {:.2}%.", 100.0 * s.gap.unwrap_or(0.0)),
        "feasible_gap" => format!("Solver status: feasible, gap {:.2}%. Better networks may exist within that margin.", 100.0 * s.gap.unwrap_or(0.0)),
        other => format!("Solver status: {other}."),
    }
}

/// First number in front of a percent sign.
fn pct(q: &str) -> Option<f64> {
    let i = q.find('%')?;
    let head = q[..i].trim_end();
    let start = head.rfind(|c: char| !(c.is_ascii_digit() || c == '.')).map_or(0, |n| n + 1);
    head[start..].parse().ok()
}

/// First number after a keyword.
fn after(q: &str, key: &str) -> Option<f64> {
    let tail = &q[q.find(key)? + key.len()..];
    let start = tail.find(|c: char| c.is_ascii_digit() || c == '.')?;
    let t = &tail[start..];
    let end = t.find(|c: char| !(c.is_ascii_digit() || c == '.')).unwrap_or(t.len());
    t[..end].parse().ok()
}

/// Turns a what-if sentence into new inputs and a description.
pub fn parse_change(q: &str, p: &Params) -> Option<(Params, String)> {
    let ql = q.to_lowercase();
    let has = |w: &[&str]| w.iter().any(|x| ql.contains(x));
    if ql.contains("yield") {
        if let Some(v) = after(&ql, "yield") {
            let v = if v > 1.0 { v / 100.0 } else { v };
            return Some((Params { yield_saf: v, ..p.clone() }, format!("yield set to {v:.2}")));
        }
    }
    if ql.contains("road factor") {
        if let Some(v) = after(&ql, "road factor") {
            return Some((Params { road_factor: v, ..p.clone() }, format!("road factor set to {v:.2}")));
        }
    }
    let sign = if has(&["fall", "drop", "decreas", "reduc", "cut", "lower", "down", "less", "-"]) { -1.0 } else { 1.0 };
    let f = 1.0 + sign * pct(&ql)? / 100.0;
    let label = format!("{:+.0}%", 100.0 * (f - 1.0));
    if has(&["transport", "tariff", "logistic", "truck", "freight"]) {
        return Some((Params { tariff_fd: p.tariff_fd * f, tariff_dr: p.tariff_dr * f, tariff_ra: p.tariff_ra * f, ..p.clone() }, format!("all tariffs changed by {label}")));
    }
    if has(&["biomass", "feedstock", "supply"]) {
        return Some((Params { biomass_multiplier: p.biomass_multiplier * f, ..p.clone() }, format!("biomass changed by {label}")));
    }
    if has(&["refiner"]) {
        return Some((Params { refinery_capex: p.refinery_capex.map(|v| v * f), ..p.clone() }, format!("refinery CapEx changed by {label}")));
    }
    if has(&["depot"]) {
        return Some((Params { depot_capex: p.depot_capex.map(|v| v * f), ..p.clone() }, format!("depot CapEx changed by {label}")));
    }
    if has(&["demand"]) {
        return Some((Params { demand_multiplier: p.demand_multiplier * f, ..p.clone() }, format!("demand changed by {label}")));
    }
    None
}

fn what_if(q: &str, s: &Solution, p: &Params) -> Answer {
    let Some((new, desc)) = parse_change(q, p) else {
        return say("what_if", "I could not map that to a solver input. Try: demand up 10%, transport up 30%, biomass down 10%, yield 0.25, road factor 1.9, refinery cost up 15%.".into(), &[]);
    };
    let t = run(&Params { time_limit_s: 6.0, ..new.clone() });
    if !t.has_network() {
        let rows: Vec<String> = t.diagnostics.iter().map(|f| format!("- **{}**: {} Fix: {}", f.limit, f.reason, f.fix)).collect();
        return say("what_if", format!("Change applied: {desc}. The solver reports **infeasible**.\n\n{}", rows.join("\n")), &["solver rerun", "diagnostics"]);
    }
    let (o0, o1) = (s.objective.unwrap_or(0.0), t.objective.unwrap_or(0.0));
    say(
        "what_if",
        format!(
            "Change applied: {desc}. The solver reran with this input.\n\n- Total cost: USD {o0:.1}M to USD {o1:.1}M per year ({:+.1}%)\n- Unit cost: USD {:.0}/t to USD {:.0}/t SAF\n- Refineries: {} to {}\n- Depots: {} to {}\n- Biomass used: {:.0} kt to {:.0} kt\n\n{}",
            100.0 * (o1 / o0 - 1.0), s.kpis.unit_cost_usd_t, t.kpis.unit_cost_usd_t, s.kpis.n_refineries, t.kpis.n_refineries,
            s.kpis.n_depots, t.kpis.n_depots, s.kpis.biomass_used_kt, t.kpis.biomass_used_kt, status_line(&t)
        ),
        &["solver rerun", "objective", "kpis"],
    )
}

fn why_refinery(q: &str, s: &Solution, p: &Params) -> Answer {
    let ql = q.to_uppercase();
    let r = s.refineries.iter().find(|r| ql.contains(&r.id)).or_else(|| s.refineries.iter().max_by(|a, b| a.throughput.partial_cmp(&b.throughput).unwrap()));
    let Some(r) = r else { return say("refinery", "No refinery is open in this result.".into(), &[]) };
    let feed: Vec<_> = s.flows_fd.iter().filter(|f| f.dst == r.id).collect();
    let total: f64 = feed.iter().map(|f| f.kt).sum();
    let mean = feed.iter().map(|f| f.kt * f.km).sum::<f64>() / total.max(1e-9);
    let dest: Vec<String> = s.flows_ra.iter().filter(|f| f.src == r.id).map(|f| format!("{} ({:.0} kt)", f.dst, f.kt)).collect();
    let mut lines = vec![
        format!("**{}** is a {} refinery at {:.4}, {:.4}, {}. It runs at {:.1}% of {:.0} kt/yr.", r.id, r.size, r.lat, r.lon, r.near, 100.0 * r.utilisation, r.capacity),
        format!("It gathers {:.0} kt biomass from {} sites at a mean {:.0} km, and ships {:.0} kt SAF to {}.", total, feed.len(), mean, r.saf_kt, dest.join(", ")),
    ];
    // Counterfactual: close the three candidate sites nearest this plant.
    let net = crate::data::network();
    let mut near: Vec<(f64, String)> = net.sites.iter().map(|x| (crate::data::haversine(r.lat, r.lon, x.lat, x.lon), x.id.clone())).collect();
    near.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let forbid: Vec<String> = near.into_iter().take(3).map(|t| t.1).collect();
    let alt = run(&Params { forbid: forbid.clone(), time_limit_s: 5.0, refine: false, ..p.clone() });
    let base = s.discrete_objective.or(s.objective).unwrap_or(0.0);
    if let Some(o) = alt.objective {
        lines.push(format!(
            "Counterfactual solve: closing its 3 nearest candidates ({}) gives USD {o:.1}M per year on candidate sites, a change of USD {:+.1}M per year against USD {base:.1}M.",
            forbid.join(", "), o - base
        ));
    }
    say("refinery", lines.join("\n\n"), &["refineries", "flows_fd", "flows_ra", "counterfactual solve"])
}

fn routes(s: &Solution) -> Answer {
    let mut v: Vec<(&str, &crate::solution::Flow)> = s.flows_fd.iter().map(|f| ("farm to depot", f)).chain(s.flows_dr.iter().map(|f| ("depot to refinery", f))).chain(s.flows_ra.iter().map(|f| ("refinery to airport", f))).collect();
    v.sort_by(|a, b| b.1.usd_m.partial_cmp(&a.1.usd_m).unwrap());
    let rows: Vec<String> = v.iter().take(5).enumerate().map(|(n, (leg, f))| format!("{}. {} to {} ({leg}): USD {:.2}M per year, {:.1} kt over {:.0} km", n + 1, f.src, f.dst, f.usd_m, f.kt, f.km)).collect();
    let c = &s.costs;
    say("routes", format!("Five most expensive routes:\n\n{}\n\nAll transport totals USD {:.1}M per year, {:.1}% of annual cost.", rows.join("\n"), c.logistics_total, 100.0 * c.logistics_total / c.total_annual), &["flows_fd", "flows_dr", "flows_ra", "costs"])
}

fn depots(s: &Solution, p: &Params) -> Answer {
    let k = &s.kpis;
    let f = p.annual_factor();
    let unit = |i: usize| 1000.0 * f * p.depot_capex[i] / p.depot_cap[i] + p.depot_var[i];
    let mut t = format!(
        "This network has {} large and {} small depots. At full load a large depot costs USD {:.2}/t and a small one USD {:.2}/t, so large wins on variable cost alone.",
        k.n_depots_large, k.n_depots_small, unit(LARGE), unit(SMALL)
    );
    if s.depots.iter().any(|d| d.colocated) {
        t.push_str(&format!(
            "\n\nDepots sit at refineries because the second leg costs USD {:.2}/t/km against USD {:.2}/t/km for the first, and depots lose no mass. Any depot away from its refinery adds cost by the triangle inequality. Below a retention of {:.3} this reverses.",
            p.tariff_dr, p.tariff_fd, p.tariff_fd / p.tariff_dr
        ));
    }
    say("depots", t, &["kpis", "params.depot_capex", "params.depot_var"])
}

fn capacity(q: &str, s: &Solution) -> Answer {
    let th = pct(q).map_or(0.90, |v| v / 100.0);
    let mut hits: Vec<(String, f64)> = s.refineries.iter().filter(|r| r.utilisation >= th).map(|r| (format!("refinery {} ({})", r.id, r.size), r.utilisation)).collect();
    hits.extend(s.depots.iter().filter(|d| d.utilisation >= th).map(|d| (format!("depot group {} ({} x{})", d.id, d.size, d.count), d.utilisation)));
    hits.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    if hits.is_empty() {
        return say("capacity", format!("No facility is at or above {:.0}% utilisation.", 100.0 * th), &["refineries.utilisation", "depots.utilisation"]);
    }
    let rows: Vec<String> = hits.iter().take(12).map(|(n, u)| format!("- {n}: {:.1}%", 100.0 * u)).collect();
    say("capacity", format!("{} facilities are at or above {:.0}%:\n\n{}", hits.len(), 100.0 * th, rows.join("\n")), &["refineries.utilisation", "depots.utilisation"])
}

fn infeasible(s: &Solution, p: &Params) -> Answer {
    let d = diag::diagnose(p);
    if s.status == "infeasible" || !d.is_empty() {
        let rows: Vec<String> = d.iter().map(|f| format!("- **{}**: {} Fix: {}", f.limit, f.reason, f.fix)).collect();
        return say("infeasible", format!("This scenario has no feasible network.\n\n{}", rows.join("\n")), &["diagnostics"]);
    }
    say("infeasible", format!("This scenario is feasible. {}", status_line(s)), &["status"])
}

fn baseline_cmp(s: &Solution, p: &Params) -> Answer {
    let o = s.objective.unwrap_or(0.0);
    let mut rows = vec![];
    for (label, b) in [("Greedy heuristic", baseline::greedy(p)), ("Airport-first", baseline::airport_first(p))] {
        if let Some(b) = b {
            let c = b.objective.unwrap_or(0.0);
            rows.push(format!("- {label}: USD {c:.1}M per year. The optimised network saves USD {:.1}M per year ({:.1}%).", c - o, 100.0 * (c - o) / c));
        }
    }
    say("baseline", format!("Optimised network: USD {o:.1}M per year on the same demand and cost basis.\n\n{}", rows.join("\n")), &["baselines", "objective"])
}

fn cost(s: &Solution, p: &Params) -> Answer {
    let c = &s.costs;
    say(
        "cost",
        format!(
            "Total USD {:.1}M per year, or USD {:.0}/t SAF.\n\n- Annualised CapEx: USD {:.1}M on USD {:.0}M over {:.0} years\n- Fixed OpEx: USD {:.1}M\n- Variable OpEx: USD {:.1}M\n- Transport: USD {:.1}M",
            c.total_annual, s.kpis.unit_cost_usd_t, c.annual_capex, c.capex_total, p.capex_years, c.opex_fixed, c.opex_variable, c.logistics_total
        ),
        &["costs", "kpis.unit_cost_usd_t"],
    )
}

const OUT_OF_SCOPE: [&str; 15] = ["carbon", "co2", "ghg", "emission", "lifecycle", "selling price", "profit", "npv", "irr", "revenue", "weather", "flood", "deforest", "legal", "permit"];

pub fn answer(question: &str, s: &Solution) -> Answer {
    let q = question.trim().to_lowercase();
    let p = s.params.clone().unwrap_or_default();
    let has = |w: &[&str]| w.iter().any(|x| q.contains(x));
    if q.is_empty() {
        return Answer { intent: "empty".into(), text: "Type a question.".into(), ..Default::default() };
    }
    if has(&OUT_OF_SCOPE) {
        return Answer {
            intent: "declined".into(),
            declined: true,
            text: "I can't answer that. The model holds cost, mass flow and capacity only, so any figure here would be invented. A qualified reviewer needs a separate lifecycle, commercial or regulatory assessment.".into(),
            sources: vec![],
        };
    }
    let net = s.has_network();
    if has(&["infeasib", "no solution", "not feasible"]) {
        return infeasible(s, &p);
    }
    if has(&["what happens", "what if", "suppose", "rerun"]) || (q.contains('%') && has(&["demand", "transport", "biomass", "tariff", "cost up", "cost down"])) {
        return if net { what_if(&q, s, &p) } else { say("what_if", "This scenario has no network to compare with. Switch to a feasible scenario first.".into(), &[]) };
    }
    if !net {
        return infeasible(s, &p);
    }
    if has(&["why"]) && has(&["refiner", "site", "located", "selected", "chosen"]) {
        return why_refinery(question, s, &p);
    }
    if has(&["expensive", "costly", "costliest", "route"]) {
        return routes(s);
    }
    if q.contains("depot") {
        return depots(s, &p);
    }
    if has(&["capacity", "utilisation", "utilization", "bottleneck", "full"]) {
        return capacity(&q, s);
    }
    if has(&["baseline", "improve", "saving", "better than", "compare"]) {
        return baseline_cmp(s, &p);
    }
    if has(&["cost", "breakdown", "total", "unit", "how much"]) {
        return cost(s, &p);
    }
    Answer {
        intent: "unmatched".into(),
        declined: true,
        text: "That question is outside what I can trace to solver output. I can explain refinery choices, route costs, depot sizes, capacity use, infeasibility, baseline savings and what-if changes.".into(),
        sources: vec![],
    }
}
