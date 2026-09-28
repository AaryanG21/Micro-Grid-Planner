"""Grid and diesel CO2 emission factors.

app.py's size_system() hard-codes 0.8 t CO2 per MWh for every site on earth.
That number is a reasonable diesel figure and a poor grid figure: India's grid
is 0.670, France's is 0.041. This module replaces the constant with a sourced,
per-country lookup so a report can say where its number came from.
"""
import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
GRID_CSV = os.path.join(DATA_DIR, "grid_emission_factors.csv")

# EPA GHG Emission Factors Hub 2025: 10.21 kg CO2 per US gallon of diesel.
DIESEL_KG_CO2_PER_LITRE = 2.70
# Litres of diesel per kWh for a mid-size genset at a good load factor. This is
# the sensitive input: an old or lightly loaded set can use 0.4-0.5 L/kWh.
DIESEL_LITRES_PER_KWH = 0.30
DIESEL_T_CO2_PER_MWH = DIESEL_KG_CO2_PER_LITRE * DIESEL_LITRES_PER_KWH   # ~0.81
WORLD_AVERAGE_GRID_T_CO2_PER_MWH = 0.44                                  # Ember 2025

GRID_SOURCE = {
    "name": "Ember yearly electricity data, via Our World in Data",
    "url": "https://ourworldindata.org/grapher/carbon-intensity-electricity",
    "licence": "CC BY 4.0 - Ember and Our World in Data",
}
DIESEL_SOURCE = {
    "name": "US EPA GHG Emission Factors Hub 2025 (10.21 kg CO2/gallon)",
    "url": "https://www.epa.gov/climateleadership/ghg-emission-factors-hub",
    "licence": "US Government work, public domain",
    "assumption": f"{DIESEL_LITRES_PER_KWH} L/kWh generator fuel consumption",
}
# India publishes its own audited factor, which beats a third-party estimate.
NATIONAL_OVERRIDES = {
    "IN": {
        "t_co2_per_mwh": 0.675,
        "year": 2026,
        "source": {
            "name": "CEA CO2 Baseline Database v22.0 (FY2025-26 weighted average)",
            "url": "https://cea.nic.in/cdm-co2-baseline-database/?lang=en",
            "licence": "Central Electricity Authority, Government of India",
        },
    },
}
_cache = {}


def _table():
    if not _cache:
        with open(GRID_CSV, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    _cache[row["iso2"].upper()] = (int(row["year"]),
                                                   float(row["t_co2_per_mwh"]))
                except (KeyError, TypeError, ValueError):
                    continue
    return _cache


def grid_factor(country_code):
    """Grid CO2 intensity in t/MWh, with the source it came from."""
    code = (country_code or "").upper()
    if code in NATIONAL_OVERRIDES:
        o = NATIONAL_OVERRIDES[code]
        return {"t_co2_per_mwh": o["t_co2_per_mwh"], "year": o["year"],
                "source": o["source"], "basis": "national regulator"}

    row = _table().get(code)
    if row:
        return {"t_co2_per_mwh": row[1], "year": row[0],
                "source": GRID_SOURCE, "basis": "country average"}
    return {"t_co2_per_mwh": WORLD_AVERAGE_GRID_T_CO2_PER_MWH, "year": 2025,
            "source": GRID_SOURCE, "basis": "world average fallback"}


def avoided_co2_t(annual_kwh, country_code=None, grid_share=1.0):
    """Tonnes CO2 avoided per year by displacing grid and/or diesel supply.

    grid_share is how much of the displaced supply was grid rather than diesel:
    1.0 for a grid-connected site, 0.0 for one running purely on a generator.
    """
    grid_share = min(max(float(grid_share), 0.0), 1.0)
    grid = grid_factor(country_code)
    mwh = annual_kwh / 1000.0
    blended = grid_share * grid["t_co2_per_mwh"] + (1 - grid_share) * DIESEL_T_CO2_PER_MWH
    return {
        "co2_avoided_t": round(mwh * blended, 1),
        "factor_t_per_mwh": round(blended, 4),
        "grid_share": grid_share,
        "grid_factor": grid,
        "diesel_factor": {"t_co2_per_mwh": round(DIESEL_T_CO2_PER_MWH, 4),
                          "source": DIESEL_SOURCE},
        "method": (f"{grid_share:.0%} grid at {grid['t_co2_per_mwh']} t/MWh "
                   f"({grid['basis']}) + {1 - grid_share:.0%} diesel at "
                   f"{DIESEL_T_CO2_PER_MWH:.2f} t/MWh"),
    }
