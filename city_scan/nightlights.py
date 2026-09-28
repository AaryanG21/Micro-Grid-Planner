"""Night-time light radiance per cell, as a proxy for where demand actually is.

Population alone puts all the load in dormitory suburbs. Night lights pick up
commercial strips, industrial estates and lit main roads, so the two together
distribute a city's consumption better than either alone.

Source: VIIRS VNL v2.2 annual composite, 2024, repackaged as a cloud-optimised
GeoTIFF on Zenodo (DOI record 17294744, CC BY 4.0). That packaging matters: the
EOG original requires a login, while this one supports windowed reads, so we
pull only the ~80x75 pixels a city needs instead of a 64 MB file.
"""
import os

import numpy as np
import rasterio
from rasterio.windows import from_bounds

COG_URL = ("/vsicurl/https://zenodo.org/api/records/17294744/files/"
           "nightlights.average_viirs.v21_m_500m_s_20240101_20241231_go_epsg4326_v20250904.tif"
           "/content")
SCALE = 10.0            # stored int16; divide by 10 for nW/cm2/sr
SOURCE = {
    "name": "VIIRS VNL v2.2 annual composite 2024 (500 m), via Zenodo record 17294744",
    "url": "https://doi.org/10.5281/zenodo.17294744",
    "licence": ("CC BY 4.0 - Earth Observation Group, Payne Institute, "
                "Colorado School of Mines"),
    "units": "nW/cm2/sr",
    "resolution_m": 500,
}
# Keep GDAL from listing the whole bucket on every open. Note: do NOT set
# CPL_VSIL_CURL_ALLOWED_EXTENSIONS here - the Zenodo URL ends in /content
# rather than .tif, and the extension filter rejects it outright.
_GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "2",
}


def radiance_for_cells(cells, bbox, url=None):
    """Add mean night-light radiance to each cell. Returns the source dict.

    One windowed read covers the whole city, then cells are cut out of that
    array in memory - opening the remote COG once per cell would be hundreds
    of HTTP round trips.
    """
    for cell in cells:
        cell.setdefault("radiance", 0.0)

    os.environ.update(_GDAL_ENV)
    south, west, north, east = bbox
    with rasterio.open(url or COG_URL) as ds:
        window = from_bounds(west, south, east, north, ds.transform)
        data = ds.read(1, window=window).astype("float32") / SCALE
        win_transform = ds.window_transform(window)

    data = np.clip(data, 0, None)
    inv = ~win_transform                      # world -> pixel for this window
    rows, cols = data.shape

    for cell in cells:
        s, w, n, e = cell["bounds"]
        c0, r0 = inv * (w, n)
        c1, r1 = inv * (e, s)
        r0, r1 = sorted((int(np.floor(r0)), int(np.ceil(r1))))
        c0, c1 = sorted((int(np.floor(c0)), int(np.ceil(c1))))
        patch = data[max(0, r0):min(rows, r1), max(0, c0):min(cols, c1)]
        cell["radiance"] = round(float(patch.mean()) if patch.size else 0.0, 3)

    return SOURCE


def demand_weights(cells, population_weight=0.6):
    """Blend population and radiance into one 0-1 weight per cell.

    Both are normalised to their own totals first, so the blend is not
    dominated by whichever happens to have larger raw numbers. A cell with
    people but no light (unlit housing) and a cell with light but no residents
    (an industrial park at night) both still get weight.
    """
    pop_total = sum(c.get("population", 0.0) for c in cells) or 1.0
    rad_total = sum(c.get("radiance", 0.0) * c.get("area_sqkm", 1.0) for c in cells) or 1.0
    light_weight = 1.0 - population_weight

    for cell in cells:
        pop_share = cell.get("population", 0.0) / pop_total
        rad_share = (cell.get("radiance", 0.0) * cell.get("area_sqkm", 1.0)) / rad_total
        cell["demand_weight"] = round(population_weight * pop_share
                                      + light_weight * rad_share, 8)
    return cells
