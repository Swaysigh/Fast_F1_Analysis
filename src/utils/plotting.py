"""
Shared plotting helpers used across components. Centralizing style here
(rather than repeating rcParams/colors in every script) keeps figures
visually consistent for a writeup.

Every function here takes already-computed dataframes (from src/pace,
src/tyre, src/telemetry, src/quali_race_gap, src/strategy) - this module
does no FastF1 loading or analysis itself, only rendering.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

# F1 team colors used across plots where a team/driver needs a consistent
# color. Not exhaustive - falls back to matplotlib's default cycle for
# anything not listed here.
TEAM_COLORS = {
    "Red Bull Racing": "#3671C6",
    "Ferrari": "#E8002D",
    "Mercedes": "#27F4D2",
    "McLaren": "#FF8000",
    "Aston Martin": "#229971",
    "Alpine": "#FF87BC",
    "Williams": "#64C4FF",
    "RB": "#6692FF",
    "Kick Sauber": "#52E252",
    "Haas F1 Team": "#B6BABD",
}

FIGSIZE_DEFAULT = (10, 6)
FIGSIZE_WIDE = (14, 6)


def _apply_base_style(ax: plt.Axes, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_pace_evolution(evolution: pd.DataFrame, driver: str, save_path: str | None = None) -> plt.Figure:
    """
    Plot a single driver's lap-by-lap pace evolution: raw lap time vs
    tyre-adjusted pace, with stint boundaries marked.

    Expects the output of src.pace.pace_analysis.pace_evolution().
    """
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)

    ax.plot(evolution["LapNumber"], evolution["LapTimeSeconds"], "o-", label="Raw lap time", alpha=0.6, markersize=4)
    ax2 = ax.twinx()
    ax2.plot(evolution["LapNumber"], evolution["AdjustedPace"], "s-", color="darkred", label="Tyre-adjusted pace (residual)", alpha=0.7, markersize=4)
    ax2.axhline(0, color="gray", linestyle="--", linewidth=0.8)

    for stint_start in evolution.groupby("Stint")["LapNumber"].min().values[1:]:
        ax.axvline(stint_start - 0.5, color="black", linestyle=":", alpha=0.5)

    _apply_base_style(ax, f"{driver}: Pace Evolution", "Lap Number", "Lap Time (s)")
    ax2.set_ylabel("Adjusted Pace Residual (s)", fontsize=11)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def plot_consistency_ranking(consistency: pd.DataFrame, top_n: int = 15, save_path: str | None = None) -> plt.Figure:
    """
    Horizontal bar chart of the most consistent driver-stints (lowest
    AdjustedPaceStd first). Bars for low-sample stints (LowSampleWarning)
    are shown with reduced opacity and a hatch pattern so they're visually
    distinguishable rather than silently blending in with reliable ones.

    Expects the output of src.pace.pace_analysis.consistency_by_stint().
    """
    subset = consistency.head(top_n).iloc[::-1]  # reverse so best is at top of horizontal chart
    labels = subset["Driver"] + " (S" + subset["Stint"].astype(int).astype(str) + ", " + subset["Compound"] + ")"

    fig, ax = plt.subplots(figsize=FIGSIZE_DEFAULT)
    colors = ["#cccccc" if low else "#3671C6" for low in subset["LowSampleWarning"]]
    hatches = ["//" if low else None for low in subset["LowSampleWarning"]]
    bars = ax.barh(labels, subset["AdjustedPaceStd"], color=colors)
    for bar, hatch in zip(bars, hatches):
        if hatch:
            bar.set_hatch(hatch)

    _apply_base_style(ax, "Most Consistent Driver-Stints (lower = steadier pace)", "Adjusted Pace Std Dev (s)", "")
    ax.text(0.98, 0.02, "hatched bars = fewer than 8 laps, read with caution",
            transform=ax.transAxes, ha="right", fontsize=8, style="italic", color="gray")

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def plot_degradation_curves(
    curves: pd.DataFrame, compound: str, save_path: str | None = None, min_total_laps: int = 10
) -> plt.Figure:
    """
    Bar chart of weighted average degradation slope per driver for one
    compound (fuel-corrected). Expects the output of
    src.tyre.degradation.compare_drivers_by_compound().

    Drivers with fewer than min_total_laps laps on this compound are
    excluded from the chart, not just flagged - a single short/anomalous
    stint (e.g. a driver who pitted onto this compound shortly before
    retiring) can produce a slope so extreme it compresses every other
    driver's bar into an unreadable flat line near zero, exactly as
    observed in testing (2024 Monza HARD: TSU's 5-lap stint produced a
    slope 10x+ larger than the rest of the field, based on the
    per-stint fit in fit_degradation_curves flagging that stint's
    LowSampleWarning - dwarfing every other bar). Excluding rather than
    just color-flagging is deliberate here: on a bar chart (unlike the
    ranked table), a single outlier bar breaks the chart's usefulness
    for everyone else, not just for itself.
    """
    plot_data = curves[curves["TotalLaps"] >= min_total_laps]
    excluded = curves[curves["TotalLaps"] < min_total_laps]

    fig, ax = plt.subplots(figsize=FIGSIZE_DEFAULT)
    colors = [TEAM_COLORS.get(team, "#888888") for team in plot_data["Team"]]
    ax.bar(plot_data["Driver"], plot_data["WeightedAvgSlope"], color=colors)
    ax.axhline(0, color="black", linewidth=0.8)

    _apply_base_style(
        ax,
        f"{compound.title()} Tyre Degradation by Driver (fuel-corrected)",
        "Driver",
        "Slope (s/lap of tyre age)",
    )
    caption = "Fuel-burn corrected; see src/tyre/degradation.py for methodology & limitations"
    if not excluded.empty:
        caption += f"\nExcluded (fewer than {min_total_laps} laps on this compound): {', '.join(excluded['Driver'])}"
    ax.text(0.02, 0.98, caption, transform=ax.transAxes, va="top", fontsize=8, style="italic", color="gray")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def plot_speed_trace(aligned: pd.DataFrame, driver_a_label: str, driver_b_label: str, save_path: str | None = None) -> plt.Figure:
    """
    Distance-aligned speed trace comparison for two drivers, with a speed
    delta subplot beneath. Expects output of
    src.telemetry.driving_style.align_to_common_distance() (already run
    through speed_delta()).
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=FIGSIZE_WIDE, sharex=True, height_ratios=[2, 1])

    ax1.plot(aligned["Distance"], aligned["Speed_A"], label=driver_a_label, linewidth=1.5)
    ax1.plot(aligned["Distance"], aligned["Speed_B"], label=driver_b_label, linewidth=1.5)
    _apply_base_style(ax1, f"{driver_a_label} vs {driver_b_label}: Speed Trace", "", "Speed (km/h)")
    ax1.legend(fontsize=9)

    if "SpeedDelta" in aligned.columns:
        ax2.fill_between(aligned["Distance"], aligned["SpeedDelta"], 0,
                          where=(aligned["SpeedDelta"] >= 0), color="tab:blue", alpha=0.4, label=f"{driver_a_label} faster")
        ax2.fill_between(aligned["Distance"], aligned["SpeedDelta"], 0,
                          where=(aligned["SpeedDelta"] < 0), color="tab:orange", alpha=0.4, label=f"{driver_b_label} faster")
        ax2.axhline(0, color="black", linewidth=0.8)
    _apply_base_style(ax2, "", "Distance (m)", "Speed Delta (km/h)")
    ax2.legend(fontsize=9, loc="upper right")

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def plot_quali_vs_race_gap(gap_df: pd.DataFrame, save_path: str | None = None) -> plt.Figure:
    """
    Diverging bar chart of QualiRank vs RacePaceRank gap per driver,
    colored by specialist label if present (run through
    classify_specialists() first for the coloring; otherwise all bars are
    a single color).

    Expects the output of src.quali_race_gap.gap_analysis.quali_vs_race_gap()
    (optionally passed through classify_specialists() first).
    """
    sorted_df = gap_df.sort_values("Gap")
    label_colors = {"Race specialist": "#2ca02c", "Qualifying specialist": "#d62728", "Balanced": "#888888"}
    colors = (
        sorted_df["Label"].map(label_colors)
        if "Label" in sorted_df.columns
        else "#3671C6"
    )

    fig, ax = plt.subplots(figsize=FIGSIZE_DEFAULT)
    ax.barh(sorted_df["Abbreviation"], sorted_df["Gap"], color=colors)
    ax.axvline(0, color="black", linewidth=0.8)

    _apply_base_style(
        ax,
        "Qualifying vs Race Pace Gap (positive = race pace stronger)",
        "Gap (rank positions)",
        "",
    )

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def plot_position_swing(comparison: pd.DataFrame, driver: str, rival: str, save_path: str | None = None) -> plt.Figure:
    """
    Bar chart of position swing per pit event between two drivers.
    Expects the output of src.strategy.strategy_analysis.compare_strategy_vs_rival().

    Note (see strategy_analysis.py docstring): a large swing right at a
    rival's own pit lap can partly reflect a pit-stop-shuffle effect
    rather than pure strategy skill - this is noted as an annotation on
    the plot itself so it travels with the figure, not just the code.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE_DEFAULT)
    colors = ["#2ca02c" if v < 0 else "#d62728" for v in comparison["PositionSwing"]]
    ax.bar(comparison["PitLap"].astype(str), comparison["PositionSwing"], color=colors)
    ax.axhline(0, color="black", linewidth=0.8)

    _apply_base_style(
        ax,
        f"{driver} vs {rival}: Position Swing per Pit Event\n(negative = {driver} gained on {rival})",
        "Pit Lap",
        "Position Swing",
    )
    ax.text(0.02, 0.98, "Swings at a rival's own pit lap may partly reflect a pit-stop shuffle, not pure skill",
            transform=ax.transAxes, va="top", fontsize=8, style="italic", color="gray")

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig