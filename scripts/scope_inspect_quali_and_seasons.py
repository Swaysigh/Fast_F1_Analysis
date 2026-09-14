"""
Step 2: Check qualifying session structure + cross-season/cross-track consistency.
Run locally: python scripts/scope_inspect_quali_and_seasons.py
Paste output back.
"""

import fastf1
import os

os.makedirs('data/cache', exist_ok=True)
fastf1.Cache.enable_cache('data/cache')

# --- Qualifying session structure (needed for component 4) ---
print("=" * 60)
print("QUALIFYING SESSION")
print("=" * 60)
q = fastf1.get_session(2024, 'Monza', 'Q')
q.load()
qlaps = q.laps
print("Shape:", qlaps.shape)
print("Columns:", list(qlaps.columns))
print("\nQ1/Q2/Q3 segment info present?")
print([c for c in qlaps.columns if 'Segment' in c or 'Q' in c])
print("\nSample - does it have a clean 'best lap per driver per segment'?")
print(qlaps[['Driver', 'LapTime', 'LapNumber']].groupby('Driver').count().head())

# --- Cross-season schema consistency (does 2023 look like 2024?) ---
print("\n" + "=" * 60)
print("CROSS-SEASON CHECK: 2023 Monza Race")
print("=" * 60)
try:
    s23 = fastf1.get_session(2023, 'Monza', 'R')
    s23.load()
    print("2023 laps shape:", s23.laps.shape)
    print("2023 columns match 2024?", list(s23.laps.columns) == list(qlaps.columns) or "different - see below")
    print("2023 columns:", list(s23.laps.columns))
except Exception as e:
    print("2023 FAILED:", repr(e))

# --- A wet/irregular race, to see how degenerate cases look ---
print("\n" + "=" * 60)
print("EDGE CASE CHECK: known wet or chaotic race (2023 Sao Paulo)")
print("=" * 60)
try:
    wet = fastf1.get_session(2023, 'Brazil', 'R')
    wet.load()
    wl = wet.laps
    print("Shape:", wl.shape)
    print("IsAccurate True count:", (wl['IsAccurate'] == True).sum(), "/", len(wl))
    print("Compound value counts:\n", wl['Compound'].value_counts())
except Exception as e:
    print("WET RACE CHECK FAILED:", repr(e))
