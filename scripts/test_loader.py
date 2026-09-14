"""
Manual smoke test for src/data/loader.py.
Run locally: python scripts/test_loader.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loader import (
    enable_cache,
    load_session,
    get_clean_laps,
    get_quali_results,
    get_race_results,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

enable_cache()

print("=" * 60)
print("TEST 1: Clean race (2024 Monza) - baseline sanity check")
print("=" * 60)
session = load_session(2024, "Monza", "R")
raw = session.laps
clean = get_clean_laps(session)
print(f"Raw laps: {len(raw)}, Clean (IsAccurate) laps: {len(clean)}")
assert len(clean) <= len(raw), "clean should never exceed raw"
assert clean["IsAccurate"].all(), "clean should only contain IsAccurate==True"
print("PASS: clean subset of raw, all IsAccurate==True")

print("\n" + "=" * 60)
print("TEST 2: Edge case (2023 Sao Paulo) - expect driver warnings")
print("=" * 60)
print("Watch for WARNING lines below re: driver 22 / drivers 3,81")
wet_session = load_session(2023, "Brazil", "R")
wet_clean = get_clean_laps(wet_session)
print(f"Raw: {len(wet_session.laps)}, Clean: {len(wet_clean)}")

print("\n" + "=" * 60)
print("TEST 3: Qualifying results (2024 Monza)")
print("=" * 60)
q_session = load_session(2024, "Monza", "Q")
q_results = get_quali_results(q_session)
print(q_results.head(10))
print("\nExpected nulls (Q2/Q3 = eliminated earlier):")
print(q_results[["Q1", "Q2", "Q3"]].isnull().sum())

print("\n" + "=" * 60)
print("TEST 4: Race results (2024 Monza)")
print("=" * 60)
r_results = get_race_results(session)
print(r_results.head(10))

print("\nALL TESTS COMPLETED - review warnings above for correctness")