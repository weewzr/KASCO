//! Min-cost flow by successive shortest paths with node potentials.
//!
//! The graphs here have about a hundred nodes, so a dense Dijkstra is both simple and
//! fast. Once the open facilities are fixed, this solves the allocation exactly.

const INF: f64 = 1e30;
const EPS: f64 = 1e-9;

#[derive(Clone)]
struct Edge {
    to: usize,
    cap: f64,
    cost: f64,
}

pub struct Mcf {
    adj: Vec<Vec<usize>>,
    edges: Vec<Edge>,
    orig_cap: Vec<f64>,
}

impl Mcf {
    pub fn new(n: usize) -> Self {
        Mcf { adj: vec![vec![]; n], edges: Vec::with_capacity(4096), orig_cap: Vec::with_capacity(2048) }
    }

    /// Adds an arc and returns its handle.
    pub fn add(&mut self, u: usize, v: usize, cap: f64, cost: f64) -> usize {
        let id = self.edges.len();
        self.edges.push(Edge { to: v, cap, cost });
        self.edges.push(Edge { to: u, cap: 0.0, cost: -cost });
        self.adj[u].push(id);
        self.adj[v].push(id + 1);
        self.orig_cap.push(cap);
        id
    }

    pub fn flow(&self, id: usize) -> f64 {
        self.edges[id + 1].cap
    }

    /// Pushes up to `want` units from s to t. Returns (flow sent, total cost).
    pub fn run(&mut self, s: usize, t: usize, want: f64) -> (f64, f64) {
        let n = self.adj.len();
        let mut h = vec![0.0; n];
        let mut dist = vec![INF; n];
        let mut seen = vec![false; n];
        let mut prev = vec![usize::MAX; n];
        let (mut sent, mut total) = (0.0, 0.0);
        while sent < want - EPS {
            dist.iter_mut().for_each(|d| *d = INF);
            seen.iter_mut().for_each(|b| *b = false);
            dist[s] = 0.0;
            for _ in 0..n {
                let mut u = usize::MAX;
                let mut best = INF;
                for v in 0..n {
                    if !seen[v] && dist[v] < best {
                        best = dist[v];
                        u = v;
                    }
                }
                if u == usize::MAX {
                    break;
                }
                seen[u] = true;
                for &e in &self.adj[u] {
                    let edge = &self.edges[e];
                    if edge.cap > EPS {
                        let rc = (edge.cost + h[u] - h[edge.to]).max(0.0);
                        if dist[u] + rc < dist[edge.to] - 1e-14 {
                            dist[edge.to] = dist[u] + rc;
                            prev[edge.to] = e;
                        }
                    }
                }
            }
            if dist[t] >= INF {
                break;
            }
            let top = dist.iter().cloned().filter(|d| *d < INF).fold(0.0, f64::max);
            for v in 0..n {
                h[v] += if dist[v] < INF { dist[v] } else { top };
            }
            let mut push = want - sent;
            let mut v = t;
            while v != s {
                let e = prev[v];
                push = push.min(self.edges[e].cap);
                v = self.edges[e ^ 1].to;
            }
            let mut v = t;
            while v != s {
                let e = prev[v];
                self.edges[e].cap -= push;
                self.edges[e ^ 1].cap += push;
                total += push * self.edges[e].cost;
                v = self.edges[e ^ 1].to;
            }
            sent += push;
        }
        (sent, total)
    }
}
