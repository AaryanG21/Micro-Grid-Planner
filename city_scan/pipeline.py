"""Run every layer for one city and assemble the result.

Design rule: a city scan must not fail because one source is down. Each layer
runs inside run_layer(), which records an error against that layer and lets the
rest continue, so a city with no emissions data still returns population,
consumption and industry, and says what is missing and why.
"""
import time
import traceback

from . import TIER_ESTIMATED, boundary, calibration, consumption, emissions
from . import grid, industry, nightlights, population, regional, scoring


def run_layer(result, name, fn, *args, **kwargs):
    """Run one layer; on failure record it and carry on."""
    started = time.monotonic()
    try:
        value = fn(*args, **kwargs)
        result["layer_status"][name] = {
            "ok": True, "seconds": round(time.monotonic() - started, 1)}
        return value
    except Exception as exc:                        # noqa: BLE001 - by design
        result["layer_status"][name] = {
            "ok": False, "seconds": round(time.monotonic() - started, 1),
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }
        result.setdefault("_tracebacks", {})[name] = traceback.format_exc()[-1500:]
        return None


def analyze_city(name=None, lat=None, lon=None, cell_m=1000, year=None,
                 download_tiles=True, top_n=20):
    """Analyse one city. Always returns a result; check layer_status."""
    started = time.monotonic()
    result = {"layer_status": {}, "sources": {}, "cell_size_m": cell_m}

    city = boundary.get_city(name=name, lat=lat, lon=lon)   # fatal if this fails
    result["city"] = {k: city[k] for k in
                      ("name", "display_name", "lat", "lon", "bbox", "country_code")}

    g = grid.make_grid(city["bbox"], city["geometry"], cell_m=cell_m)
    cells = g["cells"]
    result.update(rows=g["rows"], cols=g["cols"], cell_count=len(cells))

    src = run_layer(result, "population", population.population_for_cells,
                    cells, city["bbox"], download=download_tiles)
    if src:
        result["sources"]["population"] = src

    src = run_layer(result, "nightlights", nightlights.radiance_for_cells,
                    cells, city["bbox"])
    if src:
        result["sources"]["nightlights"] = src
    nightlights.demand_weights(cells)

    ind = run_layer(result, "industry", industry.fetch_industry, city["bbox"])
    if ind:
        industry.assign_to_cells(cells, ind["sites"])
        result["industry"] = {k: ind[k] for k in
                              ("count", "named_count", "total_kwh_day", "method")}
        result["sources"]["industry"] = ind["source"]
        # The biggest sites are worth showing by name; the tail is noise.
        result["industry"]["top_sites"] = ind["sites"][:50]

    em = run_layer(result, "emissions", emissions.fetch_emissions,
                   bbox=city["bbox"], **({"year": year} if year else {}))
    if em:
        emissions.assign_to_cells(cells, em["sources"])
        result["emissions"] = {k: em[k] for k in
                               ("fua_name", "overlapping_areas", "year", "count",
                                "facility_count", "total_co2e_t", "facility_co2e_t")}
        result["sources"]["emissions"] = em["source"]
        result["emissions"]["top_sources"] = em["sources"][:50]

    method = consumption.estimate(cells, city["country_code"])
    result["consumption"] = {**method, "totals": consumption.totals(cells)}
    result["tier"] = TIER_ESTIMATED

    # Official data, where a region publishes it.
    module = regional.lookup(city["country_code"], _state_of(city))
    official = module.official_total(city["name"]) if module else None
    if official:
        served = run_layer(result, "service_area_population",
                           module.service_area_population, city["name"])
        cal = run_layer(
            result, "calibration", calibration.apply, cells,
            official["official_residential_mwh_year"],
            (served or {}).get("population"),
            official["area_name"], official["source"], official["scope"],
            official["financial_year"]) if served else None
        if cal:
            result["calibration"] = {**cal, "utility": official["utility"],
                                     "districts": official["districts"],
                                     "population_by_district": served["by_district"]}
            result["consumption"]["totals"] = consumption.totals(cells)
            result["tier"] = cal["tier"]
            result["sources"]["official_consumption"] = official["source"]
    else:
        result["layer_status"]["calibration"] = {
            "ok": False, "seconds": 0.0,
            "error": "No official consumption data registered for this region"}

    result["scoring"] = scoring.score_cells(cells, top_n=top_n)
    result["cells"] = cells
    result["seconds"] = round(time.monotonic() - started, 1)
    result["ok_layers"] = sorted(k for k, v in result["layer_status"].items() if v["ok"])
    result["failed_layers"] = sorted(
        k for k, v in result["layer_status"].items() if not v["ok"])
    return result


def _state_of(city):
    """State name from the Nominatim display string, for the regional registry."""
    parts = [p.strip() for p in (city.get("display_name") or "").split(",")]
    known = {"Karnataka"}
    return next((p for p in parts if p in known), None)


def summary(result):
    """The result without per-cell data, for the list/summary endpoint."""
    return {k: v for k, v in result.items()
            if k not in ("cells", "_tracebacks")}
