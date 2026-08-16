# Microgrid planner: forecasting and sizing experiments

Working code behind the demand-forecasting and PV-sizing results.

## Setup

```bash
pip install pandas numpy scikit-learn lightgbm pvlib matplotlib
```

## Run order (matters)

```bash
python load_forecast.py    # downloads data, trains models, writes results_predictions.csv
python solar_sizing.py     # reads results_predictions.csv for the load shape
python make_figures.py     # writes the two PNGs
```

`load_forecast.py` fetches `data/AEP_hourly.csv` automatically on first run
(PJM AEP hourly load, 121,296 records, Oct 2004 to Aug 2018).

## What each script does

**load_forecast.py** benchmarks day-ahead hourly load forecasting. All lag
features are 24 hours or older, so this is a genuine day-ahead setup and not a
one-step-ahead model that leaks the previous hour. Models compared: seasonal
naive, ridge on calendar features, LightGBM on calendar features, LightGBM on
calendar plus lags. Also trains P10/P50/P90 quantile models and reports pinball
loss and empirical coverage.

Result on the Aug 2017 to Aug 2018 test period: LightGBM with lags reached
4.72% MAPE against 9.87% for the seasonal naive baseline. `lag_24` alone
contributed 65% of total split gain.

**solar_sizing.py** runs a physical PV model with pvlib on real TMY3 weather
(transposition to plane of array, cell temperature, PVWatts DC, inverter), then
an 8760-hour battery simulation that sweeps array and storage size and reports
loss of power supply probability (LPSP), curtailment and capex.

Key result: the textbook rule of thumb called for 6.21 kWp, while the hourly
simulation showed the cheapest configuration meeting LPSP <= 5% was 10 kWp with
a 20 kWh battery.

## Swapping in Bengaluru data

`solar_sizing.py` uses the TMY3 file bundled inside pvlib (Greensboro NC,
PSH 4.29). Bengaluru is roughly PSH 5.2 to 5.5, so yields will be better.
Replace the TMY block with:

```python
tmy, _, _, _ = pvlib.iotools.get_pvgis_tmy(12.97, 77.59, map_variables=True)
```

Other free sources: NASA POWER, NREL NSRDB, Open-Meteo, Global Wind Atlas.

## Known limitations

- The mirrored load dataset has no temperature column, so the model
  over-forecasts during cold snaps. That gap is the argument for the weather
  API in the system architecture.
- Quantile models were miscalibrated out of sample: P90 achieved 80.8%
  empirical coverage against a 90% target.
- Weather and load come from different sites and years. In the real system both
  come from the same user-supplied location.
