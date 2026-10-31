//! Kalimantan SAF Optimiser engine.
pub mod baseline;
pub mod clock;
pub mod data;
pub mod diag;
pub mod explain;
pub mod field;
pub mod flow;
pub mod location;
pub mod params;
pub mod problem;
pub mod scenarios;
pub mod solution;
pub mod solver;
pub mod validate;

use clock::now_s;
use params::*;
use problem::*;
use solution::*;

/// Design records for co-located depots, where each refinery hosts its own depots.
fn colocated_design(inst: &Instance, open: &[(usize, usize)], a: &Alloc) -> Design {
    let p = &inst.p;
    let mut d = Design::default();
    for (o, &(k, s)) in open.iter().enumerate() {
        let c = &inst.cand[k];
        d.refs.push((c.id.clone(), c.lat, c.lon, s));
        let mix = depot_mix(a.q[o], p);
        d.deps.push((c.id.clone(), c.lat, c.lon, mix.n, mix.through, true));
        if a.q[o] > 1e-9 {
            d.fr.push((c.id.clone(), c.id.clone(), a.q[o] * p.retention, 0.0));
        }
    }
    for &(i, o, q) in &a.x {
        let k = open[o].0;
        d.ff.push((i, inst.cand[k].id.clone(), q, inst.d_fc[i][k]));
    }
    for &(o, ap, q) in &a.w {
        let k = open[o].0;
        d.fa.push((inst.cand[k].id.clone(), ap, q * p.retention * p.yield_saf, inst.d_ca[k][ap]));
    }
    d
}

fn infeasible(p: &Params, findings: Vec<Finding>, t0: f64) -> Solution {
    Solution {
        params: Some(p.clone()),
        status: "infeasible".into(),
        message: if findings.is_empty() { "No design meets demand on the candidate sites.".into() } else { findings[0].reason.clone() },
        diagnostics: findings,
        runtime_s: now_s() - t0,
        colocation_dominant: p.colocation_dominant(),
        ..Default::default()
    }
}

/// Solves one scenario end to end and audits the result.
pub fn run(p: &Params) -> Solution {
    let t0 = now_s();
    let findings = diag::diagnose(p);
    if !findings.is_empty() {
        return infeasible(p, findings, t0);
    }
    let mut inst = Instance::new(p);
    let Some(o) = solver::optimise(&inst) else {
        return infeasible(p, vec![], t0);
    };
    let gap = ((o.ub - o.lb) / o.ub).max(0.0);
    let field = p.depot_mode == "field" || !p.colocation_dominant();
    let mut sol = if field {
        let Some(d) = field::build(&inst, &o.open) else {
            return infeasible(p, vec![], t0);
        };
        let mut s = assemble(p, &d);
        s.status = "heuristic".into();
        s.message = "Refinery sites from the exact search. Depot sites from a greedy cover, flows from exact min-cost flow. No optimality proof for this design.".into();
        s
    } else if p.refine && p.distance_basis == "great_circle" {
        let r = location::refine(&mut inst, &o.open, &o.alloc);
        let mut s = assemble(p, &colocated_design(&inst, &r.open, &r.alloc));
        s.refine_saving = Some(o.ub - r.cost);
        s.status = if gap <= p.gap_target + 1e-9 || o.complete { "optimal".into() } else { "feasible_gap".into() };
        s.message = format!("Candidate-site search closed to a {:.2}% gap. Continuous refinement then moved plants off candidate sites, which is a local optimum.", 100.0 * gap);
        s
    } else {
        let mut s = assemble(p, &colocated_design(&inst, &o.open, &o.alloc));
        s.status = if gap <= p.gap_target + 1e-9 || o.complete { "optimal".into() } else { "feasible_gap".into() };
        s.message = format!("Candidate-site search closed to a {:.2}% gap.", 100.0 * gap);
        s
    };
    sol.discrete_objective = Some(o.ub);
    if !field || p.colocation_dominant() {
        sol.bound = Some(o.lb);
    }
    sol.gap = Some(gap);
    sol.nodes = o.nodes;
    sol.iterations = o.iters;
    sol.validation = validate::check(&sol, p);
    sol.runtime_s = now_s() - t0;
    sol
}
