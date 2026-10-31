//! Every input, with the official values from the Airbus update as defaults.
use serde::{Deserialize, Serialize};

pub const SIZES: [&str; 2] = ["small", "large"];
pub const AIRPORTS: [&str; 4] = ["PNK", "PKN", "BPN", "TRK"];
/// Tarakan is an island, so biomass cannot reach a refinery sited there.
pub const ISLAND_AIRPORT: usize = 3;
pub const SMALL: usize = 0;
pub const LARGE: usize = 1;
pub const TRUCKS_T: [[f64; 2]; 3] = [[3.0, 9.0], [18.0, 30.0], [16.0, 32.0]];

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Params {
    pub name: String,
    /// SAF demand in kt/yr: PNK, PKN, BPN, TRK.
    pub demand: [f64; 4],
    pub demand_multiplier: f64,
    pub biomass_multiplier: f64,
    pub yield_saf: f64,
    pub retention: f64,
    /// colocated: depots sit at their refinery. field: depots at biomass sites.
    pub depot_mode: String,
    /// Longest first-leg haul allowed in field mode, km.
    pub field_radius_km: f64,
    pub depot_capex: [f64; 2],
    pub depot_cap: [f64; 2],
    pub depot_var: [f64; 2],
    pub refinery_capex: [f64; 2],
    pub refinery_cap: [f64; 2],
    pub refinery_var: [f64; 2],
    pub tariff_fd: f64,
    pub tariff_dr: f64,
    pub tariff_ra: f64,
    /// great_circle uses road_factor, road uses the OSRM matrix.
    pub distance_basis: String,
    pub road_factor: f64,
    pub capex_years: f64,
    pub fixed_opex_frac: f64,
    /// 0 means no limit.
    pub max_refineries: usize,
    pub forbid: Vec<String>,
    pub refine: bool,
    pub time_limit_s: f64,
    pub gap_target: f64,
}

impl Default for Params {
    fn default() -> Self {
        Params {
            name: "Official base case".into(),
            demand: [300.0; 4],
            demand_multiplier: 1.0,
            biomass_multiplier: 1.0,
            yield_saf: 0.20,
            retention: 1.0,
            depot_mode: "colocated".into(),
            field_radius_km: 60.0,
            depot_capex: [2.25, 4.5],
            depot_cap: [150.0, 300.0],
            depot_var: [5.0, 4.0],
            refinery_capex: [480.0, 765.0],
            refinery_cap: [500.0, 1087.0],
            refinery_var: [60.0, 55.0],
            tariff_fd: 0.10,
            tariff_dr: 0.12,
            tariff_ra: 0.08,
            distance_basis: "great_circle".into(),
            road_factor: 1.3,
            capex_years: 20.0,
            fixed_opex_frac: 0.05,
            max_refineries: 0,
            forbid: vec![],
            refine: true,
            time_limit_s: 20.0,
            gap_target: 0.002,
        }
    }
}

impl Params {
    /// Annualised CapEx plus fixed OpEx per unit of CapEx.
    pub fn annual_factor(&self) -> f64 {
        1.0 / self.capex_years + self.fixed_opex_frac
    }
    pub fn total_demand(&self) -> f64 {
        self.demand.iter().sum::<f64>() * self.demand_multiplier
    }
    /// Raw biomass needed to meet demand, kt/yr.
    pub fn raw_need(&self) -> f64 {
        self.total_demand() / (self.yield_saf * self.retention)
    }
    /// With no cheaper second leg, a depot away from its refinery can never pay.
    pub fn colocation_dominant(&self) -> bool {
        self.tariff_dr * self.retention >= self.tariff_fd - 1e-12
    }
}
