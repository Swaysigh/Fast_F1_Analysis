"""
Manual smoke test for src/telemetry/driving_style.py.
Run locally: python scripts/test_telemetry.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loader import enable_cache, load_session, get_clean_laps
from src.telemetry.driving_style import (
    align_to_common_distance,
    speed_delta,
    find_braking_zones,
    compare_braking_points,
    top_speed_comparison,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

enable_cache()

print("=" * 60)
print("Loading 2024 Monza Qualifying (fastest laps, cleanest comparison)")
print("=" * 60)
session = load_session(2024, "Monza", "Q")
laps = session.laps

driver_a, driver_b = "NOR", "PIA"  # McLaren teammates
lap_a = laps.pick_drivers(driver_a).pick_fastest()
lap_b = laps.pick_drivers(driver_b).pick_fastest()
print(f"{driver_a} fastest lap: {lap_a['LapTime']}")
print(f"{driver_b} fastest lap: {lap_b['LapTime']}")

tel_a = lap_a.get_car_data().add_distance()
tel_b = lap_b.get_car_data().add_distance()
print(f"\n{driver_a} telemetry points: {len(tel_a)}, max distance: {tel_a['Distance'].max():.1f}m")
print(f"{driver_b} telemetry points: {len(tel_b)}, max distance: {tel_b['Distance'].max():.1f}m")

print("\n" + "=" * 60)
print("ALIGNING TO COMMON DISTANCE GRID")
print("=" * 60)
aligned = align_to_common_distance(tel_a, tel_b, n_points=500)
print(f"Aligned shape: {aligned.shape}")
print(f"Columns: {list(aligned.columns)}")
print(aligned.head())

print("\n" + "=" * 60)
print("SPEED DELTA")
print("=" * 60)
aligned = speed_delta(aligned)
print(f"Mean speed delta ({driver_a} - {driver_b}): {aligned['SpeedDelta'].mean():.2f} km/h")
print(f"Max {driver_a} advantage: {aligned['SpeedDelta'].max():.2f} km/h at distance {aligned.loc[aligned['SpeedDelta'].idxmax(), 'Distance']:.0f}m")
print(f"Max {driver_b} advantage: {-aligned['SpeedDelta'].min():.2f} km/h at distance {aligned.loc[aligned['SpeedDelta'].idxmin(), 'Distance']:.0f}m")

print("\n" + "=" * 60)
print("TOP SPEED COMPARISON")
print("=" * 60)
top_speed = top_speed_comparison(aligned)
print(top_speed)

print("\n" + "=" * 60)
print(f"BRAKING ZONES: {driver_a}")
print("=" * 60)
zones_a = find_braking_zones(aligned, "A")
print(f"Found {len(zones_a)} braking zones")
print(zones_a)

print("\n" + "=" * 60)
print(f"BRAKING ZONES: {driver_b}")
print("=" * 60)
zones_b = find_braking_zones(aligned, "B")
print(f"Found {len(zones_b)} braking zones")
print(zones_b)

print("\n" + "=" * 60)
print("BRAKING POINT COMPARISON (positive = A brakes later)")
print("=" * 60)
braking_comparison = compare_braking_points(aligned)
print(braking_comparison)

print("\n" + "=" * 60)
print("SANITY CHECKS")
print("=" * 60)
assert len(aligned) == 500, "grid should have exactly n_points rows"
assert aligned["Distance"].is_monotonic_increasing, "distance grid should be sorted"
assert not aligned[["Speed_A", "Speed_B"]].isna().any().any(), "no NaNs expected after interpolation within range"
print("PASS: grid size, monotonicity, no unexpected NaNs")

# Sanity: number of braking zones found should be a plausible number for
# a track like Monza (roughly 6-11 significant braking events per lap)
print(f"\nBraking zones found - A: {len(zones_a)}, B: {len(zones_b)} (Monza plausible range: ~6-11)")

print("\nALL TESTS COMPLETED")