"""All inputs in one place, each tagged with where it came from.

Tags
    OFFICIAL    Airbus problem statement or its datasets. Never altered by default.
    LITERATURE  Taken from a cited paper or course note.
    PUBLIC      Taken from a public statistic or press report.
    ASSUMPTION  Our own choice, stated so a reviewer can challenge it.
"""
from dataclasses import asdict, dataclass, field, replace

# Official Airbus inputs
DEPOT_CAPEX = {"small": 2.25, "large": 4.5}  # USD M per facility
DEPOT_CAP = {"small": 150.0, "large": 300.0}  # kt/yr throughput
REFINERY_CAPEX = {"small": 480.0, "large": 765.0}  # USD M per facility
REFINERY_CAP = {"small": 500.0, "large": 1087.0}  # kt/yr
TARIFF_FARM_DEPOT = 0.10  # USD/t/km
TARIFF_DEPOT_REFINERY = 0.12  # USD/t/km
TARIFF_REFINERY_AIRPORT = 0.08  # USD/t/km
TRUCK_T = {"farm_depot": (3, 9), "depot_refinery": (18, 30), "refinery_airport": (16, 32)}
TOTAL_FEEDSTOCK_KT = 6800.0
SIZES = ("small", "large")

# Conversion pathways, Huang et al. 2019: t jet per t biomass and USD/t biomass
PATHWAYS = {
    "FT": {"yield": 0.18, "opex_var": 10.0, "label": "Gasification Fischer-Tropsch"},
    "ATJ": {"yield": 0.12, "opex_var": 56.0, "label": "Alcohol-to-Jet"},
    "HTL": {"yield": 0.02, "opex_var": 43.0, "label": "Hydrothermal liquefaction (jet fraction only)"},
}

# Jet fuel uplift evidence
JET_DENSITY = 0.80  # t per kL
AIRPORT_PAX_2024 = {"PNK": 2387536, "PKN": 472637, "BPN": 5534519, "TRK": 651557}
AIRPORT_AVTUR_KL_PER_DAY = {"PNK": 77.0, "BPN": 222.0}  # Pertamina Patra Niaga 2024 press figures


def litres_per_pax() -> float:
    """Pooled fuel intensity from the two airports with published avtur volumes."""
    kl = sum(v * 365 for v in AIRPORT_AVTUR_KL_PER_DAY.values())
    pax = sum(AIRPORT_PAX_2024[a] for a in AIRPORT_AVTUR_KL_PER_DAY)
    return kl * 1000 / pax


def jet_uplift_kt() -> dict:
    """Annual jet uplift per airport in kt/yr. PKN and TRK are scaled by passengers."""
    out = {}
    lpp = litres_per_pax()
    for code, pax in AIRPORT_PAX_2024.items():
        kl = AIRPORT_AVTUR_KL_PER_DAY[code] * 365 if code in AIRPORT_AVTUR_KL_PER_DAY else pax * lpp / 1000
        out[code] = kl * JET_DENSITY / 1000
    return out


def crf(r: float, n: int) -> float:
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


@dataclass
class Params:
    """One complete scenario. Every field can be edited in the simulator."""

    name: str = "Custom"
    demand_mode: str = "blend"  # blend: share of uplift, hub: all feedstock, absolute: airport_kt
    blend: float = 0.05
    airport_kt: dict = field(default_factory=dict)
    demand_multiplier: float = 1.0
    uplift_kt: dict = field(default_factory=jet_uplift_kt)

    biomass_multiplier: float = 1.0
    pathway: str = "FT"
    yield_saf: float = PATHWAYS["FT"]["yield"]
    retention: float = 0.99  # depot mass retention, Ng and Maravelias 2017
    refinery_basis: str = "input"  # input: biomass at gate, output: SAF produced

    depot_capex: dict = field(default_factory=lambda: dict(DEPOT_CAPEX))
    depot_cap: dict = field(default_factory=lambda: dict(DEPOT_CAP))
    refinery_capex: dict = field(default_factory=lambda: dict(REFINERY_CAPEX))
    refinery_cap: dict = field(default_factory=lambda: dict(REFINERY_CAP))

    tariff_fd: float = TARIFF_FARM_DEPOT
    tariff_dr: float = TARIFF_DEPOT_REFINERY
    tariff_ra: float = TARIFF_REFINERY_AIRPORT
    distance_multiplier: float = 1.0

    discount_rate: float = 0.10
    life_years: int = 20
    fixed_opex_frac: float = 0.105  # of CapEx per year, Huang et al. 2019
    refinery_opex_var: float = PATHWAYS["FT"]["opex_var"]  # USD/t biomass at refinery gate
    depot_opex_var: float = 0.0  # USD/t, no sourced value, so left at zero
    biomass_price: float = 0.0  # USD/t, no Kalimantan source, excluded by default

    max_refineries: int = 0  # 0 means no limit
    max_depots: int = 0
    forbid_refineries: tuple = ()
    forbid_depots: tuple = ()
    allow_refinery_sites: tuple = ()  # empty means all candidates
    allow_depot_sites: tuple = ()

    time_limit_s: float = 60.0
    mip_gap: float = 0.005

    @property
    def annuity(self) -> float:
        return crf(self.discount_rate, self.life_years)

    def to_dict(self) -> dict:
        return asdict(self)

    def with_(self, **kw) -> "Params":
        return replace(self, **kw)


