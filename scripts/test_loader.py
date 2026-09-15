"""
Central FastF1 loading utilities.

Every analysis component should load sessions through here, not call
fastf1.get_session() directly - this is where the defensive handling
found during data scoping lives (see notebooks/00_data_scoping.ipynb
and scripts/scope_inspect_*.py for the evidence behind each check).

Known constraints baked in here:
- A driver's laps can be entirely marked inaccurate for a session
  (observed: 2023 Monza driver 22, 2023 Sao Paulo drivers 3/81).
  We log and drop rather than crash.
- IsAccurate must be filtered before any pace/degradation stats -
  SC/VSC/red-flag laps are included in raw .laps otherwise.
- Qualifying Q1/Q2/Q3 times live in session.results, not session.laps.
  session.laps for a Q session is every lap driven across all three
  segments, unsegmented - not useful for "best time per segment".
"""
from __future__ import annotations

import logging
from pathlib import Path

import fastf1
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"


def enable_cache(cache_dir: str | Path = DEFAULT_CACHE_DIR) -> None:
    """Enable FastF1's on-disk cache. Call once per process before loading sessions."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))


def load_session(year: int, gp: str, session_type: str):
    """
    Load a FastF1 session with telemetry, laps, and results.

    Parameters
    ----------
    year : e.g. 2024
    gp : event name or round, e.g. "Monza", "Italian Grand Prix", or round number
    session_type : "FP1", "FP2", "FP3", "Q", "R"

    Returns
    -------
    fastf1.core.Session (already .load()-ed)
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load()
    return session


def get_clean_laps(session, drop_inaccurate: bool = True) -> pd.DataFrame:
    """
    Return session.laps filtered to usable rows for pace/degradation analysis.

    Drops laps where IsAccurate is False (SC/VSC/red-flag/pit laps and other
    timing anomalies) when drop_inaccurate=True. Logs a warning per driver
    whose laps are entirely dropped, rather than silently returning an empty
    slice for that driver.

    Set drop_inaccurate=False if you need raw laps for a specific reason
    (e.g. inspecting pit stops, which live on PitInTime/PitOutTime and are
    unaffected by the IsAccurate flag).
    """
    laps = session.laps.copy()

    if not drop_inaccurate:
        return laps

    clean = laps[laps["IsAccurate"] == True]  # noqa: E712 (explicit bool compare - column is object/bool mix)

    for driver in laps["Driver"].unique():
        n_total = (laps["Driver"] == driver).sum()
        n_clean = (clean["Driver"] == driver).sum()
        if n_clean == 0 and n_total > 0 and n_total < 5:
            # Trivially few laps to begin with (DNS/retirement/data quirk) -
            # distinct from a driver who raced normally but got flagged out.
            logger.warning(
                "Driver %s: only %d lap(s) recorded this session and none "
                "accurate - likely a short/incomplete session for this "
                "driver (retirement, DNS, etc.), not a data quality issue.",
                driver, n_total,
            )
        elif n_clean == 0 and n_total > 0:
            logger.warning(
                "Driver %s: all %d laps marked inaccurate for this session - "
                "excluded entirely from clean laps.",
                driver, n_total,
            )
        elif n_clean < n_total * 0.5:
            logger.warning(
                "Driver %s: only %d/%d laps accurate (%.0f%%) - results for "
                "this driver may be less reliable.",
                driver, n_clean, n_total, 100 * n_clean / n_total,
            )

    return clean


def get_quali_results(session) -> pd.DataFrame:
    """
    Return session.results for a qualifying session, with Q1/Q2/Q3 best times.

    Nulls in Q2/Q3 are expected and meaningful (driver eliminated in an
    earlier segment) - do not fillna or drop these rows.
    """
    return session.results[
        ["Abbreviation", "TeamName", "Position", "Q1", "Q2", "Q3"]
    ].copy()


def get_race_results(session) -> pd.DataFrame:
    """Return session.results for a race session: grid vs finish, status, points."""
    return session.results[
        ["Abbreviation", "TeamName", "Position", "GridPosition", "Status", "Points"]
    ].copy()