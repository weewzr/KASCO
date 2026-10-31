"""Checks the engine's defaults against the official Airbus workbook and airport file.

    cargo run --release -p saf_cli -- params
    python scripts/check_official.py
"""
import json
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
p = json.loads((ROOT / "docs" / "data" / "params.json").read_text())
wb = openpyxl.load_workbook(ROOT / "data" / "challenge3_parameters.xlsx", data_only=True)
fac = {(r[0].value, r[1].value): r for r in wb["facilities"].iter_rows(min_row=4, max_row=7)}
tr = list(wb["transport"].iter_rows(min_row=4, max_row=6, values_only=True))
air = pd.read_csv(ROOT / "data" / "airports.csv")
SIZE = {"Small": 0, "Large": 1}
checks = []


def check(name, engine, official):
    checks.append({"input": name, "engine": float(engine), "official": float(official), "passed": bool(abs(float(engine) - float(official)) < 1e-9)})


for (facility, size), row in fac.items():
    i, key = SIZE[size], facility.lower()
    check(f"{facility} {size} CapEx, USD M", p[f"{key}_capex"][i], row[2].value / 1e6)
    check(f"{facility} {size} capacity, kt", p[f"{key}_cap"][i], row[3].value)
    check(f"{facility} {size} variable OpEx, USD/t", p[f"{key}_var"][i], row[5].value)
    check(f"{facility} {size} fixed OpEx, USD M/yr", p[f"{key}_capex"][i] * p["fixed_opex_frac"], row[4].value / 1e6)
    check(f"{facility} {size} annualised CapEx, USD M/yr", p[f"{key}_capex"][i] / p["capex_years"], row[6].value / 1e6)
for key, row in zip(("tariff_fd", "tariff_dr", "tariff_ra"), tr):
    check(f"Tariff {row[0]}, USD/t/km", p[key], row[2])
for code, d in zip(air.iata, p["demand"]):
    check(f"Demand {code}, kt", d, air.set_index("iata").at[code, "saf_demand_kt_per_year"])
check("Yield, t/t", p["yield_saf"], 0.20)
check("Depot mass retention", p["retention"], 1.0)
check("Road factor", p["road_factor"], 1.3)
out = {"source": "challenge3_parameters.xlsx, challenge3_airports_4.csv, update of 31 Oct 2026 12:45", "n": len(checks), "all_passed": all(c["passed"] for c in checks), "checks": checks}
(ROOT / "docs" / "data" / "official_check.json").write_text(json.dumps(out, indent=1))
print(out["n"], "checks, all passed:", out["all_passed"])
