"""Official electricity sales for Karnataka's distribution utilities (ESCOMs).

Figures are transcribed from the utilities' own annual reports, which publish
audited actuals as machine-readable text. KERC's combined tariff order carries
the same data as scanned images, and mostly as Commission-approved projections
rather than actuals, so the annual reports are the better source.

Every figure records the document, the page and the URL it came from, so a
reviewer can check it. Refresh once a year: scripts/ingest_kerc.py.

Important limitation, and the reason calibration is service-area wide:
no ESCOM publishes sales for a single city. BESCOM's total covers eight
districts; MESCOM's covers four.
"""

MU_TO_MWH = 1000.0          # 1 million unit = 1 GWh = 1000 MWh

BESCOM = {
    "utility": "BESCOM",
    "full_name": "Bangalore Electricity Supply Company Limited",
    "financial_year": "2023-24",
    "total_sales_mu": 36185.07,
    "metered_sales_mu": 25963.53,
    "unmetered_sales_mu": 10221.54,
    "interface_energy_mu": 39821.0,
    "distribution_loss_pct": 9.13,
    "consumers_millions": 14.43,
    "service_area_sqkm": 41092,
    # Spellings that Nominatim resolves to the administrative polygon: the
    # annual report writes "Chikkaballapur", OSM has "Chikkaballapura".
    "districts": ["Bengaluru Urban", "Bengaluru Rural", "Ramanagara", "Kolar",
                  "Chikkaballapura", "Tumakuru", "Davanagere", "Chitradurga"],
    # Million units by tariff category, from the same table.
    "by_category_mu": {
        "Bhagya Jyothi (LT1)": 268.92,
        "Domestic (LT2, incl AEH)": 9245.52,
        "Commercial (LT3)": 5493.17,
        "Irrigation pumps (LT4, incl unmetered)": 10230.15,
        "Industrial (LT5 + HT2A)": 6889.91,
        "Water works and street lighting (LT6)": 2453.71,
        "Public lighting": 658.59,
        "Temporary and others (LT7)": 832.89,
    },
    # Domestic lighting incl. AEH: the category that tracks residents, and so
    # the only one that can honestly be turned into a per-capita rate.
    "residential_mu": 9245.52,
    "source": {
        "name": "BESCOM 22nd Annual Report FY2023-24, pages 22-24",
        "url": "https://bescom.karnataka.gov.in/uploads/media_to_upload1775732706.pdf",
        "licence": "Government of Karnataka publication",
        "retrieved": "2026-09-27",
    },
}

MESCOM = {
    "utility": "MESCOM",
    "full_name": "Mangalore Electricity Supply Company Limited",
    # MESCOM's own FY2024-25 report has no category split, so the residential
    # figure comes from KERC's FY2023-24 actuals table instead. The two years
    # are kept apart deliberately rather than blended.
    "financial_year": "2023-24",
    "total_sales_mu": 6877.42,
    "latest_total_sales_mu": 6654.73,
    "latest_financial_year": "2024-25",
    "distribution_loss_pct": 8.34,
    "service_area_sqkm": None,
    "districts": ["Dakshina Kannada", "Udupi", "Shivamogga", "Chikkamagaluru"],
    "by_category_mu": {
        "Domestic (LT1)": 1830.33,
        "Commercial (LT3a)": 502.17,
        "Irrigation pumps (LT4a)": 2534.07,
        "Industrial (LT5 + HT2a)": 1082.59,
        "Water works and lighting (LT6a+b)": 233.88,
        "Temporary (LT7)": 25.13,
    },
    "residential_mu": 1830.33,
    "source": {
        "name": ("MESCOM 23rd Annual Report FY2024-25 (total) and KERC Combined "
                 "Tariff Order 2025 Table 4.3B (FY2023-24 actuals by category)"),
        "url": "https://mescom.karnataka.gov.in/uploads/media_to_upload1768193771.pdf",
        "secondary_url": "https://kerc.karnataka.gov.in/uploads/96731743148968.pdf",
        "licence": "Government of Karnataka publication",
        "retrieved": "2026-09-27",
        "note": ("category figures were read from scanned tables by OCR and "
                 "checked against published subtotals (LT + HT = grand total)"),
    },
}

UTILITIES = [BESCOM, MESCOM]
# Which ESCOM serves a district. Lower-case, no spaces, for loose matching.
_DISTRICT_TO_UTILITY = {
    d.lower().replace(" ", ""): u for u in UTILITIES for d in u["districts"]
}
# Common English spellings that differ from the official district name.
_ALIASES = {
    "bangalore": "bengaluruurban", "bengaluru": "bengaluruurban",
    "bangaloreurban": "bengaluruurban", "bangalorerural": "bengalururural",
    "chikmagalur": "chikkamagaluru", "chikmangalore": "chikkamagaluru",
    "chikkamagalur": "chikkamagaluru", "mangalore": "dakshinakannada",
    "mangaluru": "dakshinakannada", "shimoga": "shivamogga",
    "tumkur": "tumakuru", "davangere": "davanagere",
}


def official_total(place_name):
    """The utility serving this place, with its published sales total.

    Returns None when no ESCOM here is known, so the caller leaves the city on
    the "estimated" tier rather than inventing a calibration.
    """
    key = (place_name or "").lower().replace(" ", "").replace(",", "")
    key = _ALIASES.get(key, key)
    utility = _DISTRICT_TO_UTILITY.get(key)
    if not utility:
        # Fall back to a substring match: "Bengaluru Urban District, Karnataka".
        for district, u in _DISTRICT_TO_UTILITY.items():
            if district in key:
                utility = u
                break
    if not utility:
        return None

    return {
        "utility": utility["utility"],
        "area_name": f"{utility['utility']} service area "
                     f"({len(utility['districts'])} districts)",
        "scope": "utility service area",
        "financial_year": utility["financial_year"],
        "official_mwh_year": utility["total_sales_mu"] * MU_TO_MWH,
        "official_residential_mwh_year": utility["residential_mu"] * MU_TO_MWH,
        "by_category_mu": utility["by_category_mu"],
        "districts": utility["districts"],
        "source": utility["source"],
    }


def service_area_population(place_name, population_module=None):
    """People served by the utility covering this place, from GHSL.

    Cached on disk: it takes ~8 Nominatim lookups plus raster reads, and the
    answer changes once a year at most.
    """
    import json
    import os

    official = official_total(place_name)
    if not official:
        return None

    cache_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data")
    cache_file = os.path.join(cache_dir, "service_area_population.json")
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as fh:
            cache = json.load(fh)
    key = official["utility"]
    if key in cache:
        return cache[key]

    if population_module is None:
        from .. import population as population_module
    districts = [f"{d} district, Karnataka, India" for d in official["districts"]]
    stats = population_module.population_in_areas(districts)
    entry = {"utility": key, "population": stats["total"],
             "by_district": stats["by_area"], "source": stats["source"]}

    os.makedirs(cache_dir, exist_ok=True)
    cache[key] = entry
    with open(cache_file, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=1)
    return entry
