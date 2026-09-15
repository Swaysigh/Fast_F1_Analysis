"""
Manual smoke test for src/tyre/degradation.py.
Run locally: python scripts/test_tyre.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loader import enable_cache, load_session, get_clean_laps
from src.tyre.degradation import (
    fit_degradation_curves,
    compare_drivers_by_compound,
    team_compound_summary,
    teammate_gap,
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
print("DEGRADATION CURVES (all driver-stints, sorted by compound/slope)")
print("=" * 60)
curves = fit_degradation_curves(clean)
print(f"Total fitted stints: {len(curves)}")
print(curves[["Driver", "Team", "Stint", "Compound", "NumLaps", "DegSlope", "RSquared", "LowSampleWarning"]].head(15))

print("\nDegSlope sanity range (seconds/lap - expect roughly 0 to ~0.3 for most, fuel-corrected):")
print(curves["DegSlope"].describe())

print("\nAny negative slopes (faster as tyre ages, even after fuel correction)?")
neg = curves[curves["DegSlope"] < 0]
print(f"{len(neg)} / {len(curves)} stints")
print(neg[["Driver", "Stint", "Compound", "NumLaps", "DegSlope", "RSquared", "LowSampleWarning"]])

print("\n" + "-" * 60)
print("COMPARISON: fuel-corrected vs raw (uncorrected) - did the fix work?")
print("-" * 60)
raw_curves = fit_degradation_curves(clean, apply_fuel_correction=False)
print(f"Raw:       {(raw_curves['DegSlope'] < 0).sum()} / {len(raw_curves)} negative slopes")
print(f"Corrected: {(curves['DegSlope'] < 0).sum()} / {len(curves)} negative slopes")
print(f"Raw mean slope:       {raw_curves['DegSlope'].mean():.4f} sec/lap")
print(f"Corrected mean slope: {curves['DegSlope'].mean():.4f} sec/lap")

print("\nLow-sample stints flagged (NumLaps < 8):")
print(curves[curves["LowSampleWarning"]][["Driver", "Stint", "Compound", "NumLaps", "DegSlope"]])

print("\n" + "=" * 60)
print("COMPARE DRIVERS ON MEDIUM COMPOUND")
print("=" * 60)
medium_ranked = compare_drivers_by_compound(curves, "MEDIUM")
print(medium_ranked)

print("\n" + "=" * 60)
print("COMPARE DRIVERS ON HARD COMPOUND")
print("=" * 60)
hard_ranked = compare_drivers_by_compound(curves, "HARD")
print(hard_ranked)

print("\n" + "=" * 60)
print("TEAM-LEVEL SUMMARY BY COMPOUND")
print("=" * 60)
team_summary = team_compound_summary(curves)
print(team_summary)

print("\n" + "=" * 60)
print("TEAMMATE GAP: LEC vs SAI (2024 Ferrari)")
print("=" * 60)
gap = teammate_gap(curves, "LEC", "SAI")
print(gap)

print("\n" + "=" * 60)
print("TEAMMATE GAP: NOR vs PIA (2024 McLaren)")
print("=" * 60)
gap2 = teammate_gap(curves, "NOR", "PIA")
print(gap2)

print("\nALL TESTS COMPLETED - review DegSlope range and any negatives above for plausibility")