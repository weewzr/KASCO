//! Exact search over refinery sites.
//!
//! The candidate-site problem is a capacitated facility location model. We relax the
//! farm supply and airport demand constraints with multipliers, which splits the model
//! into one small subproblem per site. Each subproblem is solved greedily and exactly.
//! Subgradient steps tighten the resulting lower bound, branch-and-bound closes the
//! gap, and min-cost flow prices each candidate design exactly.
use crate::clock::now_s;
use crate::params::*;
use crate::problem::*;
use std::collections::HashSet;

const INF: f64 = 1e18;

#[derive(Clone)]
struct Mult {
    u: Vec<f64>,
    lam: [f64; 4],
}

struct Eval {
    lb: f64,
    chosen: Vec<(usize, usize)>,
    gu: Vec<f64>,
    gl: [f64; 4],
    v: Vec<[f64; 2]>,
}

#[derive(Clone)]
struct Node {
    forced: Vec<usize>,
    banned: Vec<usize>,
    mult: Mult,
    lb: f64,
}

pub struct Outcome {
    pub open: Vec<(usize, usize)>,
    pub alloc: Alloc,
    pub ub: f64,
    pub lb: f64,
    pub nodes: usize,
    pub iters: usize,
    pub complete: bool,
}

/// Best value of one site's subproblem: buy the cheapest inputs, sell the dearest outputs.
#[inline]
fn pick(inp: &[(f64, usize)], out: &[(f64, usize); 4], inst: &Instance, s: usize, mut rec: Option<(&mut [f64], &mut [f64; 4])>) -> f64 {
    let (mut i, mut a) = (0, 0);
    let (mut left_i, mut left_a) = (if inp.is_empty() { 0.0 } else { inst.farm_kt[inp[0].1] }, inst.e[out[0].1]);
    let (mut q, mut val) = (0.0, 0.0);
    let cap = inst.cap_raw[s];
    let var = inst.var_raw[s];
    while q < cap && i < inp.len() && a < 4 {
        let m = inp[i].0 + var + out[a].0;
        if m >= 0.0 {
            break;
        }
        let step = left_i.min(left_a).min(cap - q);
        val += m * step;
        q += step;
        if let Some((gu, gl)) = rec.as_mut() {
            gu[inp[i].1] += step;
            gl[out[a].1] -= step;
        }
        left_i -= step;
        left_a -= step;
        if left_i <= 1e-12 {
            i += 1;
            if i < inp.len() {
                left_i = inst.farm_kt[inp[i].1];
            }
        }
        if left_a <= 1e-12 {
            a += 1;
            if a < 4 {
                left_a = inst.e[out[a].1];
            }
        }
    }
    val
}

