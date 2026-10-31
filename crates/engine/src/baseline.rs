//! Reference networks a planner could draw without an optimiser.
//!
//! Both use the same demand, distances and cost basis as the optimiser, so the saving
//! reported is like for like.
use crate::data::network;
use crate::params::*;
use crate::problem::*;
use crate::solution::*;
use crate::solver::min_fleet;

/// Opens a depot on each seed in turn and pulls in its nearest unserved sites.
fn clusters(inst: &Instance, order: &[usize]) -> (Vec<(usize, usize)>, Vec<(usize, usize, f64)>) {
    let net = network();
    let p = &inst.p;
    let dist = Dist::new(p, net);
    let km = |a: usize, b: usize| {
        let (x, y) = (&net.sites[a], &net.sites[b]);
        dist.km(net, (&x.id, x.lat, x.lon), (&y.id, y.lat, y.lon))
    };
    let mut left = inst.farm_kt.clone();
    let (mut deps, mut flows) = (vec![], vec![]);
    let mut got_all = 0.0;
    for &seed in order {
        if got_all >= inst.need - 1e-9 {
            break;
        }
        if left[seed] <= 1e-9 {
            continue;
        }
        let room = p.depot_cap[LARGE].min(inst.need - got_all);
        let size = if room <= p.depot_cap[SMALL] { SMALL } else { LARGE };
        let mut near: Vec<usize> = (0..left.len()).collect();
        near.sort_by(|&x, &y| km(seed, x).partial_cmp(&km(seed, y)).unwrap());
        let mut got = 0.0;
        for i in near {
            if got >= room - 1e-9 {
                break;
            }
            let q = left[i].min(room - got);
            if q > 1e-9 {
                flows.push((i, deps.len(), q));
                left[i] -= q;
                got += q;
            }
        }
        deps.push((seed, size));
        got_all += got;
    }
    (deps, flows)
}

/// Sends each depot to its nearest refinery with room, then fills airports nearest first.
fn serve(inst: &Instance, deps: &[(usize, usize)], flows: &[(usize, usize, f64)], refs: &[(usize, usize)]) -> Option<Design> {
    let net = network();
    let p = &inst.p;
    let dist = Dist::new(p, net);
    let mut d = Design::default();
    let mut q = vec![0.0; deps.len()];
    for &(i, j, f) in flows {
        q[j] += f;
        let site = &net.sites[deps[j].0];
        let s = &net.sites[i];
        d.ff.push((i, site.id.clone(), f, dist.km(net, (&s.id, s.lat, s.lon), (&site.id, site.lat, site.lon))));
    }
    for (j, &(site, size)) in deps.iter().enumerate() {
        let s = &net.sites[site];
        let mut n = [0, 0];
        let mut thr = [0.0, 0.0];
        n[size] = 1;
        thr[size] = q[j];
        d.deps.push((s.id.clone(), s.lat, s.lon, n, thr, false));
    }
    let mut room: Vec<f64> = refs.iter().map(|&(_, s)| p.refinery_cap[s]).collect();
    let mut order: Vec<usize> = (0..deps.len()).collect();
    order.sort_by(|&x, &y| q[y].partial_cmp(&q[x]).unwrap());
    let mut made = vec![0.0; refs.len()];
    for j in order {
        let s = &net.sites[deps[j].0];
        let mut gate = q[j] * p.retention;
        let mut opts: Vec<(f64, usize)> = refs
            .iter()
            .enumerate()
            .map(|(o, &(k, _))| {
                let c = &inst.cand[k];
                (dist.km(net, (&s.id, s.lat, s.lon), (&c.id, c.lat, c.lon)), o)
            })
            .collect();
        opts.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
        for (km, o) in opts {
            let take = gate.min(room[o]);
            if take > 1e-9 {
                d.fr.push((s.id.clone(), inst.cand[refs[o].0].id.clone(), take, km));
                room[o] -= take;
                gate -= take;
                made[o] += take * p.yield_saf;
            }
        }
        if gate > 1e-6 {
            return None;
        }
    }
    for &(k, s) in refs {
        let c = &inst.cand[k];
        d.refs.push((c.id.clone(), c.lat, c.lon, s));
    }
    let mut want: [f64; 4] = std::array::from_fn(|a| p.demand[a] * p.demand_multiplier);
    let mut pairs: Vec<(f64, usize, usize)> = vec![];
    for (o, &(k, _)) in refs.iter().enumerate() {
        for a in 0..4 {
            pairs.push((inst.d_ca[k][a], o, a));
        }
    }
    pairs.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    for (km, o, a) in pairs {
        let q = made[o].min(want[a]);
        if q > 1e-9 {
            d.fa.push((inst.cand[refs[o].0].id.clone(), a, q, km));
            made[o] -= q;
            want[a] -= q;
        }
    }
    Some(d)
}

fn fleet_sizes(inst: &Instance) -> Option<Vec<usize>> {
    let (l, s) = min_fleet(inst)?;
    let mut v = vec![LARGE; l];
    v.extend(vec![SMALL; s]);
    Some(v)
}

fn richest(inst: &Instance) -> Vec<usize> {
    let mut o: Vec<usize> = (0..inst.farm_kt.len()).collect();
    o.sort_by(|&x, &y| inst.farm_kt[y].partial_cmp(&inst.farm_kt[x]).unwrap());
    o
}

