"""
Unit tests for src/pace/pace_analysis.py.

Uses small, hand-built fake DataFrames with known-in-advance correct
answers - no FastF1, no network, runs in well under a second. This is
different from scripts/test_pace.py (a smoke test against real race
data that a human reads and judges); these tests assert exact expected
values so they can catch a regression automatically, forever, without
anyone re-reading printed output.

Run: pytest tests/test_pace_analysis.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from src.pace.pace_analysis import tyre_adjusted_pace, consistency_by_stint


def _make_fake_laps(lap_times_seconds: list[float], driver: str = "TST", stint: int = 1, compound: str = "MEDIUM") -> pd.DataFrame:
    """
    Build a minimal fake laps dataframe with just the columns
    tyre_adjusted_pace/consistency_by_stint actually need. TyreLife
    counts up from 1, one lap per entry in lap_times_seconds.
    """
    n = len(lap_times_seconds)
    return pd.DataFrame({
        "Driver": [driver] * n,
        "Stint": [stint] * n,
        "Compound": [compound] * n,
        "TyreLife": list(range(1, n + 1)),
        "LapTime": [pd.Timedelta(seconds=t) for t in lap_times_seconds],
    })


def test_adjusted_pace_residuals_are_zero_mean_per_stint():
    """
    Regression guard for the assertion we manually verified in
    scripts/test_pace.py: AdjustedPace is a residual from a per-stint
    linear fit, so it MUST average to ~zero within each stint - that's
    a mathematical property of least-squares fitting, not a coincidence
    of the real data. If this ever fails, the fitting logic itself broke.
    """
    # A stint with an obvious upward (degrading) trend plus noise.
    laps = _make_fake_laps([85.0, 85.2, 85.1, 85.4, 85.6, 85.5, 85.8, 86.0])
    result = tyre_adjusted_pace(laps)

    mean_residual = result["AdjustedPace"].mean()
    assert abs(mean_residual) < 1e-9, (
        f"expected ~zero mean residual per stint, got {mean_residual}"
    )


def test_short_stints_get_nan_adjusted_pace():
    """
    Stints shorter than min_stint_laps (default 4) should not get a
    fitted AdjustedPace at all - a 2-3 point fit is noise, not a trend,
    and reporting one would be misleading (this was a deliberate design
    decision, not just an edge case - see module docstring).
    """
    laps = _make_fake_laps([85.0, 85.2])  # only 2 laps
    result = tyre_adjusted_pace(laps)
    assert result["AdjustedPace"].isna().all()


def test_low_sample_stint_is_flagged_in_consistency_ranking():
    """
    Regression guard for the TSU bug found in testing (2024 Monza,
    scripts/test_tyre.py and test_gap.py): a stint with very few laps
    can produce an extreme, unreliable statistic that looks the same as
    a genuinely reliable one unless explicitly flagged.
    consistency_by_stint's LowSampleWarning column exists specifically
    so a 5-lap stint doesn't get silently ranked alongside a 40-lap one.
    """
    short_stint = _make_fake_laps(
        [85.0, 86.5, 84.0, 87.0, 83.5], driver="A", stint=1
    )  # 5 laps, high variance - deliberately noisy
    long_stint = _make_fake_laps(
        [85.0, 85.1, 85.2, 85.3, 85.4, 85.5, 85.6, 85.7, 85.8, 85.9], driver="B", stint=1
    )  # 10 laps, smooth trend

    combined = pd.concat([short_stint, long_stint], ignore_index=True)
    adjusted = tyre_adjusted_pace(combined)
    consistency = consistency_by_stint(adjusted, min_laps_for_ranking=8)

    driver_a_row = consistency[consistency["Driver"] == "A"].iloc[0]
    driver_b_row = consistency[consistency["Driver"] == "B"].iloc[0]

    assert driver_a_row["LowSampleWarning"] == True  # noqa: E712 - explicit bool check is clearer here
    assert driver_b_row["LowSampleWarning"] == False  # noqa: E712


def test_consistency_ranking_sorted_ascending_by_std():
    """
    The most consistent (lowest std dev) stint should always sort first -
    that's the entire point of the ranking, so a test that would catch an
    accidental sort-order flip is cheap insurance.
    """
    smooth = _make_fake_laps([85.0, 85.1, 85.2, 85.3, 85.4, 85.5, 85.6, 85.7], driver="SMOOTH", stint=1)
    noisy = _make_fake_laps([85.0, 87.0, 83.0, 88.0, 82.0, 89.0, 81.0, 90.0], driver="NOISY", stint=1)

    combined = pd.concat([smooth, noisy], ignore_index=True)
    adjusted = tyre_adjusted_pace(combined)
    consistency = consistency_by_stint(adjusted)

    assert consistency.iloc[0]["Driver"] == "SMOOTH"
    assert consistency.iloc[-1]["Driver"] == "NOISY"