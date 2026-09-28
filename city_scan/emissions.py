"""CO2e emissions per city and per grid cell, from Climate TRACE.

The v7 API has no bbox filter on emissions: you resolve a bbox (or a name) to a
Functional Urban Area id via /v7/cities, then query /v7/sources with that
cityId. v6's /assets still responds but is undocumented, so we build on v7.

FUAs are GHS metropolitan areas, not legal city limits, so a city's emissions
total can cover more ground than its Nominatim boundary. The returned source
records say so via "fua_name".
"""
import requests

from site_scan import HEADERS

BASE = "https://api.climatetrace.org/v7"
SOURCE = {
    "name": "Climate TRACE v7",
    "url": "https://climatetrace.org",
    "licence": "CC BY 4.0 - Climate TRACE (https://creativecommons.org/licenses/by/4.0/)",
    "note": ("city extents are GHS Functional Urban Areas, which may be larger "
             "than the municipal boundary"),
}
DEFAULT_GAS = "co2e_100yr"          # tonnes CO2e, 100-year GWP
# /v7/sources carries city/state data from 2021 onward only.
DEFAULT_YEAR = 2024


def find_city_id(bbox=None, name=None):
    """Resolve a bbox or name to a Climate TRACE FUA id, or None if unmatched."""
    if bbox:
        south, west, north, east = bbox
        params = {"bbox": f"{west},{south},{east},{north}"}
    elif name:
        params = {"name": name}
    else:
        raise ValueError("Pass bbox or name")
    r = requests.get(f"{BASE}/cities", params=params, headers=HEADERS, timeout=45)
    r.raise_for_status()
    hits = r.json()
    if not hits:
        return None
    # A bbox can straddle several FUAs; the largest match is listed first.
    return {"id": hits[0]["id"], "name": hits[0]["name"],
            "others": [h["name"] for h in hits[1:]]}


def fetch_emissions(bbox=None, name=None, year=DEFAULT_YEAR, gas=DEFAULT_GAS, limit=1000):
    """Facility-level emissions for the city covering bbox.

    Returns sources plus the city total. Raises LookupError when Climate TRACE
    has no city covering the area, so the pipeline can record that layer as
    unavailable instead of failing the whole scan.
    """
    city = find_city_id(bbox=bbox, name=name)
    if not city:
        raise LookupError("No Climate TRACE city covers this area")

    r = requests.get(f"{BASE}/sources", headers=HEADERS, timeout=90,
                     params={"cityId": city["id"], "year": year,
                             "gas": gas, "limit": limit})
    r.raise_for_status()
    rows = r.json()

    sources = []
    for row in rows:
        centroid = row.get("centroid") or {}
        if centroid.get("latitude") is None:
            continue
        sources.append({
            "id": row.get("id"),
            "name": row.get("name"),
            "sector": row.get("sector"),
            "subsector": row.get("subsector"),
            # city-aggregation rows are modelled city totals (e.g. all road
            # transport), not individual plants. Kept, but flagged, so the map
            # can show them differently from a real facility.
            "is_aggregate": row.get("sourceType") == "city-aggregation",
            "lat": round(float(centroid["latitude"]), 6),
            "lon": round(float(centroid["longitude"]), 6),
            "co2e_t": round(float(row.get("emissionsQuantity") or 0), 1),
            "year": row.get("year", year),
        })
    sources.sort(key=lambda s: -s["co2e_t"])

    facilities = [s for s in sources if not s["is_aggregate"]]
    return {
        "fua_id": city["id"], "fua_name": city["name"],
        "overlapping_areas": city["others"],
        "year": year, "gas": gas,
        "sources": sources,
        "count": len(sources),
        "facility_count": len(facilities),
        "total_co2e_t": round(sum(s["co2e_t"] for s in sources), 1),
        "facility_co2e_t": round(sum(s["co2e_t"] for s in facilities), 1),
        "source": SOURCE,
    }


def assign_to_cells(cells, sources, include_aggregates=False):
    """Add per-cell CO2e from facility centroids.

    City-aggregation rows are excluded by default: they carry one centroid for
    a whole city's road traffic, so binning them into one cell would invent a
    hotspot that does not exist.
    """
    for cell in cells:
        cell.setdefault("co2e_t", 0.0)
        cell.setdefault("emitter_count", 0)

    for src in sources:
        if src["is_aggregate"] and not include_aggregates:
            continue
        for cell in cells:
            s, w, n, e = cell["bounds"]
            if s <= src["lat"] < n and w <= src["lon"] < e:
                cell["co2e_t"] += src["co2e_t"]
                cell["emitter_count"] += 1
                break

    for cell in cells:
        cell["co2e_t"] = round(cell["co2e_t"], 1)
    return cells
