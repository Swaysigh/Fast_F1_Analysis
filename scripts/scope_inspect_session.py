"""
Step 1: Inspect a single race session - laps, telemetry, weather.
Run locally: python 01_inspect_session.py
Paste the full output back into chat.
"""
import fastf1
import os

os.makedirs('data/cache', exist_ok=True)
fastf1.Cache.enable_cache('data/cache')

session = fastf1.get_session(2024, 'Monza', 'R')
session.load()

laps = session.laps
print("=" * 60)
print("LAPS DATAFRAME")
print("=" * 60)
print("Shape:", laps.shape)
print("Columns:", list(laps.columns))
print("\nNull counts per column:")
print(laps.isnull().sum())
print("\nSample row:")
print(laps.iloc[0])

print("\n" + "=" * 60)
print("TELEMETRY (single lap)")
print("=" * 60)
fastest_lap = laps.pick_fastest()
tel = fastest_lap.get_car_data().add_distance()
print("Shape:", tel.shape)
print("Columns:", list(tel.columns))
print("\nSample rows:")
print(tel.head())
print("\nSampling rate check (time deltas, seconds):")
print(tel['Time'].diff().dt.total_seconds().describe())

print("\n" + "=" * 60)
print("WEATHER DATA")
print("=" * 60)
weather = session.weather_data
print("Shape:", weather.shape)
print("Columns:", list(weather.columns) if weather is not None else "None")

print("\n" + "=" * 60)
print("TYRE / COMPOUND INFO")
print("=" * 60)
print(laps[['Driver', 'Compound', 'TyreLife', 'Stint']].drop_duplicates(subset=['Driver','Stint']).head(20))
