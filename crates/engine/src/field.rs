//! Field depots: one depot per biomass site, gathering only from nearby sites.
//!
//! This prices the decentralised design a planner may prefer for operational reasons.
//! Depot sites come from a greedy cover and flows from exact min-cost flow, so the
//! result is a feasible design with no optimality proof.
use crate::data::network;
use crate::flow::Mcf;
use crate::params::*;
use crate::problem::*;
use crate::solution::Design;

pub fn build(inst: &Instance, open: &[(usize, usize)]) -> Option<Design> {
    let net = network();
    let p = &inst.p;
    let dist = Dist::new(p, net);
    let nf = net.sites.len();
    let mut radius = if p.colocation_dominant() { p.field_radius_km } else { p.field_radius_km.max(250.0) };
    let km = |a: usize, b: usize| {
        let (x, y) = (&net.sites[a], &net.sites[b]);
        dist.km(net, (&x.id, x.lat, x.lon), (&y.id, y.lat, y.lon))
    };
    let dd: Vec<Vec<f64>> = (0..nf).map(|a| (0..nf).map(|b| if a == b { 0.0 } else { km(a, b) }).collect()).collect();
    let reserved: Vec<bool> = net.sites.iter().map(|s| open.iter().any(|&(k, _)| inst.cand[k].id == s.id)).collect();
    let cap = p.depot_cap[LARGE];

    for _ in 0..6 {
        let mut left = inst.farm_kt.clone();
        let mut sites = vec![];
        let mut covered = 0.0;
        while covered < inst.need * 1.10 {
            let (mut best, mut pick) = (1e-6, None);
            for j in 0..nf {
                if reserved[j] || sites.contains(&j) {
                    continue;
                }
                let mut near: Vec<usize> = (0..nf).filter(|&i| dd[j][i] <= radius && left[i] > 1e-9).collect();
                near.sort_unstable_by(|&x, &y| dd[j][x].partial_cmp(&dd[j][y]).unwrap());
                let mut got = 0.0;
                for i in near {
                    got += left[i].min(cap - got);
                }
                if got > best {
                    best = got;
                    pick = Some(j);
                }
            }
            let Some(j) = pick else { break };
            let mut near: Vec<usize> = (0..nf).filter(|&i| dd[j][i] <= radius && left[i] > 1e-9).collect();
            near.sort_unstable_by(|&x, &y| dd[j][x].partial_cmp(&dd[j][y]).unwrap());
            let mut got = 0.0;
            for i in near {
                let q = left[i].min(cap - got);
                left[i] -= q;
                got += q;
            }
            covered += got;
            sites.push(j);
        }
        if let Some(d) = flows(inst, open, &sites, &dd, radius) {
            return Some(d);
        }
        radius *= 1.4;
    }
    None
}

fn flows(inst: &Instance, open: &[(usize, usize)], sites: &[usize], dd: &[Vec<f64>], radius: f64) -> Option<Design> {
    let net = network();
    let p = &inst.p;
    let (nf, nd, m) = (net.sites.len(), sites.len(), open.len());
    let (din, dout, rin, rout, air) = (2 + nf, 2 + nf + nd, 2 + nf + 2 * nd, 2 + nf + 2 * nd + m, 2 + nf + 2 * nd + 2 * m);
    let mut g = Mcf::new(air + 4);
    for i in 0..nf {
        g.add(0, 2 + i, inst.farm_kt[i], 0.0);
    }
    let (mut ex, mut eu, mut ew) = (vec![], vec![], vec![]);
    let dist = Dist::new(p, net);
    let mut dep_ref = vec![vec![0.0; m]; nd];
    for (d, &j) in sites.iter().enumerate() {
        for i in 0..nf {
            if dd[i][j] <= radius {
                ex.push((i, d, g.add(2 + i, din + d, inst.farm_kt[i], p.tariff_fd * dd[i][j] / 1000.0)));
            }
        }
        g.add(din + d, dout + d, p.depot_cap[LARGE], p.depot_var[LARGE] / 1000.0);
        let s = &net.sites[j];
        for (o, &(k, _)) in open.iter().enumerate() {
            let c = &inst.cand[k];
            let km = dist.km(net, (&s.id, s.lat, s.lon), (&c.id, c.lat, c.lon));
            dep_ref[d][o] = km;
            eu.push((d, o, g.add(dout + d, rin + o, f64::INFINITY, p.tariff_dr * p.retention * km / 1000.0)));
        }
    }
    for (o, &(k, s)) in open.iter().enumerate() {
        g.add(rin + o, rout + o, inst.cap_raw[s], inst.var_raw[s]);
        for a in 0..4 {
            ew.push((o, a, g.add(rout + o, air + a, inst.e[a], inst.g(k, a))));
        }
    }
    for a in 0..4 {
        g.add(air + a, 1, inst.e[a], 0.0);
    }
    let (sent, _) = g.run(0, 1, inst.need);
    if sent < inst.need - 1e-6 {
        return None;
    }
    let mut d = Design::default();
    for &(k, s) in open {
        let c = &inst.cand[k];
        d.refs.push((c.id.clone(), c.lat, c.lon, s));
    }
    let mut q = vec![0.0; nd];
    for &(i, j, e) in &ex {
        let f = g.flow(e);
        if f > 1e-7 {
            q[j] += f;
            let site = &net.sites[sites[j]];
            d.ff.push((i, site.id.clone(), f, dd[i][sites[j]]));
        }
    }
    let f = p.annual_factor();
    for (j, &site) in sites.iter().enumerate() {
        if q[j] <= 1e-7 {
            continue;
        }
        let small_fits = q[j] <= p.depot_cap[SMALL] + 1e-9;
        let cost = |s: usize| f * p.depot_capex[s] + q[j] * p.depot_var[s] / 1000.0;
        let size = if small_fits && cost(SMALL) <= cost(LARGE) { SMALL } else { LARGE };
        let mut n = [0, 0];
        let mut thr = [0.0, 0.0];
        n[size] = 1;
        thr[size] = q[j];
        let s = &net.sites[site];
        d.deps.push((s.id.clone(), s.lat, s.lon, n, thr, false));
    }
    for &(j, o, e) in &eu {
        let fl = g.flow(e);
        if fl > 1e-7 {
            let s = &net.sites[sites[j]];
            d.fr.push((s.id.clone(), inst.cand[open[o].0].id.clone(), fl * p.retention, dep_ref[j][o]));
        }
    }
    for &(o, a, e) in &ew {
        let fl = g.flow(e);
        if fl > 1e-7 {
            let k = open[o].0;
            d.fa.push((inst.cand[k].id.clone(), a, fl * p.retention * p.yield_saf, inst.d_ca[k][a]));
        }
    }
    Some(d)
}
