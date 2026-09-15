"""
Component 5: strategy outcome analysis.

SCOPE NOTE (read this first):
This module does NOT simulate a full alternative race strategy (i.e. it
does not answer "what if this driver had pitted 5 laps later, accounting
for traffic, safety cars, and every rival's reaction"). That would need
race-wide gap/traffic simulation this project doesn't have data for.

What it DOES do, which is answerable with FastF1 data alone: score the
undercut/overcut mechanism against one specific rival. An undercut works
by pitting before a rival and using the fresh-tyre pace advantage to
jump them once they also pit; an overcut works by staying out longer and
relying on track position + tyre life to hold them off. Both are
fundamentally about a track-position swap around a pit stop relative to
ONE other car, which we CAN measure directly from lap position data.

Given a driver and a specific rival, this module reports:
- who pitted first, and how many laps apart
- track position before/after both have pitted
- whether the strategy "worked" (position gained relative to that rival)
This is a real, defensible measurement - it's just narrower than "who had
the best strategy in the whole race," which isn't answerable from this
data source alone. Say so explicitly in any writeup - don't let the
scoring here get read as more than it is.

Input: clean race laps from src.data.loader.get_clean_laps(). Position
data comes from the Position column on laps (each lap's classified
running order), not the separately-fetched telemetry position stream.
"""
from __future__ import annotations

import pandas as pd


def get_pit_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """
    Extract one row per pit stop: driver, the lap they pitted on, and the
    compound they came out on.

    A pit stop is identified by a non-null PitInTime on a lap - this is
    the lap during which the driver entered the pits. The lap immediately
    after (same Stint + 1, TyreLife resets to ~1) is when they're back on
    a fresh/different tyre.
    """
    pit_laps = laps[laps["PitInTime"].notna()][
        ["Driver", "LapNumber", "Stint", "Compound", "Position"]
    ].copy()
    pit_laps = pit_laps.rename(columns={"LapNumber": "PitLap", "Position": "PositionAtPit"})
    return pit_laps.sort_values(["Driver", "PitLap"])


def compare_strategy_vs_rival(
    laps: pd.DataFrame, driver: str, rival: str
) -> pd.DataFrame:
    """
    For every pit stop either driver takes, compare track position between
    the two around that pit window: position on the lap before the pit,
    and position a fixed number of laps after both drivers have made their
    next stop (or end of race, whichever comes first).

    Returns one row per pit event (from either driver) with:
    - who pitted, on what lap
    - each driver's position just before that pit lap
    - each driver's position ~3 laps after (once the pit-lane time itself
      has washed out of the position data)
    - PositionSwing: negative means `driver` gained positions on `rival`
      after this pit event, positive means `driver` lost positions

    This only reports what happened - it does not judge "was this the
    right call," since that depends on information (tyre life remaining,
    what rivals further back were doing, weather) outside this comparison.
    Use the PositionSwing sign/magnitude as one input to that judgment,
    not the whole answer.

    INTERPRETATION CAVEAT - pit-stop shuffles: a driver can briefly show
    Position == 1 (or any unusually good position) simply because the
    cars actually ahead of them are mid-pit-stop on that lap, not because
    they're genuinely leading on pace. Verified against 2024 Monza: PIA
    led laps 1-16 legitimately, then SAI inherited the lead for laps
    17-18 purely because PIA had just pitted - a real, common effect, not
    a data error, but it means a large PositionSwing right at a rival's
    own pit lap can partly reflect this shuffle rather than pure strategy
    skill. When reporting a striking swing, check whether it lines up
    with a rival's own pit window before reading it as skill.
    """
    driver_laps = laps[laps["Driver"] == driver].set_index("LapNumber")
    rival_laps = laps[laps["Driver"] == rival].set_index("LapNumber")

    pit_events = laps[
        (laps["Driver"].isin([driver, rival])) & (laps["PitInTime"].notna())
    ][["Driver", "LapNumber"]].sort_values("LapNumber")

    rows = []
    for _, event in pit_events.iterrows():
        pit_lap = event["LapNumber"]
        who_pitted = event["Driver"]

        before_lap = pit_lap - 1
        after_lap = pit_lap + 3  # a few laps out, past the immediate pit-lane time loss

        pos_driver_before = driver_laps["Position"].get(before_lap)
        pos_rival_before = rival_laps["Position"].get(before_lap)
        pos_driver_after = driver_laps["Position"].get(after_lap)
        pos_rival_after = rival_laps["Position"].get(after_lap)

        if None in (pos_driver_before, pos_rival_before, pos_driver_after, pos_rival_after) or any(
            pd.isna(v) for v in [pos_driver_before, pos_rival_before, pos_driver_after, pos_rival_after]
        ):
            # Missing data around this event (e.g. too close to race end,
            # or one driver retired) - skip rather than report a
            # misleading partial comparison.
            continue

        gap_before = pos_driver_before - pos_rival_before  # positive = driver behind rival
        gap_after = pos_driver_after - pos_rival_after

        rows.append({
            "PitLap": pit_lap,
            "WhoPitted": who_pitted,
            f"{driver}_PosBefore": pos_driver_before,
            f"{rival}_PosBefore": pos_rival_before,
            f"{driver}_PosAfter": pos_driver_after,
            f"{rival}_PosAfter": pos_rival_after,
            # Negative = driver's position relative to rival improved
            # (gained positions/closed or reversed the gap) after this pit event.
            "PositionSwing": gap_after - gap_before,
        })

    return pd.DataFrame(rows)


