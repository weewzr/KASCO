"""Independent check of the Rust engine.

The Rust CLI exports the candidate-site MILP as a plain LP file. HiGHS, a separate
open-source solver, then solves that file. Agreement means the Rust search and the
algebraic formulation describe the same problem and reach the same optimum.

    cargo run --release -p saf_cli -- lp model.lp
    python scripts/verify_highs.py model.lp [seconds] [rust_objective]
"""
import json
import sys
from pathlib import Path

import highspy

path = sys.argv[1]
limit = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
rust = float(sys.argv[3]) if len(sys.argv) > 3 else None

h = highspy.Highs()
h.setOptionValue("output_flag", False)
h.setOptionValue("time_limit", limit)
h.setOptionValue("mip_rel_gap", 0.001)
h.readModel(path)
h.run()
info = h.getInfo()
out = {
    "solver": "HiGHS " + h.version(),
    "model_status": h.modelStatusToString(h.getModelStatus()),
    "objective": info.objective_function_value,
    "bound": info.mip_dual_bound,
    "gap_pct": 100 * info.mip_gap,
    "columns": h.getNumCol(),
    "rows": h.getNumRow(),
    "time_limit_s": limit,
    "rust_candidate_objective": rust,
}
if rust is not None:
    out["difference_pct"] = 100 * (rust - info.objective_function_value) / info.objective_function_value
Path("docs/data").mkdir(parents=True, exist_ok=True)
Path("docs/data/highs_check.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
