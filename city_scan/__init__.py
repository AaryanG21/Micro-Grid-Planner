"""
City scan: the city-scale counterpart to site_scan.py.

site_scan answers "what is at this point?" for a ~50 m radius. city_scan
answers "where in this city should a microgrid go?" by building a grid over
the city and attaching population, estimated consumption, industry and CO2
emissions to every cell.

Every value carries a confidence tier, because coverage is uneven worldwide:

  official   - published by a utility or regulator (KERC/BESCOM first)
  calibrated - a global estimate scaled to match an official total
  estimated  - global proxies only (population x national per-capita use)

See CITY_DATA.md for each source, its licence and its resolution.
"""
TIER_OFFICIAL = "official"
TIER_CALIBRATED = "calibrated"
TIER_ESTIMATED = "estimated"
