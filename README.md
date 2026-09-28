# Microgrid Feasibility Dashboard

This project is a Microgrid Feasibility Dashboard, consisting of a Python Flask backend API and a React frontend.

## Prerequisites

- Node.js
- npm
- Python 3.x
- pip

## How to Run the Program

You need to run both the backend (Flask) and the frontend (React) servers simultaneously in two separate terminal windows.

### 1. Run the Backend (Flask API)

Open a terminal in the root directory of this repository and run the following commands:

`source .venv/bin/activate`

`pip install -r requirements.txt`

`python3 app.py`

The backend server should now be running, on `http://127.0.0.1:5050` (port 5000 is used by macOS AirPlay Receiver).

### 2. Run the Frontend (React App)

Open a **new, second terminal window**, also in the root directory of this repository, and run:

`npm install`

`npm start` (Assuming you map this to react-scripts start or similar, otherwise just the regular start command)

## City analysis

Beyond planning one site, the app can map a whole city: where demand is, where
industry and emissions are, and which places are the best microgrid candidates.

Search a city in the dashboard and press **Analyse city**. The map gains
toggleable layers (candidate sites, estimated consumption, population density,
industrial load, industrial sites, CO2 emitters) and a panel summarising what
was found. Clicking a candidate cell moves the site pin there, so the normal
site scan and plan flow continues from it.

### Confidence tiers

Coverage is uneven worldwide, so every number says how it was produced:

| Tier | Meaning |
|---|---|
| `official` | Published by a utility or regulator |
| `calibrated` | Global estimate scaled to an official total |
| `estimated` | Global data only (population, night lights, OSM) |

For Bengaluru the residential estimate is calibrated against BESCOM's published
FY2023-24 domestic sales. No Indian utility publishes city-level consumption
(BESCOM reports one total across eight districts), so the official figure is
applied as demand per person across the service area. Before calibration the
global model was 15.7% off that figure.

Sources, licences and resolutions for every layer are in `CITY_DATA.md`.
`scripts/probe_sources.py` re-checks that each one is still reachable.

### API

```
POST /api/city-scan                      {"name": "Bengaluru", "cell_size_m": 1000}
GET  /api/city-scan/<id>
GET  /api/city-scan/<id>/layers/<layer>  population|consumption|industry|emissions|score
GET  /api/city-scan/<id>/points/<kind>   industry|emitters
```

Results are cached in the database for 30 days; a repeat request returns in
milliseconds. The first run for a region downloads a 160 MB GHSL population
tile into `city_scan/data/tiles/` (git-ignored) and reuses it for every city in
that 10x10 degree area.

### Tests

`.venv/bin/pytest` runs everything offline: network and raster calls are stubbed.