/// Depots on the richest sites, refineries spread farthest-first across them.
pub fn greedy(p: &Params) -> Option<Solution> {
    let inst = Instance::new(p);
    let (deps, flows) = clusters(&inst, &richest(&inst));
    let fleet = fleet_sizes(&inst)?;
    let cand_of = |site: usize| inst.cand.iter().position(|c| c.id == network().sites[site].id);
    let mut chosen = vec![cand_of(deps[0].0)?];
    while chosen.len() < fleet.len() && chosen.len() < deps.len() {
        let mut best = (-1.0, None);
        for &(site, _) in &deps {
            let Some(k) = cand_of(site) else { continue };
            if chosen.contains(&k) {
                continue;
            }
            let (la, lo) = (inst.cand[k].lat, inst.cand[k].lon);
            let d = chosen.iter().map(|&r| crate::data::haversine(la, lo, inst.cand[r].lat, inst.cand[r].lon)).fold(f64::INFINITY, f64::min);
            if d > best.0 {
                best = (d, Some(k));
            }
        }
        chosen.push(best.1?);
    }
    let refs: Vec<(usize, usize)> = chosen.into_iter().zip(fleet).collect();
    let d = serve(&inst, &deps, &flows, &refs)?;
    let mut s = assemble(p, &d);
    s.status = "heuristic".into();
    s.message = "Greedy: depots on the richest sites, refineries farthest-first.".into();
    s.validation = crate::validate::check(&s, p);
    Some(s)
}

pub struct KmeansStats {
    pub restarts: usize,
    pub best: f64,
    pub median: f64,
    pub worst: f64,
    pub best_valid: bool,
    pub best_refineries: usize,
    pub best_depots: usize,
}

/// A deliberately strong benchmark: biomass-weighted k-means sites, snapped to candidates,
/// with the same exact flows and refinement as the optimiser. It uses the optimiser's fleet
/// size, so it shows the value of the site search alone.
pub fn kmeans(p: &Params, restarts: usize) -> Option<KmeansStats> {
    let net = network();
    let base = Instance::new(p);
    let fleet = fleet_sizes(&base)?;
    let k = fleet.len();
    let n = net.sites.len();
    let (mut seed, mut costs) = (12345u64, vec![]);
    let mut best: Option<(f64, Solution)> = None;
    for _ in 0..restarts {
        let mut pick = || {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (seed >> 33) as usize % n
        };
        let mut c: Vec<(f64, f64)> = (0..k).map(|_| { let s = &net.sites[pick()]; (s.lat, s.lon) }).collect();
        for _ in 0..60 {
            let mut sum = vec![(0.0, 0.0, 0.0); k];
            for s in &net.sites {
                let d = |j: usize| crate::data::haversine(s.lat, s.lon, c[j].0, c[j].1);
                let j = (0..k).min_by(|&a, &b| d(a).partial_cmp(&d(b)).unwrap()).unwrap();
                sum[j].0 += s.kt * s.lat;
                sum[j].1 += s.kt * s.lon;
                sum[j].2 += s.kt;
            }
            for j in 0..k {
                if sum[j].2 > 0.0 {
                    c[j] = (sum[j].0 / sum[j].2, sum[j].1 / sum[j].2);
                }
            }
        }
        let mut inst = Instance::new(p);
        let mut open: Vec<(usize, usize)> = vec![];
        for j in 0..k {
            let d = |a: usize| crate::data::haversine(c[j].0, c[j].1, inst.cand[a].lat, inst.cand[a].lon);
            let site = (0..inst.cand.len()).filter(|x| !open.iter().any(|o| o.0 == *x)).min_by(|&a, &b| d(a).partial_cmp(&d(b)).unwrap())?;
            open.push((site, fleet[j]));
        }
        let Some(a) = allocate(&inst, &open) else { continue };
        let r = crate::location::refine(&mut inst, &open, &a);
        costs.push(r.cost);
        if best.as_ref().map_or(true, |b| r.cost < b.0) {
            best = Some((r.cost, assemble(p, &crate::colocated_design(&inst, &r.open, &r.alloc))));
        }
    }
    costs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let (_, sol) = best?;
    Some(KmeansStats {
        restarts: costs.len(),
        best: costs[0],
        median: costs[costs.len() / 2],
        worst: costs[costs.len() - 1],
        best_valid: crate::validate::all_passed(&crate::validate::check(&sol, p)),
        best_refineries: sol.kpis.n_refineries,
        best_depots: sol.kpis.n_depots,
    })
}

/// Refineries at the airports first, the default a fuel planner might reach for.
pub fn airport_first(p: &Params) -> Option<Solution> {
    let inst = Instance::new(p);
    let net = network();
    let fleet = fleet_sizes(&inst)?;
    let mut chosen: Vec<usize> = inst.cand.iter().enumerate().filter(|(_, c)| AIRPORTS.contains(&c.id.as_str())).map(|t| t.0).collect();
    chosen.truncate(fleet.len());
    for site in richest(&inst) {
        if chosen.len() >= fleet.len() {
            break;
        }
        if let Some(k) = inst.cand.iter().position(|c| c.id == net.sites[site].id) {
            chosen.push(k);
        }
    }
    let mut seeds: Vec<usize> = (0..inst.farm_kt.len()).collect();
    let near = |i: usize| chosen.iter().map(|&k| inst.d_fc[i][k]).fold(f64::INFINITY, f64::min);
    seeds.sort_by(|&x, &y| near(x).partial_cmp(&near(y)).unwrap());
    let (deps, flows) = clusters(&inst, &seeds);
    let refs: Vec<(usize, usize)> = chosen.iter().copied().zip(fleet).collect();
    let d = serve(&inst, &deps, &flows, &refs)?;
    let mut s = assemble(p, &d);
    s.status = "heuristic".into();
    s.message = "Airport-first: refineries at PNK, PKN and BPN, then the richest sites.".into();
    s.validation = crate::validate::check(&s, p);
    Some(s)
}
