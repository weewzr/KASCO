//! Deterministic decision support. No language model is involved.
//!
//! A question maps to an intent by keywords. Each intent reads fields from a solver
//! result, what-if requests rerun the real solver, and questions the model cannot
//! answer are declined with a reason. A what-if request runs only when every part of
//! it maps to a validated input, so a partly understood question never runs silently.
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
        "heuristic" => match s.gap_to_bound {
            Some(g) => format!("Solver status: heuristic with no optimality proof, {:.2}% above the proven bound.", 100.0 * g),
            None => "Solver status: heuristic with no optimality proof.".into(),
        },
        other => format!("Solver status: {other}."),
    }
}

/// Whole words of a clause, so "up" cannot match inside "supply".
fn words(c: &str) -> Vec<&str> {
    c.split(|ch: char| !ch.is_ascii_alphanumeric()).filter(|w| !w.is_empty()).collect()
}

/// +1 for a rise, -1 for a fall, 0 when the clause gives no direction or both.
fn direction(c: &str) -> i32 {
    let w = words(c);
    let any = |exact: &[&str], stems: &[&str]| w.iter().any(|x| exact.contains(x) || stems.iter().any(|s| x.starts_with(s)));
    let up = any(&["up", "more", "rise", "rises", "rose", "rising", "add", "adds"], &["increas", "rais", "grow", "higher", "hike"]);
    let down = any(&["down", "less", "cut", "cuts", "fall", "falls", "fell", "falling"], &["decreas", "reduc", "drop", "lower", "declin", "shrink"]);
    match (up, down) {
        (true, false) => 1,
        (false, true) => -1,
        _ => 0,
    }
}

