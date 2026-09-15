"""
Manual smoke test for src/quali_race_gap/gap_analysis.py.
Run locally: python scripts/test_gap.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.data.loader import enable_cache, load_session, get_clean_laps, get_quali_results
from src.quali_race_gap.gap_analysis import (
    rank_qualifying,
    rank_race_pace,
    quali_vs_race_gap,
    classify_specialists,
    gap_over_season,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

enable_cache()


def build_gap_for_event(year: int, event: str) -> pd.DataFrame:
    q_session = load_session(year, event, "Q")
    quali_results = get_quali_results(q_session)
    quali_ranked = rank_qualifying(quali_results)

    r_session = load_session(year, event, "R")
    clean_laps = get_clean_laps(r_session)
    race_ranked = rank_race_pace(clean_laps)

    return quali_vs_race_gap(quali_ranked, race_ranked)


print("=" * 60)
print("2024 MONZA: qualifying rank")
print("=" * 60)
q_session = load_session(2024, "Monza", "Q")
quali_results = get_quali_results(q_session)
quali_ranked = rank_qualifying(quali_results)
print(quali_ranked.head(10))

print("\n" + "=" * 60)
print("2024 MONZA: race pace rank")
print("=" * 60)
r_session = load_session(2024, "Monza", "R")
clean_laps = get_clean_laps(r_session)
race_ranked = rank_race_pace(clean_laps)
print(race_ranked.head(10))

print("\n" + "=" * 60)
print("2024 MONZA: quali vs race gap (positive = race specialist)")
print("=" * 60)
gap = quali_vs_race_gap(quali_ranked, race_ranked)
print(gap)

print(f"\nDrivers matched: {len(gap)} (expect close to 20, but drivers with <10 clean "
      f"laps - retirements/DNFs - are now correctly excluded from race pace ranking, "
      f"so counts a bit below 20 are expected and correct, not a bug)")

print("\n" + "=" * 60)
print("CLASSIFIED SPECIALISTS (threshold=3)")
print("=" * 60)
classified = classify_specialists(gap, threshold=3)
print(classified[["Abbreviation", "QualiRank", "RacePaceRank", "Gap", "Label"]])
print("\nLabel counts:")
print(classified["Label"].value_counts())

print("\n" + "=" * 60)
print("SEASON AGGREGATION (Monza + a second race)")
print("=" * 60)
print("Building gap for a second event to test aggregation...")
gap_2 = build_gap_for_event(2024, "Spa")

season_summary = gap_over_season([gap, gap_2])
print(season_summary)

print("\n" + "=" * 60)
print("SANITY CHECKS")
print("=" * 60)
# A driver who qualified P1 and had the fastest race pace should have Gap == 0
assert gap["RacePaceRank"].min() == 1, "someone should be ranked 1st in race pace"
assert gap["QualiRank"].min() == 1, "someone should be ranked 1st in qualifying"
print("PASS: rank columns well-formed (min rank == 1 on both sides)")

# Gap sign check: manually verify one row makes sense
worst_quali_best_race = gap.sort_values("Gap", ascending=False).iloc[0]
print(f"\nBiggest 'race specialist' gap: {worst_quali_best_race['Abbreviation']} "
      f"(Quali P{worst_quali_best_race['QualiRank']:.0f} -> Race pace P{worst_quali_best_race['RacePaceRank']:.0f})")

print("\nALL TESTS COMPLETED")