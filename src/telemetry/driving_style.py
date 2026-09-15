"""
Component 3: telemetry-based driving style comparison.

Compares two drivers' speed/throttle/brake traces on a common lap,
aligned by distance around the track rather than by time - two drivers
are rarely at the same distance at the same timestamp (different pace,
different lap start), but "80m into the lap" means the same physical
point on track for both of them.

Why interpolation is required (see scoping notes / config.yaml):
FastF1 telemetry is NOT sampled at a fixed rate - time deltas between
samples ranged ~0.16s to ~0.92s in testing (mean ~0.26s, i.e. ~3.8Hz,
but irregular). Two drivers' raw samples will essentially never land at
the same distance values, so a raw merge/join would produce mostly NaN
or require nearest-neighbor snapping that silently introduces error.
Instead, both drivers' channels are interpolated onto one shared,
evenly-spaced distance grid, then compared directly at each grid point.

Input: single-lap Telemetry objects from FastF1, e.g.
    lap = laps.pick_driver('VER').pick_fastest()
    tel = lap.get_car_data().add_distance()
This module does not fetch telemetry itself - pass in already-loaded
Telemetry dataframes (keeps this module testable without a live session).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_CHANNELS = ["Speed", "Throttle", "Brake", "nGear", "RPM"]


def align_to_common_distance(
    tel_a: pd.DataFrame,
    tel_b: pd.DataFrame,
    channels: list[str] | None = None,
    n_points: int = 500,
) -> pd.DataFrame:
    """
    Interpolate two telemetry traces onto one shared distance grid.

    The grid spans the overlapping distance range of both laps (min of the
    two maxes, to avoid extrapolating past whichever driver's lap was
    measured over a shorter distance) at n_points evenly spaced steps.

    Returns a single dataframe with columns like Speed_A, Speed_B,
    Throttle_A, Throttle_B, ... plus a Distance column - one row per grid
    point, ready for direct comparison or plotting.

    Brake is typically boolean/0-1 in FastF1 - interpolating it linearly
    produces intermediate values (e.g. 0.3), which is intentional here:
    it represents "how much of the grid step was under braking," useful
    for finding approximate braking *zones* rather than the exact on/off
    instant. Don't treat interpolated Brake as a literal boolean.
    """
    if channels is None:
        channels = DEFAULT_CHANNELS

    for tel, label in [(tel_a, "A"), (tel_b, "B")]:
        if "Distance" not in tel.columns:
            raise ValueError(
                f"Telemetry {label} has no Distance column - call "
                f".add_distance() on the lap's telemetry before passing it in."
            )

    max_common_distance = min(tel_a["Distance"].max(), tel_b["Distance"].max())
    grid = np.linspace(0, max_common_distance, n_points)

    out = pd.DataFrame({"Distance": grid})
    for tel, suffix in [(tel_a, "A"), (tel_b, "B")]:
        # Distance must be strictly increasing for np.interp; sort defensively
        # in case of any out-of-order samples (shouldn't happen, but cheap to guard).
        sorted_tel = tel.sort_values("Distance")
        x = sorted_tel["Distance"].to_numpy(dtype=float)
        for channel in channels:
            if channel not in sorted_tel.columns:
                continue
            y = sorted_tel[channel].to_numpy(dtype=float)
            out[f"{channel}_{suffix}"] = np.interp(grid, x, y)

    return out


def speed_delta(aligned: pd.DataFrame, driver_a_label: str = "A", driver_b_label: str = "B") -> pd.DataFrame:
    """
    Add a SpeedDelta column (Speed_A - Speed_B) to an aligned dataframe.
    Positive = driver A faster at that point on track.
    """
    out = aligned.copy()
    out["SpeedDelta"] = out[f"Speed_{driver_a_label}"] - out[f"Speed_{driver_b_label}"]
    return out


def find_braking_zones(
    aligned: pd.DataFrame, driver_label: str, brake_threshold: float = 0.1
) -> pd.DataFrame:
    """
    Identify contiguous braking zones for one driver from the aligned grid:
    each zone is a (start_distance, end_distance, min_speed_in_zone) row.

    brake_threshold is on the interpolated Brake channel (0-1 range after
    interpolation - see align_to_common_distance docstring) - a low
    threshold like 0.1 catches the start of trail-braking, not just hard
    braking.
    """
    col = f"Brake_{driver_label}"
    if col not in aligned.columns:
        raise ValueError(f"No {col} column - was 'Brake' included in channels when aligning?")

    is_braking = aligned[col] > brake_threshold
    # Identify contiguous True runs via a group id that increments each time
    # the boolean flips - standard pandas idiom for run-length grouping.
    group_id = (is_braking != is_braking.shift()).cumsum()

    zones = []
    for _, group in aligned[is_braking].groupby(group_id[is_braking]):
        zones.append({
            "StartDistance": group["Distance"].min(),
            "EndDistance": group["Distance"].max(),
            "MinSpeed": group[f"Speed_{driver_label}"].min(),
            "ZoneLength": group["Distance"].max() - group["Distance"].min(),
        })

    return pd.DataFrame(zones)


def compare_braking_points(
    aligned: pd.DataFrame, brake_threshold: float = 0.1
) -> pd.DataFrame:
    """
    Compare driver A's and driver B's braking zones directly: for each of
    driver A's braking zones, find whichever of driver B's zones overlaps
    it most, and report the gap in braking start point (who brakes later
    into the corner, and by how much distance).

    Zones that don't have a reasonable overlap on the other side (e.g. one
    driver took a different line/gear and there's no matching zone) are
    left out rather than force-matched to the nearest unrelated zone.
    """
    zones_a = find_braking_zones(aligned, "A", brake_threshold)
    zones_b = find_braking_zones(aligned, "B", brake_threshold)

    if zones_a.empty or zones_b.empty:
        return pd.DataFrame()

    matches = []
    for _, za in zones_a.iterrows():
        # Find the driver-B zone with the largest overlap with this driver-A zone.
        overlaps = zones_b.apply(
            lambda zb: max(
                0,
                min(za["EndDistance"], zb["EndDistance"])
                - max(za["StartDistance"], zb["StartDistance"]),
            ),
            axis=1,
        )
        best_idx = overlaps.idxmax()
        if overlaps[best_idx] <= 0:
            continue  # no real overlap - not the same braking zone, skip

        zb = zones_b.loc[best_idx]
        matches.append({
            "ZoneStartA": za["StartDistance"],
            "ZoneStartB": zb["StartDistance"],
            # Positive = A brakes later (deeper into the corner) than B.
            "BrakingPointGap": zb["StartDistance"] - za["StartDistance"],
            "MinSpeedA": za["MinSpeed"],
            "MinSpeedB": zb["MinSpeed"],
        })

    return pd.DataFrame(matches)


def top_speed_comparison(aligned: pd.DataFrame) -> dict:
    """Simple top-speed summary for both drivers over the aligned lap."""
    return {
        "TopSpeedA": aligned["Speed_A"].max(),
        "TopSpeedB": aligned["Speed_B"].max(),
        "Gap": aligned["Speed_A"].max() - aligned["Speed_B"].max(),
    }