def undercut_success_rate(pit_laps: pd.DataFrame, laps: pd.DataFrame, position_window: int = 3) -> pd.DataFrame:
    """
    For every pair of drivers who pitted within position_window laps of
    each other (a plausible undercut/overcut situation - pitting far apart
    in time isn't really an undercut attempt on that specific rival), score
    whether the driver who pitted FIRST gained track position on the one
    who pitted SECOND.

    This is a broader, automated sweep version of compare_strategy_vs_rival
    - use that function for a specific pair you already want to inspect in
    detail, use this one to scan a whole race for undercut attempts worth
    looking at.

    Returns one row per candidate undercut attempt with an UndercutWorked
    boolean (True if the earlier-pitting driver ended up ahead of the
    later-pitting one a few laps later, having been behind or level
    before either pitted).
    """
    results = []
    pit_laps_sorted = pit_laps.sort_values("PitLap")

    for i, row_a in pit_laps_sorted.iterrows():
        for j, row_b in pit_laps_sorted.iterrows():
            if row_a["Driver"] >= row_b["Driver"]:
                continue  # avoid duplicate/self pairs (alphabetical dedup, arbitrary but consistent)
            if abs(row_a["PitLap"] - row_b["PitLap"]) > position_window:
                continue  # pitted too far apart to be a meaningful undercut attempt on each other

            earlier, later = (
                (row_a, row_b) if row_a["PitLap"] <= row_b["PitLap"] else (row_b, row_a)
            )

            comparison = compare_strategy_vs_rival(laps, earlier["Driver"], later["Driver"])
            if comparison.empty:
                continue

            first_event = comparison.iloc[0]
            was_behind_or_level = (
                first_event[f"{earlier['Driver']}_PosBefore"] >= first_event[f"{later['Driver']}_PosBefore"]
            )
            is_ahead_after = (
                first_event[f"{earlier['Driver']}_PosAfter"] < first_event[f"{later['Driver']}_PosAfter"]
            )

            results.append({
                "EarlierPitDriver": earlier["Driver"],
                "EarlierPitLap": earlier["PitLap"],
                "LaterPitDriver": later["Driver"],
                "LaterPitLap": later["PitLap"],
                "WasBehindOrLevelBefore": was_behind_or_level,
                "IsAheadAfter": is_ahead_after,
                "UndercutWorked": was_behind_or_level and is_ahead_after,
            })

    return pd.DataFrame(results)