# Register shown in the app and report. Source keys resolve to the reference list.
ASSUMPTIONS = [
    ("Biomass per site", "80 sites, 6,800 kt total", "OFFICIAL", "Airbus brief and CSV", "Treated as dry mass per year. The brief states neither basis."),
    ("Facility cost and capacity", "See Table 1", "OFFICIAL", "Airbus brief", "Refinery cost matches a 0.60 scale exponent to within 0.02%."),
    ("Road tariffs", "0.10, 0.12, 0.08 USD/t/km", "OFFICIAL", "Airbus brief", "Identical for both truck sizes, so truck size cannot affect cost."),
    ("Refinery capacity basis", "Biomass input at gate", "ASSUMPTION", "User decision; Huang et al. 2019 size plants by input", "The brief says 'production capacity'. The SAF output reading is run as a scenario."),
    ("Jet uplift BPN", "222 kL/day", "PUBLIC", "Pertamina Patra Niaga, March 2024, via press", "City-level figure. Balikpapan has one commercial airport."),
    ("Jet uplift PNK", "77 kL/day", "PUBLIC", "Pertamina Patra Niaga, April 2024, via Pontianak Post", "Reported for West Kalimantan as a whole, so this is an upper bound for PNK."),
    ("Jet uplift PKN and TRK", "Scaled by 2024 passengers", "ASSUMPTION", "DGCA and BPS passengers; pooled 13.8 L per passenger", "No published volumes found. Both are small, so the total is insensitive."),
    ("Jet density", "0.80 t/kL", "ASSUMPTION", "Typical Jet A-1 value", "Range about 0.775 to 0.84."),
    ("SAF blend, base case", "5% of uplift", "PUBLIC", "Singapore 3 to 5% by 2030 target applied to Indonesia", "Indonesia's 1% from 2027 covers only international departures at Jakarta and Bali."),
    ("Conversion yield", "0.18 t SAF per t biomass (FT)", "LITERATURE", "Huang et al. 2019", "Corn stover value. No Kalimantan residue value found."),
    ("Depot mass retention", "0.99", "LITERATURE", "Ng and Maravelias 2017", "Dry-mass basis. A wet feed scenario tests 0.55."),
    ("Refinery variable OpEx", "USD 10/t biomass (FT)", "LITERATURE", "Huang et al. 2019", "Includes an electricity credit, so it is low."),
    ("Fixed OpEx", "10.5% of CapEx per year", "LITERATURE", "Huang et al. 2019", "Published for refineries. Applied to depots by assumption."),
    ("Capital recovery", "CRF 0.1175 (r = 10%, n = 20)", "LITERATURE", "CN4252 TEA method; 10% rate in Ng and Maravelias 2017", "Huang et al. use 0.121, which is within 3%."),
    ("Biomass purchase price", "Excluded", "ASSUMPTION", "No Kalimantan source found", "The brief lists OpEx, CapEx and logistics only. Editable in the simulator."),
    ("Distances", "OSRM road network km", "PUBLIC", "OpenStreetMap via OSRM, sampled October 2026", "Median 1.9 times great-circle. Includes the ferry link to Tarakan at road tariff."),
]
