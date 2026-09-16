"""
Unit tests for src/tyre/degradation.py.

The most important test here (test_fuel_correction_reduces_confound)
directly encodes the bug we found and fixed in testing: raw lap time
mixes a real tyre-degradation trend with a fuel-burn trend running in
the OPPOSITE direction, and without correction the fuel effect can
dominate and produce a negative "degradation" slope that isn't really
about tyres at all. This test builds laps with a KNOWN, made-up
degradation rate and a KNOWN fuel effect, so we can assert the
correction moves the fitted slope in exactly the expected direction and
by roughly the expected amount - not just "the code runs."

Run: pytest tests/test_degradation.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from src.tyre.degradation import fit_degradation_curves, FUEL_BURN_SEC_PER_LAP


def _make_fake_stint_laps(
    n_laps: int,
    true_degradation_per_lap: float,
    fuel_effect_per_lap: float,
    base_time: float = 85.0,
    driver: str = "TST",
    team: str = "TestTeam",
    stint: int = 1,
    compound: str = "HARD",
    start_lap_number: int = 1,
) -> pd.DataFrame:
    """
    Build fake laps where the TRUE tyre degradation rate and TRUE fuel
    effect are both known exactly (we constructed them), so we can check
    whether fit_degradation_curves recovers something close to the true
    degradation rate once fuel is corrected for - not just an arbitrary
    number.

    LapTime for lap i (TyreLife = i) is built as:
        base_time + true_degradation_per_lap * TyreLife - fuel_effect_per_lap * LapNumber
    i.e. tyres genuinely get slower with age (positive contribution), and
    the car genuinely gets faster as raw race laps tick by from fuel burn
    (negative contribution) - mirroring the real confound.
    """
    rows = []
    for i in range(n_laps):
        tyre_life = i + 1
        lap_number = start_lap_number + i
        lap_time = (
            base_time
            + true_degradation_per_lap * tyre_life
            - fuel_effect_per_lap * lap_number
        )
        rows.append({
            "Driver": driver,
            "Team": team,
            "Stint": stint,
            "Compound": compound,
            "TyreLife": tyre_life,
            "LapNumber": lap_number,
            "LapTime": pd.Timedelta(seconds=lap_time),
        })
    return pd.DataFrame(rows)


def test_fuel_correction_reduces_confound():
    """
    This is the regression test for the actual bug: build a stint with a
    real, small positive degradation trend, but a LARGER fuel effect
    working against it (mirroring what we saw in the 2024 Monza data,
    where fuel dominated and produced misleadingly negative raw slopes).

    Assert three things:
    1. The UNCORRECTED fit's slope is negative (reproduces the bug)
    2. The CORRECTED fit's slope is positive (matches the true
       degradation direction we built into the fake data)
    3. The corrected slope is reasonably close to the true value we
       constructed, not just "some positive number"
    """
    true_degradation = 0.02   # seconds/lap - tyres genuinely degrading, slowly
    fuel_effect = 0.03        # matches FUEL_BURN_SEC_PER_LAP - stronger than degradation
    laps = _make_fake_stint_laps(
        n_laps=20,
        true_degradation_per_lap=true_degradation,
        fuel_effect_per_lap=fuel_effect,
    )

    raw_curves = fit_degradation_curves(laps, apply_fuel_correction=False)
    corrected_curves = fit_degradation_curves(laps, apply_fuel_correction=True)

    assert len(raw_curves) == 1
    assert len(corrected_curves) == 1

    raw_slope = raw_curves.iloc[0]["DegSlope"]
    corrected_slope = corrected_curves.iloc[0]["DegSlope"]

    # Reproduces the bug: without correction, fuel dominates and the fit
    # shows lap times IMPROVING with tyre age (negative slope) even though
    # we built in real, positive degradation.
    assert raw_slope < 0, f"expected raw slope to be masked negative by fuel, got {raw_slope}"

    # The fix: with correction, the recovered slope should be positive and
    # close to the true value we constructed the fake data with.
    assert corrected_slope > 0, f"expected corrected slope to be positive, got {corrected_slope}"
    assert corrected_slope == pytest.approx(true_degradation, abs=0.005), (
        f"expected corrected slope near {true_degradation}, got {corrected_slope}"
    )


def test_low_sample_stint_is_flagged():
    """
    Regression guard for the second bug found in testing: TSU's 5-lap
    stint produced a slope over 10x larger than the rest of the field
    (2024 Monza HARD compound) purely from having too few points to fit
    reliably. LowSampleWarning exists to flag stints below
    min_laps_for_reliable_fit so they aren't silently treated the same
    as a full-length stint.
    """
    short_stint = _make_fake_stint_laps(n_laps=5, true_degradation_per_lap=0.02, fuel_effect_per_lap=0.03, driver="SHORT")
    long_stint = _make_fake_stint_laps(n_laps=20, true_degradation_per_lap=0.02, fuel_effect_per_lap=0.03, driver="LONG")

    combined = pd.concat([short_stint, long_stint], ignore_index=True)
    curves = fit_degradation_curves(combined, min_stint_laps=5, min_laps_for_reliable_fit=8)

    short_row = curves[curves["Driver"] == "SHORT"].iloc[0]
    long_row = curves[curves["Driver"] == "LONG"].iloc[0]

    assert short_row["LowSampleWarning"] == True  # noqa: E712
    assert long_row["LowSampleWarning"] == False  # noqa: E712


def test_stints_below_min_stint_laps_are_excluded_entirely():
    """
    A 3-lap stint (below the default min_stint_laps=5) should not appear
    in the output at all - not flagged, just absent - since there aren't
    even enough points to attempt a meaningful linear fit.
    """
    tiny_stint = _make_fake_stint_laps(n_laps=3, true_degradation_per_lap=0.02, fuel_effect_per_lap=0.03)
    curves = fit_degradation_curves(tiny_stint)
    assert curves.empty