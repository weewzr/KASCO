# Mathematical model

This is the model behind KASCO, the Kalimantan SAF Supply Chain Optimiser. The full treatment, with results, is in `reports/KASCO_Technical_Report.pdf`. All inputs below are the official values from the Airbus update of 31 October 2026, 12:45.

## Reference frame

| Symbol | Meaning | Units |
|---|---|---|
| $i, j, k, a, s$ | biomass site, depot site, refinery site, airport, size | |
| $x_{ij}$, $u_{jk}$, $w_{ka}$ | flows: site to depot, depot to refinery, refinery to airport | kt/yr |
| $y_{js}$ | depot modules of size $s$ at $j$ (integer) | count |
| $z_{ks}$ | refinery of size $s$ open at $k$ (binary) | |
| $t_{js}$, $r_{ks}$ | throughput by size at depot and refinery | kt/yr |
| $B_i$, $D_a$ | biomass available, SAF demand | kt/yr |
| $\eta = 0.20$, $\rho = 1$ | yield, depot mass retention | t/t |
| $F^D_s$, $F^R_s$ | CapEx: 2.25, 4.5; 480, 765 | USD M |
| $C^D_s$, $C^R_s$ | biomass intake capacity: 150, 300; 500, 1,087 | kt/yr |
| $v^D_s$, $v^R_s$ | variable OpEx: 5, 4; 60, 55 | USD/t |
| $D_a$ | SAF demand: 300 per airport, 1,200 in total | kt/yr |
| $\tau_1, \tau_2, \tau_3 = 0.10, 0.12, 0.08$ | tariffs | USD/t/km |
| $n = 20$, $f = 0.05$ | CapEx life, fixed OpEx share | yr, 1/yr |

## Objective

$$\min \left(\tfrac{1}{n}+f\right)\Big[\sum F^D_s y_{js}+\sum F^R_s z_{ks}\Big]+\sum v^D_s t_{js}+\sum v^R_s r_{ks}+\sum\tau_1 d_{ij}x_{ij}+\sum\tau_2 d_{jk}u_{jk}+\sum\tau_3 d_{ka}w_{ka}$$

## Constraints

$$\sum_j x_{ij}\le B_i \qquad \sum_i x_{ij}=\sum_s t_{js} \qquad t_{js}\le C^D_s y_{js}$$

$$\sum_k u_{jk}=\rho\sum_i x_{ij} \qquad \sum_j u_{jk}=\sum_s r_{ks} \qquad r_{ks}\le C^R_s z_{ks}$$

$$\sum_a w_{ka}=\eta\sum_s r_{ks} \qquad \sum_k w_{ka}\ge D_a \qquad \sum_s z_{ks}\le 1$$

Distances are great-circle x 1.3. The last leg to Tarakan is by barge at the same tariff. Truck size cannot affect cost, because both sizes share one tariff.

## Why depots sit at refineries

For biomass moving $i \to j \to k$, transport per tonne is $\tau_1 d_{ij}+\rho\tau_2 d_{jk}$. If $\rho\tau_2\ge\tau_1$, this is at least $\tau_1(d_{ij}+d_{jk})\ge\tau_1 d_{ik}$ by the triangle inequality. So for a depot serving one refinery, moving it to that refinery never costs more.

A depot feeding two refineries needs more care, since splitting it could add a module. The base-fleet margin is USD 1.03M/yr, the difference between actual depot cost and its linear floor. `scripts/verify_depots.py` closes it: with the six base refineries fixed and depots free to go anywhere, HiGHS proves the co-located cost is optimal.

This holds for metric distances, $\rho\tau_2\ge\tau_1$ and this fleet. It reverses below $\rho=0.833$, so real wet feedstock could change it.

## Solution method

1. Relax supply and demand with multipliers. Each site then solves a small subproblem exactly, which gives a valid lower bound. The relaxed problem may pick one site in both sizes, which keeps the bound valid.
2. Tighten with subgradient steps and search refinery sites by branch-and-bound. Biomass sites are near-substitutes, so most of the bound comes from the root relaxation.
3. Price every design with exact min-cost flow.
4. Refine coordinates by alternating Weiszfeld moves and re-allocation, keeping plants on land. This step gives a local optimum with no global proof.

## Status of results

| Result | Status |
|---|---|
| Base case on candidate sites | Feasible within a proven gap |
| Five smaller cases | Rust cost equals the HiGHS proven optimum |
| Refined coordinates | Local refinement, no global proof |
| Field depots | Heuristic, no optimality proof |

## Evidence

On the base case, HiGHS reached the same cost from an exported LP file, which covers co-located depots. On five smaller cases HiGHS proved the optimum, the Rust engine matched it, and the Rust bound stayed valid. See `data/highs_check.json`, `data/bound_check.json`, `data/depot_check.json` and `data/grid_check.json`.