fn lr_eval(inst: &Instance, m: &Mult, forced: &[bool], banned: &[bool]) -> Eval {
    let nk = inst.cand.len();
    let nf = inst.farm_kt.len();
    let mut v = vec![[INF; 2]; nk];
    let mut out_all: Vec<[(f64, usize); 4]> = Vec::with_capacity(nk);
    let mut inp_all: Vec<Vec<(f64, usize)>> = Vec::with_capacity(nk);
    for k in 0..nk {
        let mut out = [(0.0, 0); 4];
        for a in 0..4 {
            out[a] = (inst.g(k, a) - m.lam[a], a);
        }
        out.sort_unstable_by(|x, y| x.0.partial_cmp(&y.0).unwrap());
        let mut inp: Vec<(f64, usize)> = Vec::new();
        if !banned[k] {
            let lim = -out[0].0;
            for i in 0..nf {
                let c = inst.c(i, k) + m.u[i] + inst.dep_rate;
                if c < lim {
                    inp.push((c, i));
                }
            }
            inp.sort_unstable_by(|x, y| x.0.partial_cmp(&y.0).unwrap());
            for s in 0..2 {
                v[k][s] = inst.fixed[s] + pick(&inp, &out, inst, s, None);
            }
        }
        out_all.push(out);
        inp_all.push(inp);
    }

    let mut base = 0.0;
    let mut f = 0usize;
    let mut chosen = vec![];
    for k in 0..nk {
        if forced[k] {
            let s = if v[k][LARGE] <= v[k][SMALL] { LARGE } else { SMALL };
            base += v[k][s];
            chosen.push((k, s));
            f += 1;
        }
    }
    let free: Vec<usize> = (0..nk).filter(|&k| !forced[k] && !banned[k]).collect();
    let mut order = [free.clone(), free.clone()];
    for s in 0..2 {
        order[s].sort_unstable_by(|&x, &y| v[x][s].partial_cmp(&v[y][s]).unwrap());
    }
    let n_free = free.len();
    let mut pre = [vec![0.0; n_free + 1], vec![0.0; n_free + 1]];
    for s in 0..2 {
        for n in 0..n_free {
            pre[s][n + 1] = pre[s][n] + v[order[s][n]][s];
        }
    }
    let lim = if inst.p.max_refineries > 0 { inst.p.max_refineries } else { usize::MAX };
    let (mut best, mut pick_n) = (INF, None);
    for nl in 0..=n_free {
        for ns in 0..=n_free {
            if f + nl + ns > lim {
                break;
            }
            let cover = (f + nl) as f64 * inst.cap_raw[LARGE] + ns as f64 * inst.cap_raw[SMALL];
            if cover < inst.need - 1e-9 {
                continue;
            }
            let c = pre[LARGE][nl] + pre[SMALL][ns];
            if c < best {
                best = c;
                pick_n = Some((nl, ns));
            }
        }
    }
    let Some((nl, ns)) = pick_n else {
        return Eval { lb: INF, chosen, gu: vec![0.0; nf], gl: [0.0; 4], v };
    };
    for n in 0..nl {
        chosen.push((order[LARGE][n], LARGE));
    }
    for n in 0..ns {
        chosen.push((order[SMALL][n], SMALL));
    }
    let mut lb = base + best;
    for i in 0..nf {
        lb -= m.u[i] * inst.farm_kt[i];
    }
    for a in 0..4 {
        lb += m.lam[a] * inst.e[a];
    }
    let mut gu: Vec<f64> = inst.farm_kt.iter().map(|b| -b).collect();
    let mut gl = inst.e;
    for &(k, s) in &chosen {
        pick(&inp_all[k], &out_all[k], inst, s, Some((&mut gu, &mut gl)));
    }
    Eval { lb, chosen, gu, gl, v }
}

fn try_design(inst: &Instance, open: &[(usize, usize)]) -> Option<(f64, Alloc)> {
    let cover: f64 = open.iter().map(|&(_, s)| inst.cap_raw[s]).sum();
    if cover < inst.need - 1e-9 {
        return None;
    }
    if inst.p.max_refineries > 0 && open.len() > inst.p.max_refineries {
        return None;
    }
    let a = allocate(inst, open)?;
    Some((total_cost(inst, open, &a), a))
}

fn normalise(mut open: Vec<(usize, usize)>) -> Vec<(usize, usize)> {
    open.sort_unstable_by_key(|t| (t.0, std::cmp::Reverse(t.1)));
    open.dedup_by_key(|t| t.0);
    open
}

struct Search<'a> {
    inst: &'a Instance,
    near: Vec<Vec<usize>>,
    best: Option<(Vec<(usize, usize)>, Alloc)>,
    ub: f64,
    seen: HashSet<Vec<(usize, usize)>>,
    deadline: f64,
}

impl<'a> Search<'a> {
    fn offer(&mut self, open: Vec<(usize, usize)>) -> bool {
        let open = normalise(open);
        if !self.seen.insert(open.clone()) {
            return false;
        }
        if let Some((c, a)) = try_design(self.inst, &open) {
            if c < self.ub - 1e-9 {
                self.ub = c;
                self.best = Some((open, a));
                return true;
            }
        }
        false
    }

