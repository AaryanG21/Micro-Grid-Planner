"""Scale estimated demand to an official published total.

The constraint discovered in Phase 0 (CITY_DATA.md): no Indian utility
publishes city-level sales. BESCOM reports one total for eight districts,
MESCOM one for four. So calibration happens at the level the data exists at -
a whole utility service area - and the city inherits the resulting scale
factor.

What that means, stated plainly for the UI: we trust the official TOTAL, and we
trust our own model only for how that total is DISTRIBUTED across the service
area. The pre-calibration error is kept, because the gap between our estimate
and the official figure is the honest measure of how good the model is.
"""
from . import TIER_CALIBRATED


def apply(cells, official_residential_mwh_year, service_area_population,
          area_name, source, scope="utility service area", financial_year=None):
    """Replace estimated residential demand with the official per-capita rate.

    The official total covers a whole service area, and the cells cover one
    city inside it, so the two cannot be equated directly - doing that inflates
    the city by the ratio of their sizes. What IS transferable is the rate per
    person: official domestic sales divided by the people the utility serves.
    That rate then drives each cell through its own population.

    Only residential demand is calibrated. Industrial load stays as estimated
    from OSM footprints, because no official figure exists for how industry is
    distributed inside the service area.
    """
    if not official_residential_mwh_year or official_residential_mwh_year <= 0:
        raise ValueError("official_residential_mwh_year must be positive")
    if not service_area_population or service_area_population <= 0:
        raise ValueError("service_area_population must be positive")

    official_kwh_per_capita_year = (official_residential_mwh_year * 1000.0
                                    / service_area_population)
    official_per_capita_day = official_kwh_per_capita_year / 365.0

    before_residential = sum(c.get("residential_kwh_day", 0.0) for c in cells)
    city_population = sum(c.get("population", 0.0) for c in cells)

    for cell in cells:
        residential = cell.get("population", 0.0) * official_per_capita_day
        cell["residential_kwh_day"] = round(residential, 1)
        cell["kwh_day"] = round(residential + cell.get("industrial_kwh_day", 0.0), 1)
        cell["tier"] = TIER_CALIBRATED

    after_residential = sum(c.get("residential_kwh_day", 0.0) for c in cells)
    # How far the global model was off, per person, against the real utility
    # figure. This is the accuracy number worth quoting.
    error_pct = ((before_residential - after_residential) / after_residential * 100
                 if after_residential else 0.0)

    return {
        "tier": TIER_CALIBRATED,
        "calibrated": "residential demand only",
        "area_name": area_name,
        "scope": scope,
        "financial_year": financial_year,
        "official_residential_mwh_year": round(official_residential_mwh_year, 1),
        "service_area_population": round(service_area_population),
        "official_kwh_per_capita_year": round(official_kwh_per_capita_year, 1),
        "city_population": round(city_population),
        "city_share_of_service_area_pct": round(
            city_population / service_area_population * 100, 1),
        "estimated_residential_kwh_day_before": round(before_residential, 1),
        "calibrated_residential_kwh_day": round(after_residential, 1),
        "pre_calibration_error_pct": round(error_pct, 1),
        "source": source,
        "caveat": (
            f"The official figure covers the whole {scope} ({area_name}), never this "
            "city alone. It is applied here as demand per person, so the city total "
            "is only as good as the assumption that people inside the city use "
            "electricity at the service-area average rate. Industrial load remains "
            "an estimate from OSM footprints."),
    }


def coverage_note(city_name, area_name, city_population, area_population=None):
    """Explain the mismatch between a city and its utility's service area."""
    note = (f"{city_name} sits inside the {area_name} service area. "
            "No published figure isolates the city.")
    if area_population:
        share = city_population / area_population * 100 if area_population else None
        note += f" The city holds about {share:.0f}% of the service area's people."
    return note
