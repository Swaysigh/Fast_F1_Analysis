"""
Diagnostic: inspect raw Position values for SAI and PIA around the laps
that produced suspicious PosBefore=1.0 readings in test_strategy.py.
Run locally: python scripts/debug_position.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loader import enable_cache, load_session

enable_cache()

session = load_session(2024, "Monza", "R")
laps = session.laps

print("=" * 60)
print("SAI laps 10-20 (around the LEC/SAI pit events at 15, 19)")
print("=" * 60)
sai = laps[laps["Driver"] == "SAI"].sort_values("LapNumber")
print(sai[sai["LapNumber"].between(10, 20)][["LapNumber", "Position", "PitInTime", "PitOutTime"]])

print("\n" + "=" * 60)
print("LEC laps 10-20")
print("=" * 60)
lec = laps[laps["Driver"] == "LEC"].sort_values("LapNumber")
print(lec[lec["LapNumber"].between(10, 20)][["LapNumber", "Position", "PitInTime", "PitOutTime"]])

print("\n" + "=" * 60)
print("PIA laps 12-20 (around the NOR/PIA pit events at 14, 16)")
print("=" * 60)
pia = laps[laps["Driver"] == "PIA"].sort_values("LapNumber")
print(pia[pia["LapNumber"].between(12, 20)][["LapNumber", "Position", "PitInTime", "PitOutTime"]])

print("\n" + "=" * 60)
print("Full race leader (Position==1.0) by lap - who's actually leading when")
print("=" * 60)
leaders = laps[laps["Position"] == 1.0][["Driver", "LapNumber"]].sort_values("LapNumber")
print(f"Total laps led (all drivers combined): {len(leaders)}")
print(leaders.head(30))
print("\nWho led at any point:")
print(leaders["Driver"].value_counts())