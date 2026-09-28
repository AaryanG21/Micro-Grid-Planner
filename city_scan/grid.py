"""The analysis grid: square-ish cells covering a city, clipped to its boundary.

Everything downstream (population, consumption, industry, emissions, scoring)
is expressed per cell, so this module defines the unit of analysis. Cells are
built in plain lat/lon; at city scale the distortion from not projecting is
under a percent, and staying in EPSG:4326 keeps the GeoJSON the map consumes
free of reprojection.
"""
import math

from shapely.geometry import box, shape

DEFAULT_CELL_M = 500
M_PER_DEG_LAT = 110_574.0


def _deg_per_m(lat):
    """Degrees of lat/lon per metre at this latitude."""
    lon_scale = max(math.cos(math.radians(lat)), 0.01)
    return 1.0 / M_PER_DEG_LAT, 1.0 / (111_320.0 * lon_scale)


def make_grid(bbox, geometry=None, cell_m=DEFAULT_CELL_M, max_cells=20_000):
    """Split bbox into ~cell_m squares, keeping those inside geometry.

    bbox is (south, west, north, east). geometry is the city's GeoJSON polygon;
    when given, a cell is kept only if it intersects the boundary, and its
    `coverage` records how much of the cell falls inside (so a cell straddling
    the city edge can be weighted down rather than counted whole).

    Raises ValueError if the request would exceed max_cells, rather than
    quietly producing a grid too big to process or send to the browser.
    """
    south, west, north, east = bbox
    if north <= south or east <= west:
        raise ValueError(f"Invalid bbox {bbox}")

    mid_lat = (south + north) / 2
    dlat_per_m, dlon_per_m = _deg_per_m(mid_lat)
    dlat = cell_m * dlat_per_m
    dlon = cell_m * dlon_per_m

    rows = max(1, math.ceil((north - south) / dlat))
    cols = max(1, math.ceil((east - west) / dlon))
    if rows * cols > max_cells:
        raise ValueError(
            f"{rows}x{cols} = {rows * cols} cells exceeds max_cells={max_cells}; "
            f"use a larger cell_m (current {cell_m} m)")

    boundary = shape(geometry) if geometry else None
    if boundary is not None and not boundary.is_valid:
        boundary = boundary.buffer(0)          # fix self-intersecting OSM rings

    cells = []
    for r in range(rows):
        cs, cn = south + r * dlat, min(south + (r + 1) * dlat, north)
        for c in range(cols):
            cw, ce = west + c * dlon, min(west + (c + 1) * dlon, east)
            poly = box(cw, cs, ce, cn)
            coverage = 1.0
            if boundary is not None:
                if not boundary.intersects(poly):
                    continue
                coverage = poly.intersection(boundary).area / poly.area
                if coverage < 0.01:            # a slither on the border: skip
                    continue
            cells.append({
                "id": f"r{r}c{c}",
                "row": r, "col": c,
                "bounds": [round(cs, 6), round(cw, 6), round(cn, 6), round(ce, 6)],
                "lat": round((cs + cn) / 2, 6),
                "lon": round((cw + ce) / 2, 6),
                "area_sqkm": round((cell_m / 1000.0) ** 2 * coverage, 4),
                "coverage": round(coverage, 3),
            })
    if not cells:
        raise ValueError("No cells intersect the city boundary")
    return {"cell_size_m": cell_m, "rows": rows, "cols": cols, "cells": cells}


def to_geojson(cells, properties=("population", "kwh_day", "tier")):
    """Cells as a GeoJSON FeatureCollection for Leaflet."""
    features = []
    for cell in cells:
        s, w, n, e = cell["bounds"]
        features.append({
            "type": "Feature",
            "id": cell["id"],
            "geometry": {"type": "Polygon", "coordinates": [[
                [w, s], [e, s], [e, n], [w, n], [w, s]]]},
            "properties": {k: cell[k] for k in properties if k in cell},
        })
    return {"type": "FeatureCollection", "features": features}
