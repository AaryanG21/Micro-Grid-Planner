"""Population per grid cell, from GHSL GHS-POP (see CITY_DATA.md).

GHSL ships the world as 10 deg x 10 deg tiles at 3 arc-seconds (~93 m at
Bengaluru's latitude), each a 160 MB zip. A tile is downloaded once and cached
on disk, because one tile covers many cities. WorldPop was rejected: its server
advertises range support and then ignores it (see CITY_DATA.md).
"""
import os
import zipfile

import numpy as np
import rasterio
import requests
from rasterio.windows import from_bounds

from site_scan import HEADERS

TILE_URL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
            "GHS_POP_GLOBE_R2023A/GHS_POP_E2025_GLOBE_R2023A_4326_3ss/V1-0/tiles/"
            "GHS_POP_E2025_GLOBE_R2023A_4326_3ss_V1_0_R{row}_C{col}.zip")
CACHE_DIR = os.environ.get(
    "CITY_SCAN_TILE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tiles"))
SOURCE = {
    "name": "GHSL GHS-POP R2023A (epoch 2025, 3 arc-seconds)",
    "url": "https://human-settlement.emergency.copernicus.eu/download.php",
    "licence": "CC BY 4.0 - European Commission, Joint Research Centre",
    "resolution_m": 93,
}


def tile_ids(bbox):
    """GHSL tile (row, col) pairs covering bbox = (south, west, north, east)."""
    south, west, north, east = bbox
    ids = set()
    for lat in (south, north):
        for lon in (west, east):
            col = int((lon + 180) // 10) + 1
            row = int((90 - lat) // 10) + 1
            ids.add((row, col))
    return sorted(ids)


def tile_path(row, col, download=True):
    """Local .tif for one tile, fetching and unzipping it on first use."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = f"GHS_POP_E2025_GLOBE_R2023A_4326_3ss_V1_0_R{row}_C{col}"
    tif = os.path.join(CACHE_DIR, f"{name}.tif")
    if os.path.exists(tif):
        return tif
    if not download:
        raise FileNotFoundError(tif)

    zip_path = os.path.join(CACHE_DIR, f"{name}.zip")
    url = TILE_URL.format(row=row, col=col)
    with requests.get(url, headers=HEADERS, stream=True, timeout=(15, 120)) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    with zipfile.ZipFile(zip_path) as zf:
        member = next(n for n in zf.namelist() if n.endswith(".tif"))
        with zf.open(member) as src, open(tif, "wb") as dst:
            dst.write(src.read())
    os.remove(zip_path)
    return tif


def population_in_areas(area_names, cell_m=5000, download=True, get_city=None,
                        make_grid=None):
    """Total population of several named areas (e.g. a utility's districts).

    Used to get the denominator for service-area calibration: an official sales
    total divided by the people it actually serves. Coarse cells keep this to a
    few seconds; at 5 km the boundary clipping is what costs accuracy, not the
    93 m raster underneath.
    """
    if get_city is None:
        from .boundary import get_city
    if make_grid is None:
        from .grid import make_grid

    per_area, total = {}, 0.0
    for name in area_names:
        # District naming varies ("X district" vs plain "X"); try both before
        # giving up, rather than letting one district silently drop out.
        variants = [name, name.replace(" district", "")]
        place = None
        for variant in variants:
            try:
                place = get_city(name=variant, require_admin=True)
                break
            except (ValueError, KeyError):
                continue
        if place is None:
            raise ValueError(f"No administrative area found for {name!r}")
        grid = make_grid(place["bbox"], place["geometry"], cell_m=cell_m,
                         max_cells=40_000)
        population_for_cells(grid["cells"], place["bbox"], download=download)
        area_pop = sum(c["population"] for c in grid["cells"])
        per_area[name] = round(area_pop)
        total += area_pop
    return {"total": round(total), "by_area": per_area,
            "cell_size_m": cell_m, "source": SOURCE}


def population_for_cells(cells, bbox, download=True):
    """Add a "population" key to every cell. Returns the source description.

    Cells are read tile by tile: each tile is opened once and every cell it
    covers is summed from it, so a city never opens the same 160 MB file twice.
    """
    for cell in cells:
        cell.setdefault("population", 0.0)

    for row, col in tile_ids(bbox):
        try:
            path = tile_path(row, col, download=download)
        except (requests.RequestException, FileNotFoundError, StopIteration) as exc:
            raise RuntimeError(f"GHSL tile R{row}_C{col} unavailable: {exc}") from exc

        with rasterio.open(path) as ds:
            tb = ds.bounds
            for cell in cells:
                s, w, n, e = cell["bounds"]
                # Skip cells this tile does not cover.
                if e <= tb.left or w >= tb.right or n <= tb.bottom or s >= tb.top:
                    continue
                window = from_bounds(max(w, tb.left), max(s, tb.bottom),
                                     min(e, tb.right), min(n, tb.top), ds.transform)
                data = ds.read(1, window=window, boundless=False)
                if data.size:
                    # GHS-POP is persons per pixel; nodata is negative.
                    cell["population"] += float(np.clip(data, 0, None).sum())

    for cell in cells:
        cell["population"] = round(cell["population"], 1)
    return SOURCE
