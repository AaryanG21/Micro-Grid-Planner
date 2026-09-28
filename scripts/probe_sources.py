"""
Phase 0 probe: can we actually reach every data source the city layer needs,
and at what resolution and licence? Results go into CITY_DATA.md by hand.

Run:  .venv/bin/python scripts/probe_sources.py
Nothing here is imported by the app. It only reads remote sources.
"""
import json
import sys
import time

import requests

sys.path.insert(0, __file__.rsplit("/", 2)[0])
from site_scan import HEADERS, overpass_query  # noqa: E402

# Bengaluru pilot bbox (south, west, north, east).
BLR = (12.83, 77.45, 13.14, 77.78)
OUT = {}


def probe(name):
    """Record one source's outcome without letting a failure stop the rest."""
    def wrap(fn):
        t = time.time()
        try:
            result = fn()
            OUT[name] = {"ok": True, "seconds": round(time.time() - t, 1), **result}
        except Exception as exc:                      # noqa: BLE001 - report, don't raise
            OUT[name] = {"ok": False, "seconds": round(time.time() - t, 1),
                         "error": f"{type(exc).__name__}: {exc}"[:300]}
        print(json.dumps({name: OUT[name]}, indent=1)[:600], flush=True)
        return fn
    return wrap


@probe("climate_trace")
def _climate_trace():
    """Facility-level CO2e. Check bbox filtering and which API version works."""
    out = {}
    for ver in ("v6", "v7"):
        r = requests.get(f"https://api.climatetrace.org/{ver}/assets",
                         params={"countries": "IND", "limit": 5}, timeout=60)
        out[ver] = r.status_code
        if r.ok and ver == "v6":
            assets = r.json().get("assets", [])
            out["sample"] = [a.get("Name") for a in assets[:3]]
    # Does it support a bounding box?
    rb = requests.get("https://api.climatetrace.org/v6/assets",
                      params={"bbox": f"{BLR[1]},{BLR[0]},{BLR[3]},{BLR[2]}", "limit": 5},
                      timeout=60)
    out["bbox_status"] = rb.status_code
    out["bbox_count"] = len(rb.json().get("assets", [])) if rb.ok else None
    return out


@probe("overpass_industry")
def _overpass_industry():
    """City-wide industrial query: does it complete, and how long does it take?"""
    q = (f"[out:json][timeout:60];("
         f'way["landuse"="industrial"]({BLR[0]},{BLR[1]},{BLR[2]},{BLR[3]});'
         f'way["building"~"^(industrial|factory|warehouse)$"]({BLR[0]},{BLR[1]},{BLR[2]},{BLR[3]});'
         f");out center tags;")
    els = overpass_query(q, deadline_s=180)
    named = [e["tags"].get("name") for e in els if e.get("tags", {}).get("name")]
    return {"elements": len(els), "named": len(named), "sample": named[:5]}


@probe("worldpop")
def _worldpop():
    """Population raster: is there a direct GeoTIFF URL, and does it accept
    HTTP range requests (so we can read one city window instead of ~1 GB)?"""
    r = requests.get("https://hub.worldpop.org/rest/data/pop/wpgp",
                     params={"iso3": "IND"}, timeout=60)
    r.raise_for_status()
    rows = r.json()["data"]
    latest = sorted(rows, key=lambda d: d.get("popyear", ""))[-1]
    files = latest.get("files") or []
    url = files[0] if isinstance(files, list) and files else None
    out = {"title": latest.get("title", "")[:80], "year": latest.get("popyear"),
           "license": latest.get("license", "")[:80], "url": url}
    if url:
        h = requests.head(url, timeout=60, allow_redirects=True)
        out["head_status"] = h.status_code
        out["size_mb"] = round(int(h.headers.get("Content-Length", 0)) / 1e6, 1)
        out["accept_ranges"] = h.headers.get("Accept-Ranges")
    return out


@probe("ghsl_population")
def _ghsl():
    """Fallback population source if WorldPop range reads don't work."""
    url = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
           "GHS_POP_GLOBE_R2023A/GHS_POP_E2025_GLOBE_R2023A_4326_3ss/V1-0/"
           "GHS_POP_E2025_GLOBE_R2023A_4326_3ss_V1_0.zip")
    h = requests.head(url, timeout=60, allow_redirects=True)
    return {"head_status": h.status_code,
            "size_mb": round(int(h.headers.get("Content-Length", 0)) / 1e6, 1),
            "accept_ranges": h.headers.get("Accept-Ranges")}


@probe("nightlights")
def _nightlights():
    """VIIRS night lights. EOG needs registration; check what is open."""
    out = {}
    for name, url in {
        "eog_root": "https://eogdata.mines.edu/nighttime_light/annual/v22/",
        "eog_token_api": "https://eogdata.mines.edu/eog-ws/token/",
        "earthengine_note": "https://developers.google.com/earth-engine/datasets/catalog/NOAA_VIIRS_DNB_ANNUAL_V22",
    }.items():
        try:
            r = requests.get(url, timeout=45, headers=HEADERS)
            out[name] = r.status_code
        except Exception as exc:                      # noqa: BLE001
            out[name] = f"{type(exc).__name__}"
    return out


@probe("kerc_bescom")
def _kerc():
    """KERC site: find tariff-order PDFs to see how detailed the sales data is."""
    r = requests.get("https://kerc.karnataka.gov.in/info-2/Tariff+Orders/en",
                     timeout=60, headers=HEADERS)
    out = {"status": r.status_code, "bytes": len(r.content)}
    if r.ok:
        import re
        pdfs = re.findall(r'href="([^"]+\.pdf)"', r.text, flags=re.I)
        out["pdf_links"] = len(pdfs)
        out["sample"] = pdfs[:5]
    return out


@probe("emission_factors")
def _emission_factors():
    """Grid CO2 intensity: CEA for India, Ember for everywhere else."""
    out = {}
    for name, url in {
        "cea": "https://cea.nic.in/cdm-co2-baseline-database/?lang=en",
        "ember": "https://ember-energy.org/data/yearly-electricity-data/",
        "ember_api": "https://api.ember-energy.org/v1/carbon-intensity/yearly?entity=India",
    }.items():
        try:
            r = requests.get(url, timeout=45, headers=HEADERS)
            out[name] = r.status_code
        except Exception as exc:                      # noqa: BLE001
            out[name] = f"{type(exc).__name__}"
    return out


if __name__ == "__main__":
    print("\n===== SUMMARY =====")
    print(json.dumps({k: (v["ok"], v.get("error", "")) for k, v in OUT.items()}, indent=1))
    with open("scripts/probe_results.json", "w") as fh:
        json.dump(OUT, fh, indent=1)
    print("wrote scripts/probe_results.json")
