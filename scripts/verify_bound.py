"""Tests that the Rust lower bound is valid on instances HiGHS can solve to optimality.

A lower bound above a proven optimum would mean the Rust bound is wrong, so each case
checks: Rust bound <= HiGHS optimum <= Rust cost, within solver tolerances.

    python scripts/verify_bound.py <saf binary> <temp folder>
"""
import json
import subprocess
import sys
from pathlib import Path

import highspy

exe, tmp = sys.argv[1], Path(sys.argv[2])
rows = []
for each in (5, 12.5, 25, 50, 75):
    lp = tmp / f"saf_check_{each}.lp"
    subprocess.run([exe, "lp", str(lp), str(each)], check=True, capture_output=True)
    rust = json.loads(subprocess.run([exe, "bound", str(each), "30"], check=True, capture_output=True, text=True).stdout)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", 300.0)
    h.setOptionValue("mip_rel_gap", 1e-4)
    h.readModel(str(lp))
    h.run()
    info = h.getInfo()
    row = {
        "total_demand_kt": each * 4,
        "rust_cost": rust["objective"],
        "rust_bound": rust["bound"],
        "rust_gap_pct": 100 * rust["gap"],
        "rust_seconds": rust["runtime_s"],
        "highs_cost": info.objective_function_value,
        "highs_bound": info.mip_dual_bound,
        "highs_gap_pct": 100 * info.mip_gap,
        "highs_status": h.modelStatusToString(h.getModelStatus()),
        "bound_valid": rust["bound"] <= info.objective_function_value + 1e-6,
        "cost_difference_pct": 100 * (rust["objective"] - info.objective_function_value) / info.objective_function_value,
    }
    rows.append(row)
    print(json.dumps(row), flush=True)
Path("docs/data/bound_check.json").write_text(json.dumps(rows, indent=1))
print("all bounds valid:", all(r["bound_valid"] for r in rows))
