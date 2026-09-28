"""Estimated electricity consumption per grid cell.

The estimate is deliberately simple and stated in full, because no global
dataset gives city-level consumption:

    cell_kwh_day = population_share x national_residential_kwh_per_day
                   + industrial load from OSM footprints

Population share is the cell's people as a fraction of the area's people.
Industry comes from industry.py rather than being folded into per-capita use,
so an industrial estate with nobody living in it is not scored as empty.

Tier is "estimated" until calibration.py scales it to an official total, at
which point it becomes "calibrated" (see CITY_DATA.md: for Karnataka the
official figure exists only for a whole utility service area, never one city).
"""
import csv
import os

from . import TIER_ESTIMATED

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PER_CAPITA_CSV = os.path.join(DATA_DIR, "national_kwh_per_capita.csv")
# Share of a country's electricity that reaches homes rather than industry,
# transport or losses. Used to avoid double-counting the industrial load that
# industry.py already estimates from footprints.
RESIDENTIAL_SHARE = 0.25
FALLBACK_KWH_PER_CAPITA_YEAR = 3_500.0      # world average, if a country is missing


def load_per_capita(path=PER_CAPITA_CSV):
    """{ISO2: annual kWh per person} from the bundled table."""
    table = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                table[row["iso2"].upper()] = float(row["kwh_per_capita_year"])
            except (KeyError, TypeError, ValueError):
                continue
    return table


def estimate(cells, country_code, per_capita=None, residential_share=RESIDENTIAL_SHARE):
    """Add estimated daily kWh to every cell. Returns the method description."""
    table = per_capita if per_capita is not None else load_per_capita()
    kwh_year = table.get((country_code or "").upper())
    used_fallback = kwh_year is None
    if used_fallback:
        kwh_year = FALLBACK_KWH_PER_CAPITA_YEAR

    residential_per_person_day = kwh_year * residential_share / 365.0
    total_pop = sum(c.get("population", 0.0) for c in cells) or 1.0

    for cell in cells:
        residential = cell.get("population", 0.0) * residential_per_person_day
        industrial = cell.get("industrial_kwh_day", 0.0)
        cell["residential_kwh_day"] = round(residential, 1)
        cell["kwh_day"] = round(residential + industrial, 1)
        cell["population_share"] = round(cell.get("population", 0.0) / total_pop, 6)
        cell["tier"] = TIER_ESTIMATED

    return {
        "tier": TIER_ESTIMATED,
        "country_code": country_code,
        "kwh_per_capita_year": kwh_year,
        "residential_share": residential_share,
        "used_fallback_per_capita": used_fallback,
        "method": (
            f"residential = population x {kwh_year:,.0f} kWh/person/year x "
            f"{residential_share:g} residential share / 365; industrial from OSM "
            "footprint area. Both are assumptions, not measurements"),
    }


def totals(cells):
    """Whole-area totals, for the summary and for calibration checks."""
    daily = sum(c.get("kwh_day", 0.0) for c in cells)
    return {
        "population": round(sum(c.get("population", 0.0) for c in cells)),
        "kwh_day": round(daily, 1),
        "gwh_year": round(daily * 365 / 1e6, 1),
        "residential_kwh_day": round(sum(c.get("residential_kwh_day", 0.0) for c in cells), 1),
        "industrial_kwh_day": round(sum(c.get("industrial_kwh_day", 0.0) for c in cells), 1),
        "cells": len(cells),
    }
