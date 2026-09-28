"""City boundary lookup via Nominatim (the same service App.jsx searches with)."""
import time

import requests

from site_scan import HEADERS

NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
# Nominatim's usage policy: at most 1 request/second from one application.
_MIN_INTERVAL_S = 1.0
_last_call = [0.0]


def _get(url, params):
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    _last_call[0] = time.monotonic()
    r.raise_for_status()
    return r.json()


def _shape(entry):
    """Normalise one Nominatim hit into the dict the pipeline passes around."""
    south, north, west, east = (float(v) for v in entry["boundingbox"])
    return {
        "name": entry.get("name") or entry["display_name"].split(",")[0],
        "display_name": entry["display_name"],
        "osm_id": entry.get("osm_id"),
        "lat": float(entry["lat"]),
        "lon": float(entry["lon"]),
        # (south, west, north, east), matching Overpass's bbox order.
        "bbox": [south, west, north, east],
        "geometry": entry.get("geojson"),
        "country_code": (entry.get("address") or {}).get("country_code", "").upper(),
    }


def _is_area(hit):
    """True for a hit with a real polygon.

    Searching "Chikkaballapur district" otherwise matches the
    Nelamangala-Chikkaballapur highway, whose LineString intersects no grid
    cell and silently produces an empty area. jsonv2 does not return "class",
    so the polygon test is the whole filter: roads come back as LineStrings.
    """
    return (hit.get("geojson") or {}).get("type") in ("Polygon", "MultiPolygon")


def _rank(hit):
    """Sort key: administrative boundaries first, then larger areas.

    A polygon alone is not enough. "Bengaluru Rural district" matches a patch
    of scrub inside a radio station compound before it matches the district,
    and that patch holds a thousand people instead of a million.
    """
    south, north, west, east = (float(v) for v in hit["boundingbox"])
    span = (north - south) * (east - west)
    return (0 if hit.get("type") == "administrative" else 1, -span)


def get_city(name=None, lat=None, lon=None, require_area=True, require_admin=False):
    """Look up a city by name, or find the city containing a point.

    Returns a dict with bbox, boundary GeoJSON and ISO country code. Raises
    ValueError when nothing matches, so the endpoint can answer 404.
    """
    params = {"format": "jsonv2", "polygon_geojson": 1, "addressdetails": 1, "limit": 10}
    if name:
        hits = _get(NOMINATIM_SEARCH, {**params, "q": name})
        areas = sorted((h for h in hits if _is_area(h)), key=_rank)
        if require_admin:
            # Districts and other official areas must match a real boundary,
            # never a same-named polygon that happens to rank first. The
            # caller then tries another spelling instead of taking the wrong one.
            areas = [h for h in areas if h.get("type") == "administrative"]
            if not areas:
                raise ValueError(f"No administrative boundary found for {name!r}")
        if not areas and require_area:
            raise ValueError(f"No administrative area found for {name!r}")
        hits = areas or hits
        if not hits:
            raise ValueError(f"No place found for {name!r}")
        return _shape(hits[0])

    if lat is None or lon is None:
        raise ValueError("Pass either name, or lat and lon")
    hit = _get(NOMINATIM_REVERSE, {**params, "lat": lat, "lon": lon, "zoom": 10})
    if "error" in hit:
        raise ValueError(f"No place found at {lat},{lon}")
    return _shape(hit)
