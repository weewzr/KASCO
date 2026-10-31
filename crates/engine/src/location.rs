//! Continuous refinement of refinery coordinates, since sites may be anywhere on land.
//!
//! Alternates two exact steps. With flows fixed, each refinery moves to its weighted
//! geometric median by Weiszfeld iteration. With locations fixed, min-cost flow
//! re-routes all material. This is Cooper's location-allocation method. It converges to
//! a local optimum, so it carries no global proof.
use crate::data::{haversine, on_land};
use crate::problem::*;

/// Starts from the weighted centroid, as an iteration begun on a data point stays there.
fn weiszfeld(pts: &[(f64, f64, f64)]) -> (f64, f64) {
    let total: f64 = pts.iter().map(|p| p.2).sum();
    let mut la = pts.iter().map(|p| p.0 * p.2).sum::<f64>() / total;
    let mut lo = pts.iter().map(|p| p.1 * p.2).sum::<f64>() / total;
    for _ in 0..300 {
        let (mut sw, mut sla, mut slo) = (0.0, 0.0, 0.0);
        for &(pla, plo, w) in pts {
            let d = haversine(la, lo, pla, plo).max(0.05);
            sw += w / d;
            sla += w * pla / d;
            slo += w * plo / d;
        }
        let (nla, nlo) = (sla / sw, slo / sw);
        let moved = (nla - la).abs() + (nlo - lo).abs();
        la = nla;
        lo = nlo;
        if moved < 1e-6 {
            break;
        }
    }
    (la, lo)
}

pub struct Refined {
    pub open: Vec<(usize, usize)>,
    pub alloc: Alloc,
    pub cost: f64,
    pub rounds: usize,
}

/// Each open refinery gets its own movable candidate, which keeps the instance intact.
pub fn refine(inst: &mut Instance, open: &[(usize, usize)], alloc: &Alloc) -> Refined {
    let net = crate::data::network();
    let mut design = vec![];
    for (o, &(k, s)) in open.iter().enumerate() {
        let c = inst.cand[k].clone();
        let idx = inst.push_cand(Cand { id: format!("R{}", o + 1), lat: c.lat, lon: c.lon });
        design.push((idx, s));
    }
    let mut a = allocate(inst, &design).unwrap_or_else(|| alloc.clone());
    let mut cost = total_cost(inst, &design, &a);
    let mut rounds = 0;
    for round in 0..40 {
        rounds = round + 1;
        let before: Vec<(f64, f64)> = design.iter().map(|&(k, _)| (inst.cand[k].lat, inst.cand[k].lon)).collect();
        for (o, &(k, _)) in design.iter().enumerate() {
            let mut pts: Vec<(f64, f64, f64)> = vec![];
            for &(i, oo, q) in &a.x {
                if oo == o {
                    pts.push((net.sites[i].lat, net.sites[i].lon, inst.p.tariff_fd * q));
                }
            }
            for &(oo, ap, q) in &a.w {
                if oo == o {
                    let port = &net.airports[ap];
                    pts.push((port.lat, port.lon, inst.p.tariff_ra * q * inst.p.yield_saf * inst.p.retention));
                }
            }
            if pts.is_empty() {
                continue;
            }
            let cur = before[o];
            let mut target = weiszfeld(&pts);
            // Keep the plant on land by backing off toward the current point.
            let mut t = 1.0;
            while !on_land(target.0, target.1) && t > 0.01 {
                t *= 0.8;
                target = (cur.0 + t * (target.0 - cur.0), cur.1 + t * (target.1 - cur.1));
            }
            if on_land(target.0, target.1) {
                inst.move_cand(k, target.0, target.1);
            }
        }
        let Some(next) = allocate(inst, &design) else { break };
        let c = total_cost(inst, &design, &next);
        if c < cost - 1e-6 {
            let gain = cost - c;
            cost = c;
            a = next;
            if gain < cost * 1e-6 {
                break;
            }
        } else {
            for (o, &(k, _)) in design.iter().enumerate() {
                inst.move_cand(k, before[o].0, before[o].1);
            }
            break;
        }
    }
    Refined { open: design, alloc: a, cost, rounds }
}
