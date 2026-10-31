"""Engine tests. Every solve here is a real HiGHS run."""
import math

import pytest

from saf.baselines import airport_baseline, greedy_baseline, trip_counts
from saf.config import AIRPORT_PAX_2024, DEPOT_CAP, Params, crf, jet_uplift_kt, litres_per_pax
from saf.data import load_network, validate_inputs
from saf.diagnostics import diagnose
from saf.explain import answer, parse_change
from saf.model import airport_demand, max_saf_kt, min_refinery_fleet, required_biomass_kt, solve
from saf.validate import all_passed, check


@pytest.fixture(scope="module")
def net():
    return load_network()


@pytest.fixture(scope="module")
def base(net):
    p = Params()
    return p, solve(p, net).to_dict()


@pytest.fixture(scope="module")
def mid(net):
    p = Params(blend=0.5)
    return p, solve(p, net).to_dict()


@pytest.fixture(scope="module")
def multi(net):
    p = Params(demand_mode="absolute", airport_kt={"PNK": 30.0, "PKN": 10.0, "BPN": 120.0, "TRK": 20.0}, time_limit_s=45.0, mip_gap=0.02)
    return p, solve(p, net).to_dict()


def test_official_dataset_matches_brief(net):
    v = validate_inputs(net)
    assert v["n_sites"] == 80
    assert v["total_kt"] == pytest.approx(6800.0, abs=0.01)
    assert v["tonnes_match"]
    assert v["null_cells"] == 0
    assert v["duplicate_ids"] == 0
    assert 20 <= v["min_kt"] and v["max_kt"] <= 100


def test_four_airports_are_the_correct_ones(net):
    a = net.airports.set_index("iata")
    assert list(a.index) == ["PNK", "PKN", "BPN", "TRK"]
    assert a.at["PKN", "city"] == "Pangkalan Bun"
    assert "Muda" not in a.at["PKN", "dat_name"]


def test_road_matrix_is_complete_and_above_straight_line(net):
    assert net.road.shape == (84, 84)
    assert net.road.isna().sum().sum() == 0
    assert (net.road.values >= 0).all()


def test_uplift_estimate_is_consistent():
    assert 13 < litres_per_pax() < 15
    u = jet_uplift_kt()
    assert set(u) == set(AIRPORT_PAX_2024)
    assert 95 < sum(u.values()) < 105
    assert u["BPN"] > u["PNK"] > u["TRK"] > u["PKN"]


def test_crf_matches_course_note():
    assert crf(0.10, 20) == pytest.approx(0.11746, abs=1e-5)


def test_fleet_knapsack_prefers_mix():
    cost, n = min_refinery_fleet(6732, {"small": 500, "large": 1087}, {"small": 480, "large": 765})
    assert cost == 6 * 765 + 480
    assert n == 7


def test_base_case_is_optimal_and_valid(base, net):
    p, s = base
    assert s["status"] == "optimal"
    assert all_passed(check(s, p, net))


def test_mid_case_is_valid(mid, net):
    p, s = mid
    assert s["status"] in ("optimal", "feasible_gap")
    assert all_passed(check(s, p, net))


def test_multi_refinery_case_is_valid(multi, net):
    p, s = multi
    assert s["status"] in ("optimal", "feasible_gap")
    assert s["kpis"]["n_refineries"] >= 1
    assert all_passed(check(s, p, net))


def test_demand_is_met_at_every_airport(base, net):
    p, s = base
    for a, d in airport_demand(p, net).items():
        assert s["kpis"]["delivered_by_airport"][a] >= d - 1e-3


def test_biomass_never_exceeds_site_supply(multi, net):
    p, s = multi
    supply = dict(zip(net.sites.location_id, net.sites.production_kilotons))
    shipped = {}
    for f in s["flows_fd"]:
        shipped[f["src"]] = shipped.get(f["src"], 0) + f["kt"]
    assert all(q <= supply[i] + 1e-3 for i, q in shipped.items())


def test_depot_capacity_respected(multi):
    _, s = multi
    for d in s["depots"]:
        assert d["throughput"] <= DEPOT_CAP[d["size"]] + 1e-3


