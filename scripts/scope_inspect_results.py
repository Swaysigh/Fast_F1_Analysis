"""
Step 3: Check session.results for qualifying (Q1/Q2/Q3) and race classification.
Run locally: python scripts/scope_inspect_results.py
"""
import fastf1
import os

os.makedirs('data/cache', exist_ok=True)
fastf1.Cache.enable_cache('data/cache')

q = fastf1.get_session(2024, 'Monza', 'Q')
q.load()

print("=" * 60)
print("QUALIFYING session.results")
print("=" * 60)
res = q.results
print("Shape:", res.shape)
print("Columns:", list(res.columns))
print("\nQ1/Q2/Q3 present:", [c for c in res.columns if c in ('Q1','Q2','Q3')])
print("\nSample:")
print(res[['Abbreviation','Position','Q1','Q2','Q3']].head(10))
print("\nNulls in Q1/Q2/Q3 (expected for drivers eliminated early):")
print(res[['Q1','Q2','Q3']].isnull().sum())

print("\n" + "=" * 60)
print("RACE session.results (for race pace ranking / final position)")
print("=" * 60)
r = fastf1.get_session(2024, 'Monza', 'R')
r.load()
rres = r.results
print("Columns:", list(rres.columns))
print(rres[['Abbreviation','Position','GridPosition','Status','Points']].head(10))
