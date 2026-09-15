"""
Manual smoke test for src/pace/pace_analysis.py.
Run locally: python scripts/test_pace.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loader import enable_cache, load_session, get_clean_laps
from src.pace.pace_analysis import (
    tyre_adjusted_pace,
    consistency_by_stint,
    raw_pace_summary,
    pace_evolution,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

enable_cache()

print("=" * 60)
print("Loading 2024 Monza Race")
print("=" * 60)
session = load_session(2024, "Monza", "R")
clean = get_clean_laps(session)
print(f"Clean laps: {len(clean)}")

print("\n" + "=" * 60)
print("RAW PACE SUMMARY (top 10 by mean lap time)")
print("=" * 60)
raw_summary = raw_pace_summary(clean)
print(raw_summary.head(10))

print("\n" + "=" * 60)
print("TYRE-ADJUSTED PACE (spot check)")
print("=" * 60)
adjusted = tyre_adjusted_pace(clean)
print("Columns added:", [c for c in adjusted.columns if c not in clean.columns])
print("\nRows with NaN AdjustedPace (short stints, expected some):")
print(adjusted["AdjustedPace"].isna().sum(), "/", len(adjusted))
print("\nSample adjusted rows (LEC):")
print(
    adjusted[adjusted["Driver"] == "LEC"][
        ["LapNumber", "Stint", "TyreLife", "LapTimeSeconds", "AdjustedPace"]
    ].head(10)
)

print("\n" + "=" * 60)
print("CONSISTENCY BY STINT (most consistent first)")
print("=" * 60)
consistency = consistency_by_stint(adjusted)
print(consistency.head(15))
print("\nLeast consistent:")
print(consistency.tail(5))

print("\n" + "=" * 60)
print("PACE EVOLUTION - single driver lap by lap (VER)")
print("=" * 60)
evolution = pace_evolution(clean, "VER")
print(evolution.head(15))
print(f"\nTotal laps in evolution: {len(evolution)}")

print("\n" + "=" * 60)
print("SANITY CHECKS")
print("=" * 60)
# AdjustedPace should be roughly zero-mean per stint (it's a residual)
per_stint_mean = adjusted.dropna(subset=["AdjustedPace"]).groupby(["Driver", "Stint"])["AdjustedPace"].mean()
print("Max abs per-stint mean residual (should be ~0, floating point only):", per_stint_mean.abs().max())
assert per_stint_mean.abs().max() < 1e-6, "residuals should be ~zero-mean per stint by construction"
print("PASS: residuals are zero-mean per stint as expected")

print("\nALL TESTS COMPLETED")