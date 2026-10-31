//! Numeric form of one scenario. Masses are raw biomass kt/yr and costs USD M/yr.
use crate::data::{haversine, network, Network};
use crate::flow::Mcf;
use crate::params::*;
use std::collections::HashMap;

#[derive(Clone, Debug)]
pub struct Cand {
    pub id: String,
    pub lat: f64,
    pub lon: f64,
}

pub struct Instance {
    pub p: Params,
    pub farm_kt: Vec<f64>,
    pub cand: Vec<Cand>,
    /// farm by candidate, km.
    pub d_fc: Vec<Vec<f64>>,
    /// candidate by airport, km.
    pub d_ca: Vec<[f64; 4]>,
    /// Raw biomass needed per airport.
    pub e: [f64; 4],
    pub need: f64,
    pub fixed: [f64; 2],
    pub cap_raw: [f64; 2],
    pub var_raw: [f64; 2],
    /// Cheapest possible depot cost per raw kt, a valid lower bound.
    pub dep_rate: f64,
}

pub struct Dist {
    index: HashMap<String, usize>,
    road: bool,
    factor: f64,
}

impl Dist {
    pub fn new(p: &Params, net: &Network) -> Self {
        let index = net.road_ids.iter().enumerate().map(|(i, s)| (s.clone(), i)).collect();
        Dist { index, road: p.distance_basis == "road", factor: p.road_factor }
    }

    /// Scenario distance between two points. Ids unlock the road matrix when available.
    pub fn km(&self, net: &Network, a: (&str, f64, f64), b: (&str, f64, f64)) -> f64 {
        let gc = haversine(a.1, a.2, b.1, b.2);
        if !self.road {
            return gc * self.factor;
        }
        match (self.index.get(a.0), self.index.get(b.0)) {
            (Some(&i), Some(&j)) => {
                let (r1, r2) = (net.road[i][j], net.road[j][i]);
                let r = r1.min(r2);
                if r.is_finite() {
                    r.max(gc)
                } else {
                    gc * 1.9
                }
            }
            _ => gc * 1.9,
        }
    }
}

impl Instance {
    pub fn new(p: &Params) -> Self {
        let net = network();
        let f = p.annual_factor();
        let mult = p.demand_multiplier / (p.yield_saf * p.retention);
        let mut e = [0.0; 4];
        for a in 0..4 {
            e[a] = p.demand[a] * mult;
        }
        let mut cand: Vec<Cand> = net.sites.iter().map(|s| Cand { id: s.id.clone(), lat: s.lat, lon: s.lon }).collect();
        for (a, ap) in net.airports.iter().enumerate() {
            if a != ISLAND_AIRPORT {
                cand.push(Cand { id: ap.iata.clone(), lat: ap.lat, lon: ap.lon });
            }
        }
        cand.retain(|c| !p.forbid.iter().any(|x| x == &c.id));
        let rate = |s: usize| f * p.depot_capex[s] / p.depot_cap[s] + p.depot_var[s] / 1000.0;
        let mut inst = Instance {
            p: p.clone(),
            farm_kt: net.sites.iter().map(|s| s.kt * p.biomass_multiplier).collect(),
            cand: vec![],
            d_fc: vec![vec![]; net.sites.len()],
            d_ca: vec![],
            e,
            need: e.iter().sum(),
            fixed: [f * p.refinery_capex[0], f * p.refinery_capex[1]],
            cap_raw: [p.refinery_cap[0] / p.retention, p.refinery_cap[1] / p.retention],
            var_raw: [p.refinery_var[0] * p.retention / 1000.0, p.refinery_var[1] * p.retention / 1000.0],
            dep_rate: rate(0).min(rate(1)),
        };
        for c in cand {
            inst.push_cand(c);
        }
        inst
    }

    pub fn push_cand(&mut self, c: Cand) -> usize {
        let net = network();
        let dist = Dist::new(&self.p, net);
        for (i, s) in net.sites.iter().enumerate() {
            self.d_fc[i].push(dist.km(net, (&s.id, s.lat, s.lon), (&c.id, c.lat, c.lon)));
        }
        let mut row = [0.0; 4];
        for (a, ap) in net.airports.iter().enumerate() {
            row[a] = dist.km(net, (&c.id, c.lat, c.lon), (&ap.iata, ap.lat, ap.lon));
        }
        self.d_ca.push(row);
        self.cand.push(c);
        self.cand.len() - 1
    }

