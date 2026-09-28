"""Industrial sites in a city, from OpenStreetMap.

Three of the four industry sources the plan calls for come from OSM in one
query: industrial land use, industrial buildings, and the company names tagged
on them. Climate TRACE's large emitters are handled in emissions.py, and
official industrial estates (KIADB and friends) are per-region, so they live
under regional/.

Load is estimated the same way site_scan.py does it, so the two layers agree:
BENCHMARKS["industrial"] per building, with a floor-area fallback for anything
big and untyped.
"""
from site_scan import AREA_INTENSITY, BENCHMARKS, overpass_query, polygon_area_sqm

SOURCE = {
    "name": "OpenStreetMap (Overpass API)",
    "url": "https://www.openstreetmap.org/copyright",
    "licence": "ODbL 1.0 - (c) OpenStreetMap contributors",
}
# One query for the whole city: ~2,200 elements for Bengaluru in ~10 s.
QUERY = """
[out:json][timeout:90];
(
  way["landuse"="industrial"]({s},{w},{n},{e});
  relation["landuse"="industrial"]({s},{w},{n},{e});
  way["building"~"^(industrial|factory|warehouse)$"]({s},{w},{n},{e});
  way["man_made"="works"]({s},{w},{n},{e});
);
out geom tags;
"""


def _ring(element):
    geom = element.get("geometry")
    if not geom:
        members = element.get("members") or []
        geom = next((m.get("geometry") for m in members
                     if m.get("role") == "outer" and m.get("geometry")), None)
    return [(p["lat"], p["lon"]) for p in geom] if geom else None


def _centroid(ring):
    return (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))


def fetch_industry(bbox, deadline_s=180):
    """Industrial sites within bbox = (south, west, north, east)."""
    south, west, north, east = bbox
    elements = overpass_query(
        QUERY.format(s=south, w=west, n=north, e=east), deadline_s=deadline_s)

    sites = []
    for el in elements:
        ring = _ring(el)
        if not ring or len(ring) < 3:
            continue
        tags = el.get("tags", {})
        area = polygon_area_sqm(ring)
        if area < 50:                       # noise: mapping slivers
            continue
        lat, lon = _centroid(ring)
        is_zone = tags.get("landuse") == "industrial"
        try:
            levels = max(1, int(float(tags.get("building:levels"))))
        except (TypeError, ValueError):
            levels = 1

        if is_zone:
            # A zone is land, not a building: only part of it is built on, and
            # only some of that is powered process load. 30% is an assumption.
            kwh_day = area * 0.30 * AREA_INTENSITY
            kind = "industrial_zone"
        else:
            kwh_day = max(BENCHMARKS["industrial"]["kwh_day"],
                          area * levels * AREA_INTENSITY)
            kind = "industrial_building"

        sites.append({
            "id": el.get("id"),
            "kind": kind,
            "name": tags.get("name"),
            "operator": tags.get("operator"),
            "sector": tags.get("industrial") or tags.get("craft") or tags.get("product"),
            "footprint_sqm": round(area, 1),
            "levels": levels,
            "lat": round(lat, 6), "lon": round(lon, 6),
            "est_kwh_day": round(kwh_day, 1),
            "source": "osm",
        })

    sites.sort(key=lambda s: -s["est_kwh_day"])
    return {
        "sites": sites,
        "count": len(sites),
        "named_count": sum(1 for s in sites if s["name"]),
        "total_kwh_day": round(sum(s["est_kwh_day"] for s in sites), 1),
        "method": ("industrial load estimated from OSM footprint area at "
                   f"{AREA_INTENSITY} kWh/m2/day (zones assumed 30% built up). "
                   "An assumption, not a measurement"),
        "source": SOURCE,
    }


def assign_to_cells(cells, sites):
    """Add industrial load and site counts to each cell by centroid."""
    for cell in cells:
        cell.setdefault("industrial_kwh_day", 0.0)
        cell.setdefault("industrial_sites", 0)
        cell.setdefault("industrial_sqm", 0.0)

    index = {}
    for cell in cells:
        s, w, n, e = cell["bounds"]
        index[cell["id"]] = (s, w, n, e, cell)

    for site in sites:
        for s, w, n, e, cell in index.values():
            if s <= site["lat"] < n and w <= site["lon"] < e:
                cell["industrial_kwh_day"] += site["est_kwh_day"]
                cell["industrial_sites"] += 1
                cell["industrial_sqm"] += site["footprint_sqm"]
                break

    for cell in cells:
        cell["industrial_kwh_day"] = round(cell["industrial_kwh_day"], 1)
        cell["industrial_sqm"] = round(cell["industrial_sqm"], 1)
    return cells
