"""Named scenarios shipped with the app. Every one is solved, none is hard-coded."""
from .config import PATHWAYS, Params

FT = PATHWAYS["FT"]
ATJ = PATHWAYS["ATJ"]

BASE = Params(name="Policy base: 5% blend")
HUB = Params(name="Full feedstock hub", demand_mode="hub", time_limit_s=600.0, mip_gap=0.01)

SCENARIOS = {
    "policy_base": BASE,
    "policy_2026": BASE.with_(name="Policy 2026: 1% blend", blend=0.01),
    "high_demand": BASE.with_(name="High demand: 50% blend (ASTM limit)", blend=0.50),
    "hub_full": HUB,
    "hub_high_transport": HUB.with_(
        name="Hub, transport tariffs +50%",
        tariff_fd=0.15, tariff_dr=0.18, tariff_ra=0.12,
    ),
    "hub_output_basis": HUB.with_(name="Hub, capacity read as SAF output", refinery_basis="output"),
    "hub_wet_feed": HUB.with_(name="Hub, wet feed dried at depots (retention 0.55)", retention=0.55),
    "hub_atj": HUB.with_(name="Hub, Alcohol-to-Jet pathway", pathway="ATJ", yield_saf=ATJ["yield"], refinery_opex_var=ATJ["opex_var"]),
    "infeasible_demand": HUB.with_(name="Infeasible: hub demand +20%", demand_multiplier=1.20),
    "constrained_refineries": HUB.with_(name="Infeasible: at most 4 refineries", max_refineries=4),
}

# The four the brief asks for, shown side by side by default.
CORE = ["policy_base", "high_demand", "hub_high_transport", "infeasible_demand"]
