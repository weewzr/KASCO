# Mathematical model

The full treatment, with results, is in `reports/Kalimantan_SAF_Technical_Report.pdf`. All inputs below are the official values from the Airbus update of 31 October 2026, 12:45.

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
| $F^D_s$, $F^R_s$ | CapEx | USD M |
| $C^D_s$, $C^R_s$ | biomass intake capacity | kt/yr |
| $v^D_s$, $v^R_s$ | variable OpEx | USD/t |
| $\tau_1, \tau_2, \tau_3 = 0.10, 0.12, 0.08$ | tariffs | USD/t/km |
| $n = 20$, $f = 0.05$ | CapEx life, fixed OpEx share | yr, 1/yr |

## Objective

$$\min \left(\tfrac{1}{n}+f\right)\Big[\sum F^D_s y_{js}+\sum F^R_s z_{ks}\Big]+\sum v^D_s t_{js}+\sum v^R_s r_{ks}+\sum\tau_1 d_{ij}x_{ij}+\sum\tau_2 d_{jk}u_{jk}+\sum\tau_3 d_{ka}w_{ka}$$

## Constraints

$$\sum_j x_{ij}\le B_i \qquad \sum_i x_{ij}=\sum_s t_{js} \qquad t_{js}\le C^D_s y_{js}$$

$$\sum_k u_{jk}=\rho\sum_i x_{ij} \qquad \sum_j u_{jk}=\sum_s r_{ks} \qquad r_{ks}\le C^R_s z_{ks}$$

$$\sum_a w_{ka}=\eta\sum_s r_{ks} \qquad \sum_k w_{ka}\ge D_a \qquad \sum_s z_{ks}\le 1$$

Distances are great-circle x 1.3. The last leg to Tarakan is by barge at the same tariff.

## Why depots sit at refineries

For biomass moving $i \to j \to k$, transport per tonne is $\tau_1 d_{ij}+\rho\tau_2 d_{jk}$. If $\rho\tau_2\ge\tau_1$, this is at least $\tau_1(d_{ij}+d_{jk})\ge\tau_1 d_{ik}$ by the triangle inequality, so moving the depot to $k$ never costs more. With $\rho=1$ and $\tau_2>\tau_1$, co-location is optimal. It reverses below $\rho=0.833$.

## Solution method

1. Relax supply and demand with multipliers. Each site then solves a small subproblem exactly, which gives a valid lower bound.
2. Tighten with subgradient steps and close the gap by branch-and-bound over refinery sites.
3. Price every design with exact min-cost flow.
4. Refine coordinates by alternating Weiszfeld moves and re-allocation, keeping plants on land. This step gives a local optimum with no global proof.

## Evidence

On the base case, HiGHS reached the same cost from an exported LP file. On five smaller cases HiGHS proved the optimum, the Rust engine matched it, and the Rust bound stayed valid. See `data/highs_check.json` and `data/bound_check.json`.
