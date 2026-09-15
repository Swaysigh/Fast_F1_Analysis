"""
Manual smoke test for src/strategy/strategy_analysis.py.
Run locally: python scripts/test_strategy.py

IMPORTANT: this module intentionally uses RAW laps (session.laps), not
get_clean_laps() - pit-in/pit-out laps are exactly the rows IsAccurate
filtering tends to drop (they're slower, anomalous laps by nature), but
they're the rows this module actually needs.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loader import enable_cache, load_session
from src.strategy.strategy_analysis import (
    get_pit_laps,
    compare_strategy_vs_rival,
    undercut_success_rate,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

enable_cache()

print("=" * 60)
print("Loading 2024 Monza Race (RAW laps - see module docstring for why)")
print("=" * 60)
session = load_session(2024, "Monza", "R")
raw_laps = session.laps
print(f"Raw laps: {len(raw_laps)}")

print("\n" + "=" * 60)
print("PIT STOPS")
print("=" * 60)
pit_laps = get_pit_laps(raw_laps)
print(f"Total pit stops found: {len(pit_laps)}")
print(pit_laps.head(15))

print(f"\nPit stops per driver (sanity - most drivers should have 1-3):")
print(pit_laps.groupby("Driver").size().sort_values(ascending=False))

print("\n" + "=" * 60)
print("SPECIFIC RIVAL COMPARISON: LEC vs SAI (Ferrari teammates)")
print("=" * 60)
comparison = compare_strategy_vs_rival(raw_laps, "LEC", "SAI")
print(comparison)

print("\n" + "=" * 60)
print("SPECIFIC RIVAL COMPARISON: NOR vs PIA (McLaren teammates)")
print("=" * 60)
comparison2 = compare_strategy_vs_rival(raw_laps, "NOR", "PIA")
print(comparison2)

print("\n" + "=" * 60)
print("UNDERCUT SWEEP (pit stops within 3 laps of each other)")
print("=" * 60)
sweep = undercut_success_rate(pit_laps, raw_laps, position_window=3)
print(f"Candidate undercut situations found: {len(sweep)}")
print(sweep)

if not sweep.empty:
    print(f"\nUndercut worked: {sweep['UndercutWorked'].sum()} / {len(sweep)}")

print("\n" + "=" * 60)
print("SANITY CHECKS")
print("=" * 60)
assert len(pit_laps) > 0, "should find at least some pit stops in a race"
# Every driver should have pitted at least once in a normal dry/mixed race
# (barring an unusual zero-stop strategy, which would itself be notable)
drivers_with_no_pit = set(raw_laps["Driver"].unique()) - set(pit_laps["Driver"].unique())
print(f"Drivers with zero recorded pit stops: {drivers_with_no_pit if drivers_with_no_pit else 'none'}")
print("(Non-empty here isn't necessarily wrong - could be a retirement before their stop - but worth a look)")

print("\nALL TESTS COMPLETED")