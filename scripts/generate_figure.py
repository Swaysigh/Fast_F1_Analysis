"""
Generate all figures from real 2024 Monza (+ Spa for the gap chart) data.
Run locally: python scripts/generate_figures.py
Outputs land in reports/figures/ - open them after running to check they
look right, this script doesn't validate the visuals themselves.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loader import enable_cache, load_session, get_clean_laps, get_quali_results
from src.pace.pace_analysis import tyre_adjusted_pace, consistency_by_stint, pace_evolution
from src.tyre.degradation import fit_degradation_curves, compare_drivers_by_compound
from src.telemetry.driving_style import align_to_common_distance, speed_delta
from src.quali_race_gap.gap_analysis import rank_qualifying, rank_race_pace, quali_vs_race_gap, classify_specialists
from src.strategy.strategy_analysis import compare_strategy_vs_rival
from src.utils.plotting import (
    plot_pace_evolution,
    plot_consistency_ranking,
    plot_degradation_curves,
    plot_speed_trace,
    plot_quali_vs_race_gap,
    plot_position_swing,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
enable_cache()

FIG_DIR = Path(__file__).resolve().parents[1] / "reports" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("Loading 2024 Monza sessions")
print("=" * 60)
r_session = load_session(2024, "Monza", "R")
q_session = load_session(2024, "Monza", "Q")
clean_laps = get_clean_laps(r_session)
raw_laps = r_session.laps

print("\n[1/6] Pace evolution (VER)")
evolution = pace_evolution(clean_laps, "VER")
plot_pace_evolution(evolution, "VER", save_path=str(FIG_DIR / "01_pace_evolution_VER.png"))
print(f"  Saved: {FIG_DIR / '01_pace_evolution_VER.png'}")

print("\n[2/6] Consistency ranking")
adjusted = tyre_adjusted_pace(clean_laps)
consistency = consistency_by_stint(adjusted)
plot_consistency_ranking(consistency, save_path=str(FIG_DIR / "02_consistency_ranking.png"))
print(f"  Saved: {FIG_DIR / '02_consistency_ranking.png'}")

print("\n[3/6] Tyre degradation (HARD compound)")
curves = fit_degradation_curves(clean_laps)
hard_ranked = compare_drivers_by_compound(curves, "HARD")
plot_degradation_curves(hard_ranked, "HARD", save_path=str(FIG_DIR / "03_degradation_HARD.png"))
print(f"  Saved: {FIG_DIR / '03_degradation_HARD.png'}")

print("\n[4/6] Speed trace (NOR vs PIA, qualifying fastest laps)")
q_laps = q_session.laps
lap_a = q_laps.pick_drivers("NOR").pick_fastest()
lap_b = q_laps.pick_drivers("PIA").pick_fastest()
tel_a = lap_a.get_car_data().add_distance()
tel_b = lap_b.get_car_data().add_distance()
aligned = speed_delta(align_to_common_distance(tel_a, tel_b))
plot_speed_trace(aligned, "NOR", "PIA", save_path=str(FIG_DIR / "04_speed_trace_NOR_PIA.png"))
print(f"  Saved: {FIG_DIR / '04_speed_trace_NOR_PIA.png'}")

print("\n[5/6] Qualifying vs race pace gap")
quali_ranked = rank_qualifying(get_quali_results(q_session))
race_ranked = rank_race_pace(clean_laps)
gap = quali_vs_race_gap(quali_ranked, race_ranked)
classified = classify_specialists(gap)
plot_quali_vs_race_gap(classified, save_path=str(FIG_DIR / "05_quali_race_gap.png"))
print(f"  Saved: {FIG_DIR / '05_quali_race_gap.png'}")

print("\n[6/6] Position swing (LEC vs SAI)")
comparison = compare_strategy_vs_rival(raw_laps, "LEC", "SAI")
plot_position_swing(comparison, "LEC", "SAI", save_path=str(FIG_DIR / "06_position_swing_LEC_SAI.png"))
print(f"  Saved: {FIG_DIR / '06_position_swing_LEC_SAI.png'}")

print("\n" + "=" * 60)
print(f"ALL 6 FIGURES GENERATED in {FIG_DIR}")
print("Open them and check they look right - this script only confirms")
print("they were generated without errors, not that they're correct.")
print("=" * 60)