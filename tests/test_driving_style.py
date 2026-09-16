"""
Unit tests for src/telemetry/driving_style.py.

Builds tiny synthetic telemetry with a known, simple shape (constant or
linear speed) so the interpolation result can be checked against an
exact expected answer, rather than just "did it run."

Run: pytest tests/test_driving_style.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest

from src.telemetry.driving_style import align_to_common_distance, speed_delta


def _make_fake_telemetry(distances: list[float], speeds: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "Distance": distances,
        "Speed": speeds,
        "Throttle": [100.0] * len(distances),
        "Brake": [0.0] * len(distances),
        "nGear": [8] * len(distances),
        "RPM": [11000.0] * len(distances),
    })


def test_alignment_produces_requested_grid_size():
    tel_a = _make_fake_telemetry([0, 100, 200, 300], [200, 220, 240, 260])
    tel_b = _make_fake_telemetry([0, 90, 210, 290], [190, 215, 235, 255])

    aligned = align_to_common_distance(tel_a, tel_b, n_points=50)
    assert len(aligned) == 50
    assert aligned["Distance"].is_monotonic_increasing


def test_alignment_recovers_known_linear_speed():
    """
    If speed increases perfectly linearly with distance, interpolation
    at any point should match the exact linear formula - this checks the
    interpolation math itself is correct, not just "produces some numbers."
    """
    # Speed = 200 + 0.5 * distance, exactly, from 0 to 1000m
    distances = list(range(0, 1001, 50))
    speeds = [200 + 0.5 * d for d in distances]
    tel_a = _make_fake_telemetry(distances, speeds)
    tel_b = _make_fake_telemetry(distances, speeds)  # identical for simplicity

    aligned = align_to_common_distance(tel_a, tel_b, n_points=11)  # every 100m from 0-1000

    for _, row in aligned.iterrows():
        expected_speed = 200 + 0.5 * row["Distance"]
        assert row["Speed_A"] == pytest.approx(expected_speed, abs=0.01)
        assert row["Speed_B"] == pytest.approx(expected_speed, abs=0.01)


def test_alignment_stops_at_shorter_common_distance():
    """
    If one driver's telemetry only extends to 500m and the other to
    1000m, the aligned grid should stop at 500m (the overlapping range) -
    extrapolating past a driver's actual recorded distance would be
    fabricating data, not measuring it.
    """
    tel_a = _make_fake_telemetry([0, 250, 500], [200, 210, 220])
    tel_b = _make_fake_telemetry([0, 500, 1000], [200, 220, 240])

    aligned = align_to_common_distance(tel_a, tel_b, n_points=20)
    assert aligned["Distance"].max() == pytest.approx(500, abs=1)


def test_speed_delta_sign_convention():
    """
    speed_delta = Speed_A - Speed_B. Positive should mean A is faster at
    that point. Locks in the sign convention.
    """
    aligned = pd.DataFrame({
        "Distance": [0, 100, 200],
        "Speed_A": [200, 220, 210],
        "Speed_B": [190, 225, 215],
    })
    result = speed_delta(aligned)
    assert result["SpeedDelta"].tolist() == pytest.approx([10, -5, -5])