def test_mass_balance_and_yield(multi):
    p, s = multi
    k = s["kpis"]
    assert k["gate_biomass_kt"] == pytest.approx(k["biomass_used_kt"] * p.retention, rel=1e-4)
    assert k["saf_kt"] == pytest.approx(k["gate_biomass_kt"] * p.yield_saf, rel=1e-4)


def test_no_flow_through_closed_facility(multi):
    _, s = multi
    opened = {d["id"] for d in s["depots"]}
    assert {f["dst"] for f in s["flows_fd"]} <= opened
    opened = {r["id"] for r in s["refineries"]}
    assert {f["dst"] for f in s["flows_dr"]} <= opened


def test_objective_is_sum_of_parts(base):
    _, s = base
    c = s["costs"]
    parts = c["annual_capital"] + c["opex_fixed"] + c["opex_variable"] + c["logistics_total"]
    assert parts == pytest.approx(s["objective"], rel=1e-5)


def test_changing_inputs_changes_the_answer(net, base):
    p, s = base
    higher = solve(p.with_(tariff_ra=p.tariff_ra * 3), net)
    assert higher.objective > s["objective"]
    cheaper = solve(p.with_(refinery_capex={"small": 240.0, "large": 765.0}), net)
    assert cheaper.objective < s["objective"]


def test_lower_yield_needs_more_biomass(net, mid):
    p, s = mid
    low = solve(p.with_(yield_saf=0.12), net)
    assert low.kpis["biomass_used_kt"] > s["kpis"]["biomass_used_kt"]


def test_truck_size_cannot_change_cost(base):
    _, s = base
    t = trip_counts(s)
    assert t["refinery_airport"]["trips_small"] >= t["refinery_airport"]["trips_large"]
    assert s["costs"]["logistics_refinery_airport"] > 0


def test_supply_infeasible_is_detected_and_explained(net):
    p = Params(demand_mode="hub", demand_multiplier=1.2, time_limit_s=20.0)
    assert required_biomass_kt(p, net) > 6800
    d = diagnose(p, net)
    assert d["findings"][0]["limit"] == "Biomass supply"
    assert solve(p, net).status == "infeasible"


def test_refinery_count_infeasible_is_detected(net):
    p = Params(demand_mode="hub", max_refineries=4, time_limit_s=20.0)
    assert any(f["limit"] == "Refinery count" for f in diagnose(p, net)["findings"])
    assert solve(p, net).status == "infeasible"


def test_hub_demand_equals_feedstock_potential(net):
    p = Params(demand_mode="hub")
    assert sum(airport_demand(p, net).values()) == pytest.approx(max_saf_kt(p, net))
    assert max_saf_kt(p, net) == pytest.approx(6800 * 0.99 * 0.18, rel=1e-3)


def test_baselines_are_valid_and_not_cheaper(base, mid, net):
    for p, s in (base, mid):
        for fn in (greedy_baseline, airport_baseline):
            b = fn(p, net).to_dict()
            assert all_passed(check(b, p, net)), fn.__name__
            assert b["objective"] >= s["objective"] - 1e-6


def test_explainer_uses_solver_numbers(base, net):
    p, s = base
    a = answer("Which routes are most expensive?", s, p, net)
    top = max(s["flows_ra"], key=lambda f: f["usd_m"])
    assert top["src"] in a["text"] and not a["declined"]


def test_explainer_declines_unmodelled_questions(base, net):
    p, s = base
    a = answer("What is the lifecycle CO2 of this network?", s, p, net)
    assert a["declined"] and a["intent"] == "declined"


def test_explainer_reruns_solver_for_what_if(base, net):
    p, s = base
    a = answer("What happens if demand increases by 20%?", s, p, net)
    assert a["intent"] == "what_if"
    assert "reran" in a["text"]


def test_what_if_parser_maps_to_inputs():
    p = Params()
    new, _ = parse_change("transport up 30%", p)
    assert new.tariff_fd == pytest.approx(0.13)
    new, _ = parse_change("biomass down 10%", p)
    assert new.biomass_multiplier == pytest.approx(0.9)
    new, _ = parse_change("what if yield 0.12", p)
    assert new.yield_saf == 0.12
    new, _ = parse_change("hello", p)
    assert new is None
