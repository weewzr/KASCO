"""Write the ready-to-copy submission text, with figures read from the solver results.

    python scripts/make_submission.py
"""
import json
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"


def load(n):
    return json.loads((DATA / f"{n}.json").read_text())


base, B = load("official_base"), load("baselines")
cost, gap = base["objective"], 100 * base["gap"]
low, high = B["greedy"]["saving_usd_m"], B["airport_first"]["saving_usd_m"]

TITLE = "KASCO — Kalimantan SAF Supply Chain Optimiser"
LIVE = "https://weewzr.github.io/airbustrack3ray/"
REPO = "https://github.com/weewzr/airbustrack3ray"
SUMMARY = (
    "KASCO is a working prototype for planning a Sustainable Aviation Fuel supply chain across Kalimantan, built for Airbus Challenge 3. "
    "Using the official challenge data, it connects 80 biomass sites to depots, refineries and four international airports. "
    "A Rust optimisation engine, running in the browser through WebAssembly, selects facility sites and sizes, routes every tonne and proves how close each network is to the best possible on candidate sites. "
    "Planners explore an interactive map, rerun scenarios and ask explainable, solver-grounded questions, and the assistant refuses what the model cannot support. "
    f"The base case meets all 1,200 kt of demand at USD {cost:.1f}M a year, within a proven {gap:.2f}% gap, and USD {low:.0f}M to {high:.0f}M below two simple heuristic layouts. "
    "HiGHS independently reached the same cost. KASCO helps a planner test decisions and find their limits before committing capital."
)
SHORT = (
    "KASCO is a working prototype that optimises a Sustainable Aviation Fuel supply chain across Kalimantan on the official Airbus Challenge 3 data. "
    "A Rust solver running in the browser picks depot and refinery sites, routes biomass and SAF to four airports, and reports a proven gap. "
    f"Users explore an interactive map, rerun scenarios and get explainable, solver-grounded answers. Base case: USD {cost:.1f}M a year, with all 1,200 kt of demand met."
)
words = len(SUMMARY.split())
assert 100 <= words <= 150, words
assert len(SHORT) < 500, len(SHORT)

deck = Presentation(ROOT / "docs" / "reports" / "KASCO_Pitch.pptx")
notes = [s.notes_slide.notes_text_frame.text for s in deck.slides]
script_words = sum(len(n.split()) for n in notes)
script = "\n\n".join(f"**Slide {i}.** {n}" for i, n in enumerate(notes, 1))

(ROOT / "docs" / "SUBMISSION.md").write_text(
    f"""# KASCO submission content

## Submission title

{TITLE}

## Project materials

Live prototype: {LIVE}

GitHub repository: {REPO}

Technical report: {LIVE}reports/KASCO_Technical_Report.pdf

Presentation: {LIVE}reports/KASCO_Pitch.pptx

Cover image: {LIVE}reports/KASCO_Cover.jpg

## Summary ({words} words)

{SUMMARY}

## Short prototype description ({len(SHORT)} characters)

{SHORT}

## Three-minute pitch script ({script_words} words, about {script_words / 150 * 60:.0f} seconds at 150 words a minute)

{script}
""",
    encoding="utf-8",
)
print("summary words", words, "| short chars", len(SHORT), "| script words", script_words)