/// First number in a clause, with any sign written directly in front of it.
fn number(c: &str) -> Option<(f64, Option<f64>)> {
    let b = c.as_bytes();
    let start = (0..b.len()).find(|&i| b[i].is_ascii_digit() || (b[i] == b'.' && i + 1 < b.len() && b[i + 1].is_ascii_digit()))?;
    let end = (start..b.len()).find(|&i| !(b[i].is_ascii_digit() || b[i] == b'.')).unwrap_or(b.len());
    let v: f64 = c[start..end].trim_end_matches('.').parse().ok()?;
    let sign = match start.checked_sub(1).map(|i| b[i]) {
        Some(b'+') => Some(1.0),
        Some(b'-') => Some(-1.0),
        _ => None,
    };
    Some((v, sign))
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum Topic {
    Demand(Option<usize>),
    Tariff(Option<usize>),
    Biomass,
    Yield,
    RoadFactor,
    RefineryCapex,
    DepotCapex,
    Capex,
    RefineryCap,
    DepotCap,
    RefineryVar,
    DepotVar,
    VarOpex,
    FixedOpex,
    CapexYears,
    MaxRefineries,
    Refinery,
    Depot,
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum Val {
    /// Multiply the input by this factor.
    Factor(f64),
    /// Set the input to this value.
    Set(f64),
}

fn topic_of(c: &str) -> Option<Topic> {
    let has = |w: &[&str]| w.iter().any(|x| c.contains(x));
    let port = [["pnk", "pontianak", "supadio"], ["pkn", "pangkalan", "iskandar"], ["bpn", "balikpapan", "sepinggan"], ["trk", "tarakan", "juwata"]].iter().position(|names| names.iter().any(|n| c.contains(n)));
    let leg = [["farm to depot", "site to depot", "first leg"], ["depot to refinery", "second leg", "depot-to-refinery"], ["refinery to airport", "last leg", "saf transport"]].iter().position(|names| names.iter().any(|n| c.contains(n)));
    let (r, d) = (c.contains("refiner"), c.contains("depot"));
    if leg.is_some() || has(&["transport", "tariff", "logistic", "truck", "freight", "haul", "shipping"]) {
        return Some(Topic::Tariff(leg));
    }
    if r && has(&["at most", "no more than", "max", "limit", "only"]) {
        return Some(Topic::MaxRefineries);
    }
    if has(&["road factor", "distance", "circuity"]) {
        return Some(Topic::RoadFactor);
    }
    if c.contains("yield") {
        return Some(Topic::Yield);
    }
    if has(&["fixed opex", "fixed cost", "fixed operating"]) {
        return Some(Topic::FixedOpex);
    }
    if has(&["capex life", "plant life", "capex years", "depreciation"]) {
        return Some(Topic::CapexYears);
    }
    if has(&["variable opex", "variable cost", "variable operating"]) {
        return Some(if r { Topic::RefineryVar } else if d { Topic::DepotVar } else { Topic::VarOpex });
    }
    if c.contains("capacity") {
        return if r { Some(Topic::RefineryCap) } else if d { Some(Topic::DepotCap) } else { None };
    }
    if has(&["capex", "capital", "cost", "price", "construction"]) {
        if r {
            return Some(Topic::RefineryCapex);
        }
        if d {
            return Some(Topic::DepotCapex);
        }
        if has(&["capex", "capital"]) {
            return Some(Topic::Capex);
        }
    }
    if has(&["biomass", "feedstock", "supply"]) {
        return Some(Topic::Biomass);
    }
    if c.contains("demand") {
        return Some(Topic::Demand(port));
    }
    if r {
        return Some(Topic::Refinery);
    }
    if d {
        return Some(Topic::Depot);
    }
    None
}

/// The amount a clause asks for. Direction is required for a percentage, except for
/// inputs that are themselves shares, where a bare figure sets the value.
fn value_of(c: &str, t: Option<Topic>) -> Option<Val> {
    let w = words(c);
    let stem = |s: &str| w.iter().any(|x| x.starts_with(s));
    if stem("doubl") {
        return Some(Val::Factor(2.0));
    }
    if stem("tripl") {
        return Some(Val::Factor(3.0));
    }
    if stem("halv") || w.contains(&"half") {
        return Some(Val::Factor(0.5));
    }
    let (v, sign) = number(c)?;
    let pct = c.contains('%') || c.contains("percent");
    let dir = direction(c);
    if pct {
        let s = sign.or(if dir != 0 { Some(dir as f64) } else { None });
        return match (s, t) {
            (Some(s), _) => Some(Val::Factor(1.0 + s * v / 100.0)),
            (None, Some(Topic::Yield | Topic::FixedOpex)) => Some(Val::Set(v / 100.0)),
            _ => None,
        };
    }
    if dir != 0 || sign.is_some() {
        return None;
    }
    match t {
        Some(Topic::Yield | Topic::RoadFactor | Topic::FixedOpex | Topic::CapexYears | Topic::MaxRefineries | Topic::RefineryCap | Topic::DepotCap | Topic::Demand(_)) => Some(Val::Set(v)),
        _ => None,
    }
}

fn pct_label(f: f64) -> String {
    format!("{:+.1}%", 100.0 * (f - 1.0))
}

/// Applies one change. Returns its description, or None if the amount does not fit.
fn apply(p: &mut Params, t: Topic, v: Val, c: &str) -> Option<String> {
    let sizes: Vec<usize> = if c.contains("small") { vec![SMALL] } else if c.contains("large") { vec![LARGE] } else { vec![SMALL, LARGE] };
    let size = if sizes.len() == 1 { format!("{} ", SIZES[sizes[0]]) } else { String::new() };
    let scale = |a: &mut [f64; 2], f: f64| sizes.iter().for_each(|&s| a[s] *= f);
    let set = |a: &mut [f64; 2], x: f64| sizes.iter().for_each(|&s| a[s] = x);
    let pair = |a: &mut [f64; 2], label: &str, v: Val| match v {
        Val::Factor(f) => {
            scale(a, f);
            format!("{size}{label} {}", pct_label(f))
        }
        Val::Set(x) => {
            set(a, x);
            format!("{size}{label} set to {x:.0}")
        }
    };
    let text = match t {
        Topic::Demand(port) => match (v, port) {
            (Val::Factor(f), None) => {
                p.demand_multiplier *= f;
                format!("demand {}", pct_label(f))
            }
            (Val::Factor(f), Some(a)) => {
                p.demand[a] *= f;
                format!("{} demand {}", AIRPORTS[a], pct_label(f))
            }
            (Val::Set(x), Some(a)) => {
                p.demand[a] = x / p.demand_multiplier;
                format!("{} demand set to {x:.0} kt", AIRPORTS[a])
            }
            (Val::Set(x), None) => {
                let each = if c.contains("per airport") || c.contains("each") { x } else { x / 4.0 };
                p.demand = [each / p.demand_multiplier; 4];
                format!("demand set to {each:.0} kt per airport")
            }
        },
        Topic::Tariff(leg) => {
            let Val::Factor(f) = v else { return None };
            match leg {
                Some(0) => p.tariff_fd *= f,
                Some(1) => p.tariff_dr *= f,
                Some(_) => p.tariff_ra *= f,
                None => {
                    p.tariff_fd *= f;
                    p.tariff_dr *= f;
                    p.tariff_ra *= f;
                }
            }
            let name = ["first-leg tariff", "second-leg tariff", "last-leg tariff"];
            format!("{} {}", leg.map_or("all tariffs", |l| name[l]), pct_label(f))
        }
        Topic::Biomass => {
            let Val::Factor(f) = v else { return None };
            p.biomass_multiplier *= f;
            format!("biomass {}", pct_label(f))
        }
        Topic::Yield => {
            p.yield_saf = match v {
                Val::Factor(f) => p.yield_saf * f,
                Val::Set(x) => {
                    if x > 1.0 {
                        x / 100.0
                    } else {
                        x
                    }
                }
            };
            format!("yield set to {:.3}", p.yield_saf)
        }
        Topic::RoadFactor => {
            p.road_factor = match v {
                Val::Factor(f) => p.road_factor * f,
                Val::Set(x) => x,
            };
            format!("road factor set to {:.2}", p.road_factor)
        }
        Topic::FixedOpex => {
            p.fixed_opex_frac = match v {
                Val::Factor(f) => p.fixed_opex_frac * f,
                Val::Set(x) => {
                    if x >= 1.0 {
                        x / 100.0
                    } else {
                        x
                    }
                }
            };
            format!("fixed OpEx set to {:.1}% of CapEx", 100.0 * p.fixed_opex_frac)
        }
        Topic::CapexYears => {
            p.capex_years = match v {
                Val::Factor(f) => p.capex_years * f,
                Val::Set(x) => x,
            };
            format!("CapEx life set to {:.0} years", p.capex_years)
        }
        Topic::MaxRefineries => {
            let Val::Set(x) = v else { return None };
            p.max_refineries = x as usize;
            format!("at most {} refineries", p.max_refineries)
        }
        Topic::RefineryCapex => pair(&mut p.refinery_capex, "refinery CapEx", v),
        Topic::DepotCapex => pair(&mut p.depot_capex, "depot CapEx", v),
        Topic::RefineryCap => pair(&mut p.refinery_cap, "refinery capacity", v),
        Topic::DepotCap => pair(&mut p.depot_cap, "depot capacity", v),
        Topic::RefineryVar => pair(&mut p.refinery_var, "refinery variable OpEx", v),
        Topic::DepotVar => pair(&mut p.depot_var, "depot variable OpEx", v),
        Topic::VarOpex => {
            let Val::Factor(f) = v else { return None };
            p.refinery_var = p.refinery_var.map(|x| x * f);
            p.depot_var = p.depot_var.map(|x| x * f);
            format!("variable OpEx {}", pct_label(f))
        }
        Topic::Capex => {
            let Val::Factor(f) = v else { return None };
            p.refinery_capex = p.refinery_capex.map(|x| x * f);
            p.depot_capex = p.depot_capex.map(|x| x * f);
            format!("all CapEx {}", pct_label(f))
        }
        Topic::Refinery | Topic::Depot => return None,
    };
    Some(text)
}

/// Rejects inputs that would make the model meaningless before any solve starts.
fn in_range(p: &Params) -> Result<(), String> {
    let positive = p.demand.iter().all(|d| *d >= 0.0) && p.total_demand() > 0.0;
    if !positive {
        return Err("demand must stay above zero".into());
    }
    if !(p.yield_saf > 0.0 && p.yield_saf <= 1.0) {
        return Err("yield must be between 0 and 1".into());
    }
    if p.road_factor < 1.0 {
        return Err("road factor cannot be below 1, since roads are never shorter than a straight line".into());
    }
    if p.biomass_multiplier <= 0.0 || [p.tariff_fd, p.tariff_dr, p.tariff_ra].iter().any(|t| *t < 0.0) {
        return Err("biomass must stay positive and tariffs cannot be negative".into());
    }
    if p.refinery_cap.iter().chain(&p.depot_cap).any(|c| *c <= 0.0) || p.refinery_capex.iter().chain(&p.depot_capex).any(|c| *c < 0.0) {
        return Err("capacities must stay positive and CapEx cannot be negative".into());
    }
    if p.capex_years < 1.0 || !(0.0..1.0).contains(&p.fixed_opex_frac) {
        return Err("CapEx life must be at least 1 year and fixed OpEx below 100%".into());
    }
    Ok(())
}

pub struct Parsed {
    pub params: Params,
    pub applied: Vec<String>,
    pub unmapped: Vec<String>,
    pub invalid: Option<String>,
}

/// Reads a what-if sentence clause by clause. Each clause keeps its own sign and amount.
pub fn parse_changes(q: &str, p: &Params) -> Parsed {
    let mut text = format!(" {} ", q.to_lowercase().replace("what-if", "what if").replace("per cent", "percent"));
    for lead in ["what happens if", "what would happen if", "what if", "suppose that", "suppose", "rerun with", "rerun"] {
        text = text.replace(lead, " ");
    }
    for sep in [" while ", " and ", " but ", " plus ", " also ", " as well as ", " with ", " at the same time ", ",", ";", "?", "!"] {
        text = text.replace(sep, "|");
    }
    let mut out = Parsed { params: p.clone(), applied: vec![], unmapped: vec![], invalid: None };
    let mut pending: Vec<(Topic, String)> = vec![];
    for raw in text.split('|') {
        let c = raw.trim().trim_end_matches('.').trim();
        if c.is_empty() {
            continue;
        }
        let t = topic_of(c);
        let v = value_of(c, t);
        match (t, v) {
            (None, None) => {
                if number(c).is_some() || direction(c) != 0 {
                    out.unmapped.push(c.to_string());
                }
            }
            (Some(t), None) => pending.push((t, c.to_string())),
            (t, Some(v)) => {
                if let Some(t) = t {
                    pending.push((t, c.to_string()));
                }
                if pending.is_empty() {
                    out.unmapped.push(c.to_string());
                    continue;
                }
                // "Refinery and depot CapEx up 10%" shares the amount and the attribute.
                let attr = pending.last().map(|x| x.0);
                for (pt, pc) in pending.drain(..) {
                    let pt = match (pt, attr) {
                        (Topic::Refinery, Some(Topic::DepotCapex)) => Topic::RefineryCapex,
                        (Topic::Depot, Some(Topic::RefineryCapex)) => Topic::DepotCapex,
                        (Topic::Refinery, Some(Topic::DepotCap)) => Topic::RefineryCap,
                        (Topic::Depot, Some(Topic::RefineryCap)) => Topic::DepotCap,
                        (x, _) => x,
                    };
                    match apply(&mut out.params, pt, v, &pc) {
                        Some(s) => out.applied.push(s),
                        None => out.unmapped.push(pc),
                    }
                }
            }
        }
    }
    out.unmapped.extend(pending.into_iter().map(|x| x.1));
    if !out.applied.is_empty() {
        out.invalid = in_range(&out.params).err();
    }
    out
}

/// Turns a what-if sentence into new inputs, only if all of it was understood.
pub fn parse_change(q: &str, p: &Params) -> Option<(Params, String)> {
    let r = parse_changes(q, p);
    if r.applied.is_empty() || !r.unmapped.is_empty() || r.invalid.is_some() {
        return None;
    }
    Some((r.params, r.applied.join("; ")))
}

fn what_if(q: &str, s: &Solution, p: &Params) -> Answer {
    let r = parse_changes(q, p);
    let refuse = |text: String| Answer { intent: "what_if".into(), text, sources: vec![], declined: true };
    if let Some(why) = &r.invalid {
        return refuse(format!("I did not run the solver, because {why}. Requested: {}.", r.applied.join("; ")));
    }
    if !r.unmapped.is_empty() {
        let got = if r.applied.is_empty() { String::new() } else { format!(" I understood: {}.", r.applied.join("; ")) };
        return refuse(format!(
            "I did not run the solver, because I could not map this part to an input with a clear direction and amount: \"{}\".{got} Try: demand up 10%, transport down 5%, refinery CapEx up 15%, biomass down 10%, yield 0.25, road factor 1.9.",
            r.unmapped.join("\", \"")
        ));
    }
    if r.applied.is_empty() {
        return refuse("I could not map that to a solver input. Try: demand up 10%, transport down 5%, refinery CapEx up 15%, biomass down 10%, yield 0.25, road factor 1.9.".into());
    }
    let desc = r.applied.join("; ");
    let t = run(&Params { time_limit_s: 6.0, ..r.params.clone() });
    if !t.has_network() {
        let rows: Vec<String> = t.diagnostics.iter().map(|f| format!("- **{}**: {} Fix: {}", f.limit, f.reason, f.fix)).collect();
        return say("what_if", format!("Changes applied: {desc}. The solver reports **infeasible**.\n\n{}", rows.join("\n")), &["solver rerun", "diagnostics"]);
    }
    let (o0, o1) = (s.objective.unwrap_or(0.0), t.objective.unwrap_or(0.0));
    say(
        "what_if",
        format!(
            "Changes applied: {desc}. The solver reran with these inputs.\n\n- Total cost: USD {o0:.1}M to USD {o1:.1}M per year ({:+.1}%)\n- Unit cost: USD {:.0}/t to USD {:.0}/t SAF\n- Refineries: {} to {}\n- Depots: {} to {}\n- Biomass used: {:.0} kt to {:.0} kt\n\n{}",
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
            "Counterfactual solve, limited to 5 s: closing its 3 nearest candidates ({}) gives USD {o:.1}M per year on candidate sites, a change of USD {:+.1}M per year against USD {base:.1}M.",
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
            "\n\nDepots sit at refineries because the second leg costs USD {:.2}/t/km against USD {:.2}/t/km for the first, and depots lose no mass under the official inputs. On the official six-plant fleet, HiGHS found no cheaper depot layout with depots free to go anywhere. Below a retention of {:.3} this reverses, so real wet feedstock could change the answer.",
            p.tariff_dr, p.tariff_fd, p.tariff_fd / p.tariff_dr
        ));
    }
    say("depots", t, &["kpis", "params.depot_capex", "params.depot_var"])
}

fn capacity(q: &str, s: &Solution) -> Answer {
    let th = number(q).filter(|_| q.contains('%')).map_or(0.90, |n| n.0 / 100.0);
    let mut hits: Vec<(String, f64)> = s.refineries.iter().filter(|r| r.utilisation >= th).map(|r| (format!("refinery {} ({})", r.id, r.size), r.utilisation)).collect();
    hits.extend(s.depots.iter().filter(|d| d.utilisation >= th).map(|d| (format!("depot group {} ({} x{})", d.id, d.size, d.count), d.utilisation)));
    hits.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    if hits.is_empty() {
        return say("capacity", format!("No facility is at or above {:.0}% utilisation.", 100.0 * th), &["refineries.utilisation", "depots.utilisation"]);
    }
    let rows: Vec<String> = hits.iter().take(12).map(|(n, u)| format!("- {n}: {:.1}%", 100.0 * u)).collect();
    say("capacity", format!("{} facilities are at or above {:.0}%:\n\n{}", hits.len(), 100.0 * th, rows.join("\n")), &["refineries.utilisation", "depots.utilisation"])
}

fn unused(s: &Solution) -> Answer {
    let k = &s.kpis;
    let spare = k.biomass_available_kt - k.biomass_used_kt;
    if k.sites_skipped.is_empty() {
        return say("unused", format!("Every site ships biomass. {:.0} kt of supply is left over across them.", spare), &["kpis.sites_skipped"]);
    }
    say(
        "unused",
        format!(
            "{} sites ship nothing: {}. Demand needs {:.0} kt of the {:.0} kt available, so the solver leaves the {:.0} kt that costs most to bring in.",
            k.sites_skipped.len(), k.sites_skipped.join(", "), k.biomass_used_kt, k.biomass_available_kt, spare
        ),
        &["kpis.sites_skipped", "kpis.biomass_used_kt"],
    )
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
    if let Some(k) = baseline::kmeans(p, 30) {
        rows.push(format!("- K-means sites with exact flows, a stronger benchmark: best USD {:.1}M, median USD {:.1}M per year. The optimised network saves USD {:.1}M to {:.1}M per year.", k.best, k.median, k.best - o, k.median - o));
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
const CHANGE_WORDS: [&str; 8] = ["demand", "transport", "biomass", "tariff", "feedstock", "capex", "cost up", "cost down"];

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
    if has(&["what happens", "what if", "what-if", "what would happen", "suppose", "rerun"]) || q.starts_with("if ") || (q.contains('%') && has(&CHANGE_WORDS)) {
        return if net { what_if(&q, s, &p) } else { say("what_if", "This scenario has no network to compare with. Switch to a feasible scenario first.".into(), &[]) };
    }
    if !net {
        return infeasible(s, &p);
    }
    if has(&["unused", "skipped", "skip", "not used", "left out", "ship nothing"]) {
        return unused(s);
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
        text: "That question is outside what I can trace to solver output. I can explain refinery choices, route costs, depot sizes, unused sites, capacity use, infeasibility, baseline savings and what-if changes.".into(),
        sources: vec![],
    }
}
