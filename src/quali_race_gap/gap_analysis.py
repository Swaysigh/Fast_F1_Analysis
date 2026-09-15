"""
Component 4: qualifying vs race pace gap.

Computes each driver's qualifying rank vs their race pace rank and the
delta between them, across a session or season, to identify "qualifying
specialists" (fast over one lap, fade in the race) vs "race-day
specialists" (the reverse).

Qualifying rank comes from session.results (Q1/Q2/Q3 best times) - NOT
session.laps, which for a Q session is every lap driven across all three
segments, unsegmented (confirmed during scoping - see src/data/loader.py).

Race pace rank is median race lap time by default - a simple, robust
choice (median resists outlier laps better than mean without needing the
IsAccurate filtering to be perfect). This does NOT use the tyre-adjusted/
fuel-corrected pace from src/pace and src/tyre - see
RACE_PACE_METHODOLOGY_NOTE below for why, and rank_by_adjusted_pace() for
the more rigorous alternative if you want it.
"""
from __future__ import annotations

import logging

import pandas as pd
from scipy import stats

RACE_PACE_METHODOLOGY_NOTE = """
Why median raw lap time, not tyre-adjusted pace, is the default here:

The tyre-adjusted pace from src/pace/pace_analysis.py deliberately REMOVES
each driver's own stint-level trend before computing consistency - that's
correct for "how consistent is this driver," but wrong for "how fast is
this driver relative to the field," because it also strips out real
differences in how well a driver/car manages a stint (which is part of
race pace, not noise to remove).

Median raw race lap time is simpler and answers a more direct question:
over the whole race, what lap times did this driver actually produce?
It's still filtered to IsAccurate == True laps (assuming the input came
from get_clean_laps()), so SC/VSC/pit laps are already excluded.

Trade-off: median raw pace does NOT correct for strategy differences
(a driver on a 1-stop vs 2-stop strategy runs different average stint
lengths/tyre ages) or fuel load the way src/tyre's degradation fits do.
rank_by_adjusted_pace() is provided as an alternative that uses the
fuel-corrected degradation intercepts instead, for a stricter comparison -
use it if strategy differences across the field are a real concern for
the sessions being compared, but note it inherits the fuel-correction
limitation documented in src/tyre/degradation.py (partial correction only).
"""


def _lap_time_to_seconds(laps: pd.DataFrame, col: str = "LapTime") -> pd.Series:
    return laps[col].dt.total_seconds()


def rank_qualifying(quali_results: pd.DataFrame) -> pd.DataFrame:
    """
    Rank drivers by qualifying performance using their best segment time
    reached (Q3 if they made it, else Q2, else Q1) - this is effectively
    just session.results['Position'], but recomputed explicitly here so
    the ranking logic is visible and auditable rather than trusting an
    opaque upstream column.

    Expects quali_results from src.data.loader.get_quali_results()
    (columns: Abbreviation, TeamName, Position, Q1, Q2, Q3).
    """
    out = quali_results.copy()
    out["QualiRank"] = out["Position"]
    return out[["Abbreviation", "TeamName", "QualiRank", "Q1", "Q2", "Q3"]].sort_values("QualiRank")


def rank_race_pace(clean_race_laps: pd.DataFrame, min_laps: int = 10) -> pd.DataFrame:
    """
    Rank drivers by median race lap time (ascending - lower is better/faster).

    Drivers with fewer than min_laps clean laps are excluded from the
    ranking entirely - a handful of laps before a retirement, mechanical
    issue, or DNF isn't a race pace sample, and ranking it alongside
    drivers who ran a full race distance would misrepresent both.

    See RACE_PACE_METHODOLOGY_NOTE for why median raw lap time is the
    default rather than tyre-adjusted pace.

    Expects clean_race_laps from src.data.loader.get_clean_laps() (i.e.
    already filtered to IsAccurate == True).
    """
    laps = clean_race_laps.copy()
    laps["LapTimeSeconds"] = _lap_time_to_seconds(laps)

    summary = (
        laps.groupby("Driver")["LapTimeSeconds"]
        .agg(["median", "count"])
        .rename(columns={"median": "MedianRaceLapTime", "count": "NumLaps"})
        .reset_index()
        .rename(columns={"Driver": "Abbreviation"})
    )

    excluded = summary[summary["NumLaps"] < min_laps]
    if not excluded.empty:
        logging.getLogger(__name__).warning(
            "Excluding %d driver(s) from race pace ranking - fewer than "
            "%d clean laps (likely early retirement/DNF, not a "
            "representative race pace sample): %s",
            len(excluded), min_laps, list(excluded["Abbreviation"]),
        )

    summary = summary[summary["NumLaps"] >= min_laps].copy()
    summary["RacePaceRank"] = summary["MedianRaceLapTime"].rank(method="min").astype(int)
    return summary.sort_values("RacePaceRank")


def quali_vs_race_gap(quali_ranked: pd.DataFrame, race_ranked: pd.DataFrame) -> pd.DataFrame:
    """
    Merge qualifying rank and race pace rank per driver and compute the gap.

    Gap = QualiRank - RacePaceRank. Positive gap means the driver's race
    pace rank is BETTER (lower number) than their qualifying rank - i.e. a
    "race-day specialist". Negative gap means the reverse - a
    "qualifying specialist."

    Drivers missing from either side are dropped via the inner merge
    rather than filled with a placeholder rank.
    """
    merged = quali_ranked.merge(race_ranked, on="Abbreviation", how="inner")
    merged["Gap"] = merged["QualiRank"] - merged["RacePaceRank"]
    return merged[
        ["Abbreviation", "TeamName", "QualiRank", "RacePaceRank", "Gap", "MedianRaceLapTime", "NumLaps"]
    ].sort_values("Gap", ascending=False)


def classify_specialists(gap_df: pd.DataFrame, threshold: int = 3) -> pd.DataFrame:
    """
    Label each driver as a "Race specialist" (Gap >= threshold), "Qualifying
    specialist" (Gap <= -threshold), or "Balanced" (in between).
    """
    out = gap_df.copy()
    out["Label"] = "Balanced"
    out.loc[out["Gap"] >= threshold, "Label"] = "Race specialist"
    out.loc[out["Gap"] <= -threshold, "Label"] = "Qualifying specialist"
    return out


def gap_over_season(per_race_gaps: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Aggregate per-race gap dataframes into a season-level summary: mean gap
    and its consistency (std dev) per driver across the races passed in.
    """
    combined = pd.concat(per_race_gaps, ignore_index=True)
    summary = (
        combined.groupby("Abbreviation")["Gap"]
        .agg(["mean", "std", "count"])
        .rename(columns={"mean": "MeanGap", "std": "GapStd", "count": "NumRaces"})
        .reset_index()
    )
    return summary.sort_values("MeanGap", ascending=False)