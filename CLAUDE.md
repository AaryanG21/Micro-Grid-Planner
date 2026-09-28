# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The backend runs on **port 5050**, not 5000 — macOS AirPlay Receiver holds 5000, and
`package.json`'s `proxy` points at 5050. There is no `python` on this machine; use the venv.

```bash
source .venv/bin/activate && pip install -r requirements.txt
.venv/bin/python app.py          # backend  -> http://127.0.0.1:5050
npm install && npm start         # frontend -> http://localhost:3000 (proxies /api to 5050)

.venv/bin/pytest                 # whole suite, fully offline (network + rasters stubbed)
.venv/bin/pytest test_city_scan.py::test_calibration_applies_official_per_capita_rate
FLASK_APP=app.py .venv/bin/flask db upgrade     # apply migrations
.venv/bin/python scripts/probe_sources.py       # re-check every external data source
```

**Migrations:** `app.py` calls `db.create_all()` at import, so a freshly started app already
has every table and `flask db migrate` reports "no changes". New tables therefore need a
hand-written migration (see `migrations/versions/c3f81a92b7d4_add_city_analysis.py`).
When testing a migration, point `DATABASE_URL` at an **absolute** path outside the repo —
a relative path resolves back to `instance/microgrid.db`, and a `drop_all()` there wipes
the dev database (it happened; `instance/` is gitignored, so there is no backup).

## Architecture

Flask API (`app.py`, ~850 lines, single file) + React CRA frontend (`src/App.jsx`, ~1,750 lines).
SQLite by default, Postgres via `DATABASE_URL` (Render deploy in `render.yaml`).
Multi-tenant: Organization -> User -> Project -> Analysis, JWT auth, per-org API keys.

Three analysis scales, each layered on the one below:

1. **Plan** (`size_system` in `app.py`) — sizes PV/wind/biomass/battery for one site with
   `scipy.optimize.linprog`, simulates 8760 hours, returns capex/IRR/LPSP. NASA POWER and
   Open-Meteo supply weather.
2. **Site scan** (`site_scan.py`) — one map click, ~50 m radius. OSM buildings via Overpass,
   demand from per-building benchmarks (documented assumptions, *not* ML), then shaped into
   an hourly profile by the trained model in `models/demand_shape.joblib` (this step *is* ML).
3. **City scan** (`city_scan/`) — a whole city as a grid of cells, with population, night
   lights, industry, emissions and a candidate-site ranking. See below.

Both scans register themselves onto the app the same way: `register_site_scan(app, cache, limiter)`
and `register_city_scan(app, cache, limiter)`, called near the top of `app.py`.

### Honesty contract

Every derived number carries the method that produced it. `site_scan.py` returns a `method`
string on each figure; `city_scan` adds a **tier** on every value:

| Tier | Meaning |
|---|---|
| `official` | published by a utility or regulator |
| `calibrated` | global estimate scaled to an official total |
| `estimated` | global proxies only |

Preserve this when editing. A number whose provenance the UI cannot state does not belong
in a feasibility report.

### city_scan pipeline

`pipeline.analyze_city()` runs each layer through `run_layer()`, which records failures
per layer and continues — one dead upstream API must never fail a whole scan. Order:
`boundary` -> `grid` -> `population` -> `nightlights` -> `industry` -> `emissions` ->
`consumption` -> `calibration` (if the region has official data) -> `scoring`.
Results cache in the `CityAnalysis` table for 30 days; a repeat request returns in ms.

**Calibration is service-area wide, and applied as a rate per person.** No Indian utility
publishes city-level consumption — BESCOM reports one total across 8 districts and 41,092 km².
Scaling city cells to that total inflates the city ~7x. Instead: official domestic sales ÷
service-area population = kWh per person per year, applied through each cell's population.
Only residential demand is calibrated; industrial load stays an OSM estimate. The
pre-calibration error is kept and shown — for Bengaluru the global model was 15.7% off.

Adding a region = adding a module under `city_scan/regional/` and registering it in
`regional/__init__.py`. Nothing in the pipeline changes.

## External data

`CITY_DATA.md` is the source of truth: every layer's URL, licence, resolution and gotchas,
plus what was tried and rejected. Read it before touching a data source. Highlights:

- **Overpass** returns 406 without a User-Agent, and 429/504 when busy. `overpass_query()`
  in `site_scan.py` retries with backoff and a hard deadline; it does not fail over to
  mirrors (every public mirror tested was dead or slower than the retry).
- **Population** is GHSL, not WorldPop: WorldPop advertises `Accept-Ranges` and then ignores
  ranged GETs. GHSL tiles are 160 MB each, cached in `city_scan/data/tiles/` (gitignored).
- **Night lights** come from a Zenodo-hosted COG because EOG's own files need a login. Do
  not set `CPL_VSIL_CURL_ALLOWED_EXTENSIONS` for it — the URL ends in `/content`, not `.tif`.
- **Climate TRACE** has no bbox filter on emissions: resolve bbox -> `cityId` via `/v7/cities`,
  then query `/v7/sources`. `sourceType: city-aggregation` rows are modelled city totals at
  one centroid; binning them into a cell invents a hotspot, so they are excluded.
- **Nominatim** matches roads and scrub patches for district names. Use `require_admin=True`
  for official areas and try spelling variants ("Chikkaballapur" vs "Chikkaballapura").

## Frontend notes

`react-leaflet` traps that cost time here, all commented in `src/components/city/CityLayers.jsx`:
`GeoJSON` renders `data` once at mount (keys must change when data arrives), `LayersControl.Overlay`
ignores `eventHandlers` (so layers load eagerly with the scan) and takes exactly one layer
child (wrap markers in `LayerGroup`, or each marker becomes its own legend row).

City state lives in `src/hooks/useCityScan.js` rather than `App.jsx`, which is already long.

## Repo hygiene

Root holds `.bak-*` snapshots and `patch_*.py` one-off scripts from earlier manual edits —
rollback artefacts, not maintained code. `load_forecast.py`, `solar_sizing.py` and
`train_demand_model.py` are a separate research track (see `FORECASTING.md`), not wired into
the live API.