    /// Site swaps, size flips, adds and drops until no move improves the design.
    fn improve(&mut self) {
        loop {
            let Some((open, _)) = self.best.clone() else { return };
            let start = self.ub;
            let n = open.len();
            'outer: for o in 0..n {
                let (k, s) = open[o];
                for &alt in &self.near[k].clone() {
                    if open.iter().any(|t| t.0 == alt) {
                        continue;
                    }
                    let mut d = open.clone();
                    d[o] = (alt, s);
                    if self.offer(d) {
                        break 'outer;
                    }
                    if now_s() > self.deadline {
                        return;
                    }
                }
                let mut d = open.clone();
                d[o].1 = 1 - s;
                if self.offer(d) {
                    break 'outer;
                }
                let mut d = open.clone();
                d.remove(o);
                if self.offer(d) {
                    break 'outer;
                }
            }
            if self.ub < start - 1e-9 {
                continue;
            }
            // A further small plant can pay for itself on haulage.
            for &k in &self.near[open[0].0].clone() {
                if now_s() > self.deadline {
                    return;
                }
                if open.iter().any(|t| t.0 == k) {
                    continue;
                }
                let mut d = open.clone();
                d.push((k, SMALL));
                self.offer(d);
            }
            if self.ub >= start - 1e-9 {
                return;
            }
        }
    }

    /// Lloyd clustering on the biomass, snapped to candidates, for a starting design.
    fn seed(&mut self, n: usize, size: &dyn Fn(usize) -> usize) {
        let inst = self.inst;
        let nk = inst.cand.len();
        let mut centres: Vec<usize> = vec![];
        let mut best_d: Vec<f64> = vec![f64::INFINITY; inst.farm_kt.len()];
        for _ in 0..n {
            let mut pick = 0;
            let mut top = -1.0;
            for k in 0..nk {
                let gain: f64 = (0..inst.farm_kt.len()).map(|i| inst.farm_kt[i] * (best_d[i].min(2000.0) - inst.d_fc[i][k]).max(0.0)).sum();
                if gain > top && !centres.contains(&k) {
                    top = gain;
                    pick = k;
                }
            }
            centres.push(pick);
            for i in 0..inst.farm_kt.len() {
                best_d[i] = best_d[i].min(inst.d_fc[i][pick]);
            }
        }
        let d = centres.iter().enumerate().map(|(j, &k)| (k, size(j))).collect();
        self.offer(d);
    }
}

/// Cheapest refinery fleet that covers the need, as (large, small) counts.
pub fn min_fleet(inst: &Instance) -> Option<(usize, usize)> {
    let top = (inst.need / inst.cap_raw[SMALL]).ceil() as usize + 2;
    let mut best: Option<(f64, usize, usize)> = None;
    for nl in 0..=top {
        for ns in 0..=top {
            if nl + ns == 0 || (inst.p.max_refineries > 0 && nl + ns > inst.p.max_refineries) {
                continue;
            }
            if nl as f64 * inst.cap_raw[LARGE] + ns as f64 * inst.cap_raw[SMALL] >= inst.need - 1e-9 {
                let c = nl as f64 * inst.fixed[LARGE] + ns as f64 * inst.fixed[SMALL];
                if best.map_or(true, |b| c < b.0) {
                    best = Some((c, nl, ns));
                }
            }
        }
    }
    best.map(|b| (b.1, b.2))
}

