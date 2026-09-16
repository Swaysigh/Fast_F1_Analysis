"""
Unit tests for src/quali_race_gap/gap_analysis.py.

test_driver_with_few_laps_excluded_from_ranking is the regression test
for the real bug found in testing: TSU had only 5 clean laps in the 2024
Monza race (an early retirement), and before the min_laps fix, this
produced a fake, misleading "Qualifying specialist" label purely from
having too little data to rank fairly - not from any real gap between
his qualifying and race performance.

Run: pytest tests/test_gap_analysis.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from src.quali_race_gap.gap_analysis import rank_race_pace, rank_qualifying, quali_vs_race_gap


def _make_fake_race_laps(driver_lap_times: dict[str, list[float]]) -> pd.DataFrame:
    """
    Build fake race laps for several drivers at once.
    driver_lap_times: {driver_code: [lap_time_seconds, ...]}
    """
    rows = []
    for driver, times in driver_lap_times.items():
        for t in times:
            rows.append({"Driver": driver, "LapTime": pd.Timedelta(seconds=t)})
    return pd.DataFrame(rows)


def test_driver_with_few_laps_excluded_from_ranking():
    """
    Regression test for the TSU bug: a driver with very few laps (e.g. an
    early retirement) should be excluded from the race pace ranking
    entirely, not ranked last based on an unrepresentative handful of laps.
    """
    laps = _make_fake_race_laps({
        "NORMAL_A": [85.0] * 40,          # full race distance, clean pace
        "NORMAL_B": [86.0] * 40,          # full race distance, slightly slower
        "RETIRED": [200.0, 201.0, 199.0, 202.0, 198.0],  # only 5 laps, wildly slow (simulating car trouble before retiring)
    })

    ranked = rank_race_pace(laps, min_laps=10)

    assert "RETIRED" not in ranked["Abbreviation"].values, (
        "driver with fewer than min_laps clean laps should be excluded entirely"
    )
    assert set(ranked["Abbreviation"]) == {"NORMAL_A", "NORMAL_B"}
    # NORMAL_A is faster, should rank 1st
    assert ranked[ranked["Abbreviation"] == "NORMAL_A"].iloc[0]["RacePaceRank"] == 1


def test_driver_with_enough_laps_is_ranked_normally():
    """Sanity check: min_laps only excludes genuinely low-sample drivers."""
    laps = _make_fake_race_laps({
        "A": [85.0] * 15,
        "B": [86.0] * 15,
    })
    ranked = rank_race_pace(laps, min_laps=10)
    assert set(ranked["Abbreviation"]) == {"A", "B"}


def test_quali_vs_race_gap_sign_convention():
    """
    Positive Gap should mean race pace rank is BETTER (numerically lower)
    than qualifying rank - i.e. a driver who out-performs their qualifying
    position once the race actually happens. This locks in the sign
    convention so it can't silently flip during a refactor.
    """
    quali = pd.DataFrame({
        "Abbreviation": ["A", "B"],
        "TeamName": ["TeamA", "TeamB"],
        "QualiRank": [5, 1],
        "Q1": [pd.Timedelta(seconds=80)] * 2,
        "Q2": [pd.Timedelta(seconds=79)] * 2,
        "Q3": [pd.Timedelta(seconds=78)] * 2,
    })
    race = pd.DataFrame({
        "Abbreviation": ["A", "B"],
        "MedianRaceLapTime": [85.0, 90.0],
        "NumLaps": [40, 40],
        "RacePaceRank": [1, 5],  # A: race pace much better than quali rank; B: much worse
    })

    gap = quali_vs_race_gap(quali, race)

    a_gap = gap[gap["Abbreviation"] == "A"].iloc[0]["Gap"]
    b_gap = gap[gap["Abbreviation"] == "B"].iloc[0]["Gap"]

    assert a_gap == 4   # QualiRank 5 - RacePaceRank 1 = 4 (race pace stronger)
    assert b_gap == -4  # QualiRank 1 - RacePaceRank 5 = -4 (qualifying stronger)