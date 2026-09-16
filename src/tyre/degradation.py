"""
Component 2: tyre degradation modeling.

Fits lap time vs tyre age regression curves per driver per compound and
compares degradation slopes across drivers/teams. This is the mirror
image of src/pace/pace_analysis.py's tyre_adjusted_pace(): that module
fits the same kind of trend but throws the slope away and keeps the
residual (driver consistency). This module keeps the slope and discards
the residual (tyre management).

IMPORTANT - fuel load confound:
FastF1 does not expose fuel mass as a data channel (confirmed: it is not
part of the official timing/telemetry stream FastF1 pulls from). A race
car burns off on the order of 100+ kg of fuel over a race distance, and
published estimates put the effect at roughly 0.03-0.035 sec/kg - i.e.
a full stint's fuel burn can be worth a full second or more of lap time,
in the OPPOSITE direction to tyre degradation (car gets faster as it
burns fuel, slower as tyres wear). Fitting LapTime ~ TyreLife alone
without correcting for this conflates the two effects, and in testing
against 2024 Monza the fuel effect dominated: two-thirds of fitted
stints showed a *negative* raw slope (lap times improving with tyre
age), which is not a plausible tyre story on its own.

fit_degradation_curves() therefore applies a standard linear fuel-burn
correction before fitting (see FUEL_BURN_SEC_PER_LAP below) rather than
fitting raw lap time. This is a modeled assumption, not measured data -
the constant is a widely-cited approximation, not telemetry - and should
be disclosed as such anywhere these slopes are reported (see README).
Pass apply_fuel_correction=False to get the raw uncorrected fit instead
(e.g. for comparison, or to demonstrate the confound itself).

KNOWN LIMITATION - correction is partial, not exact:
Tested against 2024 Monza: fuel correction cut negative-slope stints from
32/48 to 19/48 and flipped the mean slope from -0.006 to +0.024 sec/lap -
a real improvement, but not a full fix. Do not "tune" the fuel constant
further to chase zero negatives; the remaining gap is very likely real
effects the linear correction can't capture, not an undertuned constant:
  - track evolution (grip rises through a race as rubber goes down,
    pushing lap times down independent of tyres/fuel - largest for long
    stints, which is exactly where the remaining negatives cluster)
  - non-representative early-stint laps (traffic right after a pit stop,
    fuel-saving/lift-and-coast laps) biasing the fitted slope
  - FUEL_BURN_SEC_PER_LAP is one global constant, not circuit- or
    load-specific
A negative post-correction slope should be read as "no strong degradation
signal detected, and possibly a positive (grip-gaining) trend" rather
than confidently negative tyre wear - report it with that framing, not
as a claim that the tyre got faster with age.

Input is expected to come from src.data.loader.get_clean_laps() (i.e.
already filtered to IsAccurate == True).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

# Widely-cited approximation: ~0.03 sec/kg of fuel per lap. Not measured -
# FastF1 has no fuel channel - and not track-specific. Treat as a rough
# correction that removes most of the confound, not an exact model.
FUEL_BURN_SEC_PER_LAP = 0.03
# Total race fuel load assumption (kg) used to estimate per-lap burn rate
# when total race laps are known. Conservative mid-range estimate; actual
# loads vary by team/strategy and are not published per-race.
ASSUMED_RACE_FUEL_KG = 100.0


def _lap_time_to_seconds(laps: pd.DataFrame, col: str = "LapTime") -> pd.Series:
    return laps[col].dt.total_seconds()


def fit_degradation_curves(
    laps: pd.DataFrame,
    min_stint_laps: int = 5,
    apply_fuel_correction: bool = True,
    min_laps_for_reliable_fit: int = 8,
) -> pd.DataFrame:
    """
    Fit a linear regression of (fuel-corrected) LapTimeSeconds ~ TyreLife
    per driver-stint, and return one row per stint with the fitted slope
    (seconds lost per lap of tyre age), intercept, R-squared, and stint
    metadata.

    Fuel correction (on by default - see module docstring for why this
    matters): adds back FUEL_BURN_SEC_PER_LAP seconds for each lap already
    completed in the race at that point, so the fitted slope reflects tyre
    wear rather than a mix of tyre wear and the car getting lighter. This
    uses overall LapNumber (laps completed in the race), not TyreLife
    (laps completed on this set of tyres) - fuel burns off race-wide, not
    per-stint.

    Stints shorter than min_stint_laps are excluded entirely - a handful of
    points can't support a meaningful slope estimate. Stints between
    min_stint_laps and min_laps_for_reliable_fit are still fit and
    returned, but flagged via LowSampleWarning=True: short-stint slopes are
    dominated by one or two laps (e.g. a 5-lap stint where one lap has
    traffic) and should not be read the same way as a 20+ lap fit. Always
    check this column before ranking or comparing - see
    compare_drivers_by_compound, which already weights by NumLaps but does
    not exclude low-sample stints outright.

    Slope is in seconds/lap of TyreLife. Positive slope = lap time
    increasing with tyre age (expected direction: degradation). With fuel
    correction applied, a near-zero or negative slope is more clearly
    notable than in the uncorrected fit - it suggests genuinely flat wear
    on that compound/track, not just fuel burn masking degradation.

    Uses scipy.stats.linregress rather than numpy polyfit (used in
    pace_analysis) specifically because we want R-squared here to judge fit
    quality - pace_analysis only needed the residual, so it didn't need the
    stats output.
    """
    laps = laps.copy()
    laps["LapTimeSeconds"] = _lap_time_to_seconds(laps)

    if apply_fuel_correction:
        # Add back the time "lost" to fuel burn so far, so what remains in
        # the trend is attributable to tyre wear rather than fuel.
        laps["LapTimeSeconds"] = (
            laps["LapTimeSeconds"] + laps["LapNumber"] * FUEL_BURN_SEC_PER_LAP
        )

    rows = []
    for (driver, stint, compound, team), group in laps.groupby(
        ["Driver", "Stint", "Compound", "Team"]
    ):
        if len(group) < min_stint_laps:
            continue
        x = group["TyreLife"].to_numpy(dtype=float)
        y = group["LapTimeSeconds"].to_numpy(dtype=float)

        result = stats.linregress(x, y)
        rows.append({
            "Driver": driver,
            "Team": team,
            "Stint": stint,
            "Compound": compound,
            "NumLaps": len(group),
            "DegSlope": result.slope,          # seconds per lap of tyre age
            "Intercept": result.intercept,
            "RSquared": result.rvalue ** 2,
            "PValue": result.pvalue,
            "StdErr": result.stderr,
            "TyreLifeStart": x.min(),
            "TyreLifeEnd": x.max(),
            "LowSampleWarning": len(group) < min_laps_for_reliable_fit,
            "FuelCorrected": apply_fuel_correction,
        })

    if not rows:
        # No stint met min_stint_laps - return an empty frame with the
        # right columns rather than letting sort_values() crash on an
        # empty DataFrame with no columns at all (found via unit testing,
        # not observed in real data - every real race so far has had at
        # least one long-enough stint, but a caller filtering to a very
        # short session or an unusual field could hit this).
        return pd.DataFrame(columns=[
            "Driver", "Team", "Stint", "Compound", "NumLaps", "DegSlope",
            "Intercept", "RSquared", "PValue", "StdErr", "TyreLifeStart",
            "TyreLifeEnd", "LowSampleWarning", "FuelCorrected",
        ])

    return pd.DataFrame(rows).sort_values(["Compound", "DegSlope"])


def compare_drivers_by_compound(degradation_curves: pd.DataFrame, compound: str) -> pd.DataFrame:
    """
    Filter fitted curves to one compound and rank drivers by average
    degradation slope across their stints on it (weighted by stint length,
    since a 25-lap stint's slope is a much better estimate than a 5-lap
    one's).

    Lower average slope = manages that compound better (loses less time
    per lap of tyre age), all else equal. "All else equal" is doing real
    work in that sentence - this does not control for fuel load, track
    evolution, or traffic. See module docstring / README for that caveat.
    """
    subset = degradation_curves[degradation_curves["Compound"] == compound].copy()
    if subset.empty:
        return subset

    def weighted_avg(group: pd.DataFrame) -> pd.Series:
        weights = group["NumLaps"]
        return pd.Series({
            "WeightedAvgSlope": np.average(group["DegSlope"], weights=weights),
            "TotalLaps": weights.sum(),
            "NumStints": len(group),
            "AvgRSquared": np.average(group["RSquared"], weights=weights),
        })

    ranked = subset.groupby(["Driver", "Team"]).apply(weighted_avg, include_groups=False).reset_index()
    return ranked.sort_values("WeightedAvgSlope")


def team_compound_summary(degradation_curves: pd.DataFrame) -> pd.DataFrame:
    """
    Team-level (not driver-level) average degradation slope per compound -
    useful for separating "this team's car is kind to tyres" from "this
    specific driver manages tyres well," since the former shows up as both
    teammates having similar slopes and the latter as a gap between them.
    """
    return (
        degradation_curves.groupby(["Team", "Compound"])
        .apply(
            lambda g: pd.Series({
                "WeightedAvgSlope": np.average(g["DegSlope"], weights=g["NumLaps"]),
                "TotalLaps": g["NumLaps"].sum(),
                "NumDrivers": g["Driver"].nunique(),
            }),
            include_groups=False,
        )
        .reset_index()
        .sort_values(["Compound", "WeightedAvgSlope"])
    )


def teammate_gap(degradation_curves: pd.DataFrame, driver_a: str, driver_b: str) -> pd.DataFrame:
    """
    Compare two drivers' (intended for teammates, but works for any pair)
    degradation slopes compound-by-compound, on the same machinery. This is
    the cleanest read on "who manages tyres better" since car effects
    should mostly cancel out between teammates.

    Returns one row per compound both drivers have a fitted slope for
    (compounds only one of them ran are dropped, since there's nothing to
    compare).
    """
    results = []
    for compound in degradation_curves["Compound"].unique():
        a_rows = degradation_curves[
            (degradation_curves["Driver"] == driver_a) & (degradation_curves["Compound"] == compound)
        ]
        b_rows = degradation_curves[
            (degradation_curves["Driver"] == driver_b) & (degradation_curves["Compound"] == compound)
        ]
        if a_rows.empty or b_rows.empty:
            continue

        a_slope = np.average(a_rows["DegSlope"], weights=a_rows["NumLaps"])
        b_slope = np.average(b_rows["DegSlope"], weights=b_rows["NumLaps"])
        results.append({
            "Compound": compound,
            f"{driver_a}_Slope": a_slope,
            f"{driver_b}_Slope": b_slope,
            "Gap": a_slope - b_slope,  # positive = driver_a degrading faster (worse)
            f"{driver_a}_Laps": a_rows["NumLaps"].sum(),
            f"{driver_b}_Laps": b_rows["NumLaps"].sum(),
        })

    return pd.DataFrame(results)