pub fn optimise(inst: &Instance) -> Option<Outcome> {
    let t0 = now_s();
    let budget = inst.p.time_limit_s;
    let deadline = t0 + budget;
    let (fl, fs) = min_fleet(inst)?;
    let nk = inst.cand.len();
    let near: Vec<Vec<usize>> = (0..nk)
        .map(|k| {
            let (la, lo) = (inst.cand[k].lat, inst.cand[k].lon);
            let mut v: Vec<(f64, usize)> = (0..nk)
                .filter(|&j| j != k)
                .map(|j| (crate::data::haversine(la, lo, inst.cand[j].lat, inst.cand[j].lon), j))
                .collect();
            v.sort_unstable_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
            v.into_iter().take(10).map(|t| t.1).collect()
        })
        .collect();
    let mut sr = Search { inst, near, best: None, ub: INF, seen: HashSet::new(), deadline: t0 + budget * 0.3 };
    let n = fl + fs;
    sr.seed(n, &|j| if j < fl { LARGE } else { SMALL });
    sr.seed(n + 1, &|j| if j < fl { LARGE } else { SMALL });
    sr.improve();
    sr.deadline = deadline;
    if sr.best.is_none() {
        // Fall back on every biomass site's nearest designs through the bound below.
        sr.ub = INF;
    }

    let eps = inst.p.gap_target;
    let start_lam = inst.fixed[LARGE] / inst.cap_raw[LARGE] + inst.var_raw[LARGE] + inst.dep_rate + 0.01;
    let root = Node {
        forced: vec![],
        banned: vec![],
        mult: Mult { u: vec![0.0; inst.farm_kt.len()], lam: [start_lam; 4] },
        lb: -INF,
    };
    let mut stack = vec![root];
    let (mut nodes, mut iters) = (0usize, 0usize);
    let mut min_closed = INF;
    let mut complete = true;

    while let Some(mut node) = stack.pop() {
        if node.lb >= sr.ub * (1.0 - eps) {
            min_closed = min_closed.min(node.lb);
            continue;
        }
        if now_s() > deadline {
            stack.push(node);
            complete = false;
            break;
        }
        nodes += 1;
        let mut forced = vec![false; nk];
        let mut banned = vec![false; nk];
        node.forced.iter().for_each(|&k| forced[k] = true);
        node.banned.iter().for_each(|&k| banned[k] = true);

        let mut m = node.mult.clone();
        let mut best_m = m.clone();
        let (mut theta, mut stall) = (2.0, 0);
        let mut node_lb = node.lb;
        let max_it = if nodes == 1 { 900 } else { 140 };
        let mut last: Option<Eval> = None;
        for it in 0..max_it {
            iters += 1;
            let e = lr_eval(inst, &m, &forced, &banned);
            if e.lb >= INF / 2.0 {
                node_lb = INF;
                break;
            }
            if e.lb > node_lb + 1e-7 {
                node_lb = e.lb;
                best_m = m.clone();
                stall = 0;
            } else {
                stall += 1;
                if stall >= 16 {
                    theta *= 0.6;
                    stall = 0;
                    m = best_m.clone();
                }
            }
            if it % 12 == 0 {
                let improved = sr.offer(e.chosen.clone());
                if improved {
                    sr.improve();
                }
            }
            if node_lb >= sr.ub * (1.0 - eps) || theta < 1e-3 {
                last = Some(e);
                break;
            }
            let norm: f64 = e.gu.iter().map(|g| g * g).sum::<f64>() + e.gl.iter().map(|g| g * g).sum::<f64>();
            if norm < 1e-12 {
                last = Some(e);
                break;
            }
            let ub = if sr.ub < INF / 2.0 { sr.ub } else { e.lb * 1.2 };
            let step = theta * (ub - e.lb).max(1e-6) / norm;
            for i in 0..m.u.len() {
                m.u[i] = (m.u[i] + step * e.gu[i]).max(0.0);
            }
            for a in 0..4 {
                m.lam[a] = (m.lam[a] + step * e.gl[a]).max(0.0);
            }
            last = Some(e);
            if now_s() > deadline {
                break;
            }
        }
        if node_lb >= sr.ub * (1.0 - eps) {
            min_closed = min_closed.min(node_lb);
            continue;
        }
        let e = last.unwrap_or_else(|| lr_eval(inst, &best_m, &forced, &banned));
        // Branch on the most attractive site not yet decided.
        let pick = e.chosen.iter().map(|t| t.0).filter(|&k| !forced[k]).min_by(|&x, &y| {
            let a = e.v[x][LARGE].min(e.v[x][SMALL]);
            let b = e.v[y][LARGE].min(e.v[y][SMALL]);
            a.partial_cmp(&b).unwrap()
        });
        let pick = pick.or_else(|| {
            (0..nk).filter(|&k| !forced[k] && !banned[k]).min_by(|&x, &y| {
                let a = e.v[x][LARGE].min(e.v[x][SMALL]);
                let b = e.v[y][LARGE].min(e.v[y][SMALL]);
                a.partial_cmp(&b).unwrap()
            })
        });
        let Some(k) = pick else {
            min_closed = min_closed.min(node_lb);
            continue;
        };
        let mut off = node.clone();
        off.banned.push(k);
        off.mult = best_m.clone();
        off.lb = node_lb;
        let mut on = node;
        on.forced.push(k);
        on.mult = best_m;
        on.lb = node_lb;
        stack.push(off);
        stack.push(on);
    }

    let (open, alloc) = sr.best.take()?;
    let pending = stack.iter().map(|n| n.lb).fold(INF, f64::min);
    let lb = min_closed.min(pending).min(sr.ub);
    Some(Outcome { open, alloc, ub: sr.ub, lb, nodes, iters, complete })
}
