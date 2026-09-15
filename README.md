# F1 Driver Performance Analysis

Quantitative analysis of Formula 1 driver and team performance using official
timing and telemetry data via [FastF1](https://github.com/theOehrly/Fast-F1).
Moves past descriptive charts into comparative statistical analysis of race
pace, tyre strategy, and qualifying performance.

## Data source

FastF1 pulls official F1 timing API data: lap times, sector times, car
telemetry (speed, throttle, brake, gear, RPM), tyre compound/age, and weather
— at session- and lap-level granularity, across seasons 2023–2025.

**Note:** FastF1 requires live internet access to `livetiming.formula1.com`.
Data pulls must be run in an environment with unrestricted network access
(local machine, Colab, CI) — not a sandboxed environment.

## Core analysis components

1. **Race pace & consistency** — lap time evolution per driver, raw vs.
   tyre-age-adjusted pace, lap time variance as a consistency metric.
2. **Tyre degradation modeling** — regression-fit degradation curves
   (lap time vs. tyre age) per compound per driver, with a fuel-burn
   correction applied (FastF1 has no fuel-mass channel, so this uses a
   standard ~0.03 sec/kg/lap approximation rather than measured data —
   see `src/tyre/degradation.py` docstring for details and caveats).
3. **Telemetry driving-style comparison** — distance-aligned speed/throttle/
   brake traces between two drivers on a common lap (teammate comparisons).
   Telemetry sampling is irregular (~3.8 Hz, not fixed-rate), so both
   drivers' traces are interpolated onto a shared distance grid before
   comparison — see `src/telemetry/driving_style.py`.
4. **Qualifying vs. race pace gap** — delta between qualifying rank and race
   pace rank per driver, classifying "qualifying specialists" vs
   "race-day specialists". Uses median raw race lap time by default rather
   than tyre-adjusted pace — see `RACE_PACE_METHODOLOGY_NOTE` in
   `src/quali_race_gap/gap_analysis.py` for the reasoning and the
   stricter alternative.
5. **Strategy outcome analysis** — scores the undercut/overcut mechanism
   against a specific rival using actual pit lap and track position data.
   This does NOT simulate a full alternative race (no traffic/safety-car
   modeling) — it measures track-position swaps around real pit events,
   a narrower but directly answerable question. See the scope note in
   `src/strategy/strategy_analysis.py`.

## Project structure

```
f1-driver-performance-analysis/
├── configs/
│   └── config.yaml          # seasons, sessions, required columns/channels
├── data/
│   ├── raw/                 # untouched FastF1 pulls (gitignored)
│   ├── processed/           # cleaned/derived datasets (gitignored)
│   └── cache/                # FastF1 cache dir (gitignored)
├── notebooks/
│   └── 00_data_scoping.ipynb  # data availability/quality checks — run first
├── src/
│   ├── data/                # FastF1 loading, caching, session fetch helpers
│   ├── pace/                # component 1: race pace & consistency
│   ├── tyre/                # component 2: degradation modeling
│   ├── telemetry/           # component 3: driving style comparison
│   ├── quali_race_gap/      # component 4: qualifying vs race gap
│   ├── strategy/            # component 5: strategy outcome analysis
│   └── utils/                # shared helpers (alignment, stats, plotting)
├── scripts/                  # standalone runnable scripts (data pulls, etc.)
├── reports/
│   └── figures/              # generated plots (gitignored)
├── tests/
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Status

Data scoping in progress — see `notebooks/00_data_scoping.ipynb` for
availability/completeness checks across seasons before analysis components
are built out.