    /// Moves a candidate to new coordinates and refreshes its distances.
    pub fn move_cand(&mut self, k: usize, lat: f64, lon: f64) {
        let net = network();
        let dist = Dist::new(&self.p, net);
        self.cand[k].lat = lat;
        self.cand[k].lon = lon;
        let id = self.cand[k].id.clone();
        for (i, s) in net.sites.iter().enumerate() {
            self.d_fc[i][k] = dist.km(net, (&s.id, s.lat, s.lon), (&id, lat, lon));
        }
        for (a, ap) in net.airports.iter().enumerate() {
            self.d_ca[k][a] = dist.km(net, (&id, lat, lon), (&ap.iata, ap.lat, ap.lon));
        }
    }

    pub fn c(&self, i: usize, k: usize) -> f64 {
        self.p.tariff_fd * self.d_fc[i][k] / 1000.0
    }

    pub fn g(&self, k: usize, a: usize) -> f64 {
        self.p.tariff_ra * self.d_ca[k][a] * self.p.yield_saf * self.p.retention / 1000.0
    }
}

#[derive(Clone, Debug, Default)]
pub struct DepotMix {
    pub n: [usize; 2],
    pub through: [f64; 2],
    pub annual: f64,
}

/// Cheapest set of depot modules for a throughput. Large fills first, as it is cheaper per tonne.
pub fn depot_mix(q: f64, p: &Params) -> DepotMix {
    if q <= 1e-9 {
        return DepotMix::default();
    }
    let f = p.annual_factor();
    let mut best = DepotMix { annual: f64::INFINITY, ..Default::default() };
    let top = (q / p.depot_cap[1]).ceil() as usize + 1;
    for nl in 0..=top {
        let big = q.min(nl as f64 * p.depot_cap[1]);
        let rest = q - big;
        let ns = (rest / p.depot_cap[0] - 1e-9).ceil().max(0.0) as usize;
        let annual = f * (nl as f64 * p.depot_capex[1] + ns as f64 * p.depot_capex[0]) + (big * p.depot_var[1] + rest * p.depot_var[0]) / 1000.0;
        if annual < best.annual {
            best = DepotMix { n: [ns, nl], through: [rest, big], annual };
        }
    }
    best
}

#[derive(Clone, Debug)]
pub struct Alloc {
    /// (farm, index into open, raw kt)
    pub x: Vec<(usize, usize, f64)>,
    /// (index into open, airport, raw kt equivalent)
    pub w: Vec<(usize, usize, f64)>,
    pub flow_cost: f64,
    /// Raw kt through each open facility.
    pub q: Vec<f64>,
}

/// Exact optimal flows for a fixed set of open refineries, or None if demand cannot be met.
pub fn allocate(inst: &Instance, open: &[(usize, usize)]) -> Option<Alloc> {
    let (nf, m) = (inst.farm_kt.len(), open.len());
    let n_nodes = 2 + nf + 2 * m + 4;
    let (rin, rout, air) = (2 + nf, 2 + nf + m, 2 + nf + 2 * m);
    let mut g = Mcf::new(n_nodes);
    for i in 0..nf {
        g.add(0, 2 + i, inst.farm_kt[i], 0.0);
    }
    let mut ex = Vec::with_capacity(nf * m);
    let mut ew = Vec::with_capacity(m * 4);
    for (o, &(k, s)) in open.iter().enumerate() {
        for i in 0..nf {
            ex.push((i, o, g.add(2 + i, rin + o, inst.farm_kt[i], inst.c(i, k))));
        }
        g.add(rin + o, rout + o, inst.cap_raw[s], inst.var_raw[s]);
        for a in 0..4 {
            ew.push((o, a, g.add(rout + o, air + a, inst.e[a], inst.g(k, a))));
        }
    }
    for a in 0..4 {
        g.add(air + a, 1, inst.e[a], 0.0);
    }
    let (sent, cost) = g.run(0, 1, inst.need);
    if sent < inst.need - 1e-6 {
        return None;
    }
    let x: Vec<_> = ex.iter().map(|&(i, o, e)| (i, o, g.flow(e))).filter(|t| t.2 > 1e-7).collect();
    let w: Vec<_> = ew.iter().map(|&(o, a, e)| (o, a, g.flow(e))).filter(|t| t.2 > 1e-7).collect();
    let mut q = vec![0.0; m];
    for t in &x {
        q[t.1] += t.2;
    }
    Some(Alloc { x, w, flow_cost: cost, q })
}

/// Annual network cost for a fixed design, including integer depot modules.
pub fn total_cost(inst: &Instance, open: &[(usize, usize)], a: &Alloc) -> f64 {
    let fixed: f64 = open.iter().map(|&(_, s)| inst.fixed[s]).sum();
    let dep: f64 = a.q.iter().map(|&q| depot_mix(q, &inst.p).annual).sum();
    fixed + a.flow_cost + dep
}
