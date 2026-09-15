"""
Component 1: race pace evolution and consistency analysis.

Decomposes lap time into raw pace and tyre-age-adjusted pace, and
quantifies consistency via variance of the adjusted pace (not raw lap
time) - two drivers with similar mean pace can have very different
variance once tyre degradation is accounted for separately.

Input is expected to come from src.data.loader.get_clean_laps() (i.e.
already filtered to IsAccurate == True). Functions here do not
re-filter - garbage in, garbage out is intentional so this module
stays a pure transform over whatever laps it's given.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _lap_time_to_seconds(laps: pd.DataFrame, col: str = "LapTime") -> pd.Series:
    """Convert a pandas Timedelta lap-time column to float seconds."""
    return laps[col].dt.total_seconds()


def add_pace_seconds(laps: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of laps with a LapTimeSeconds float column added."""
    out = laps.copy()
    out["LapTimeSeconds"] = _lap_time_to_seconds(out)
    return out


def tyre_adjusted_pace(laps: pd.DataFrame, min_stint_laps: int = 4) -> pd.DataFrame:
    """
    Fit a per-driver-per-stint linear trend of LapTimeSeconds vs TyreLife and
    return laps with an added AdjustedPace column: the residual after
    removing that trend (i.e. pace with the tyre-age effect subtracted out).

    Stints shorter than min_stint_laps are left with AdjustedPace = NaN -
    not enough points to fit a meaningful trend, and a 2-3 point "fit" would
    just be noise dressed up as a slope.

    A positive AdjustedPace residual means the lap was slower than the
    stint's own degradation trend would predict; negative means faster.
    This isolates lap-to-lap driver variability from the (also
    driver-dependent, but different-natured) tyre management question,
    which is handled separately in src/tyre/.
    """
    laps = add_pace_seconds(laps)
    laps["AdjustedPace"] = np.nan

    for (driver, stint), group in laps.groupby(["Driver", "Stint"]):
        if len(group) < min_stint_laps:
            continue
        x = group["TyreLife"].to_numpy(dtype=float)
        y = group["LapTimeSeconds"].to_numpy(dtype=float)
        # Simple linear fit: LapTime ~ TyreLife. Degree-1 is deliberate here -
        # this is a local per-stint trend removal, not the degradation model
        # itself (that's src/tyre/, which compares slopes across compounds
        # and is allowed to consider higher-order fits).
        slope, intercept = np.polyfit(x, y, 1)
        predicted = slope * x + intercept
        residual = y - predicted
        laps.loc[group.index, "AdjustedPace"] = residual

    return laps


def consistency_by_stint(laps_with_adjusted: pd.DataFrame, min_laps_for_ranking: int = 8) -> pd.DataFrame:
    """
    Per driver-per-stint consistency: std dev of AdjustedPace (residual pace
    after tyre-age trend removed). Lower = more consistent under pressure,
    independent of whether their tyres were also degrading.

    Stints with fewer than min_laps_for_ranking laps are still returned but
    flagged via a LowSampleWarning column - std dev on a handful of laps is
    dominated by one or two outlier laps and shouldn't be read the same way
    as a 20+ lap stint's std dev. Filter these out explicitly if you want a
    ranking that's only comparing like-for-like sample sizes.

    Requires laps_with_adjusted to already have an AdjustedPace column
    (i.e. laps that went through tyre_adjusted_pace() first).
    """
    grouped = (
        laps_with_adjusted.dropna(subset=["AdjustedPace"])
        .groupby(["Driver", "Stint", "Compound"])["AdjustedPace"]
        .agg(["std", "mean", "count"])
        .rename(columns={"std": "AdjustedPaceStd", "mean": "AdjustedPaceMean", "count": "NumLaps"})
        .reset_index()
    )
    grouped["LowSampleWarning"] = grouped["NumLaps"] < min_laps_for_ranking
    return grouped.sort_values("AdjustedPaceStd")


def raw_pace_summary(laps: pd.DataFrame) -> pd.DataFrame:
    """
    Per-driver raw pace summary across the whole session: mean, median, std,
    min lap time. This is the "before adjustment" baseline - useful for
    sanity-checking against consistency_by_stint(), not a replacement for it.
    """
    laps = add_pace_seconds(laps)
    return (
        laps.groupby("Driver")["LapTimeSeconds"]
        .agg(["mean", "median", "std", "min", "count"])
        .rename(columns={
            "mean": "MeanLapTime",
            "median": "MedianLapTime",
            "std": "LapTimeStd",
            "min": "FastestLap",
            "count": "NumLaps",
        })
        .sort_values("MeanLapTime")
    )


def pace_evolution(laps: pd.DataFrame, driver: str) -> pd.DataFrame:
    """
    Lap-by-lap pace evolution for a single driver across the race: raw lap
    time and tyre-adjusted pace side by side, ordered by LapNumber. Intended
    for plotting (lap number on x-axis, both series on y).
    """
    laps = tyre_adjusted_pace(laps)
    driver_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")
    return driver_laps[
        ["LapNumber", "Stint", "Compound", "TyreLife", "LapTimeSeconds", "AdjustedPace"]
    ].reset_index(drop=True)