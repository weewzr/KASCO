//! States why a scenario has no feasible network. Each test is hand-checkable arithmetic.
use crate::data::network;
use crate::params::*;
use crate::solution::Finding;

pub fn diagnose(p: &Params) -> Vec<Finding> {
    let net = network();
    let demand = p.total_demand();
    let need_raw = p.raw_need();
    let need_gate = need_raw * p.retention;
    let avail = net.sites.iter().map(|s| s.kt).sum::<f64>() * p.biomass_multiplier;
    let mut out = vec![];
    if need_raw > avail + 1e-6 {
        let top = avail * p.retention * p.yield_saf;
        out.push(Finding {
            limit: "Biomass supply".into(),
            available: avail,
            required: need_raw,
            unit: "kt/yr".into(),
            reason: format!(
                "Demand of {demand:.0} kt SAF needs {need_raw:.0} kt biomass at yield {:.2}, but only {avail:.0} kt exists. This feedstock can make at most {top:.0} kt SAF.",
                p.yield_saf
            ),
            fix: format!(
                "Cut demand by {:.1}%, or raise yield to at least {:.3}.",
                100.0 * (1.0 - avail / need_raw),
                demand / (avail * p.retention)
            ),
        });
    }
    if p.max_refineries > 0 {
        let cap = p.max_refineries as f64 * p.refinery_cap[LARGE];
        if need_gate > cap + 1e-6 {
            out.push(Finding {
                limit: "Refinery count".into(),
                available: cap,
                required: need_gate,
                unit: "kt/yr".into(),
                reason: format!("{} large refineries take {cap:.0} kt biomass, but this scenario needs {need_gate:.0} kt.", p.max_refineries),
                fix: format!("Allow at least {} refineries.", (need_gate / p.refinery_cap[LARGE]).ceil() as usize),
            });
        }
    }
    out
}
