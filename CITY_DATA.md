# City layer data sources

Findings from `scripts/probe_sources.py` (raw output in `scripts/probe_results.json`).
Every layer the city scan serves must appear here with a source, a licence and a
resolution, so any number in the UI can be traced back to where it came from.

## Verified 2026-09-27

### Population — GHSL GHS-POP R2023A (chosen)
- Tiles: `https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/GHS_POP_E2025_GLOBE_R2023A_4326_3ss/V1-0/tiles/GHS_POP_E2025_GLOBE_R2023A_4326_3ss_V1_0_R{row}_C{col}.zip`
- Tile index: `col = floor((lon+180)/10)+1`, `row = floor((90-lat)/10)+1`. Bengaluru = R8_C26,
  whose bounds are lon 69.99–79.99, lat 9.10–19.10.
- 3 arc-seconds ≈ **93 m** at this latitude, EPSG:4326, epoch 2025, persons per cell.
- One tile = 160 MB zipped, downloaded in **27 s**; covers 10°×10°, so it is
  fetched once and cached per region rather than per city.
- Ranged GET returns **206**, so partial reads work if we later want them.
- Sanity check: the Bengaluru bbox (12.83–13.14 N, 77.45–77.78 E) sums to
  **14,478,427 people**, consistent with the ~14 M urban agglomeration.
- Licence: CC BY 4.0 (European Commission, JRC). Attribution required.

### Population — WorldPop (rejected)
- `https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/IND/ind_ppp_2020.tif`
  is 1.84 GB and `HEAD` advertises `Accept-Ranges: bytes`, but a real ranged
  `GET` is ignored: the server streams the whole file and GDAL fails with
  "Range downloading not supported by this server!". Also only reaches 2020.
- Kept here so nobody tries it again on the strength of the HEAD response.

### Industry — OpenStreetMap via Overpass
- One city-wide query for `landuse=industrial` + `building=industrial|factory|warehouse`
  over the Bengaluru bbox returned **2,199 elements (440 named) in 9.8 s**.
  Sample names: Bosch NhP, BWSSB, BMTC Depot 4, Central Warehouse, Concor.
- No tiling needed at city scale; one query per city is fine.
- Reliability: see Phase 0a in the plan — `overpass_query()` in `site_scan.py`
  now retries on 429/504 and enforces a deadline. The `overpass.kumi.systems`
  mirror was removed as dead.
- Licence: ODbL. Attribution required, and share-alike applies to derived
  geometry — relevant if this is ever commercialised.

### Emissions — Climate TRACE v7 (resolved)
- There is **no bbox filter on emissions**. The flow is two calls:
  1. `GET /v7/cities?bbox={west},{south},{east},{north}` → Functional Urban Area id
     (Bengaluru = `ghs-fua_9099`; the bbox also overlaps `Hoskote Urban Area`).
  2. `GET /v7/sources?cityId=ghs-fua_9099&year=2024&gas=co2e_100yr&limit=1000`.
  `/v7/assets` does not exist — v7 renamed assets to **sources**. v6 `/assets`
  still answers but is undocumented; we build on v7.
- No API key, no auth, CORS open. `limit`/`offset` paginate. City-level data
  exists from **2021** onward only. Emissions are in **metric tonnes**.
- Verified for Bengaluru: **177 sources, 8.42 Mt CO2e total**, of which
  **157 real facilities = 3.02 Mt**. The rest are `sourceType: city-aggregation`
  rows (e.g. all road transport at one centroid), which `assign_to_cells`
  excludes so they cannot invent a hotspot.
- FUAs are GHS metropolitan areas, **not municipal boundaries**, so a city
  total can cover more ground than the Nominatim boundary.
- Licence: CC BY 4.0. Note their terms carve out some external datasets
  (GADM, GHS-FUA), worth re-checking before any commercial use.

### Night lights — VIIRS VNL v2.2 2024, via Zenodo (resolved)
- URL: `https://zenodo.org/api/records/17294744/files/nightlights.average_viirs.v21_m_500m_s_20240101_20241231_go_epsg4326_v20250904.tif/content`
- **No login.** EOG's own server (eogdata.mines.edu) redirects every `.tif` to a
  Keycloak login, so the authoritative source needs registration; this Zenodo
  record is EOG's own VNL 2024 composite repackaged as a true COG.
- 63.7 MB, 15 arc-seconds (~500 m), EPSG:4326, int16 with `scale=10` — divide
  by 10 for nW/cm2/sr. Ranged GET returns 206.
- Verified: a Bengaluru window (74x79 px) read in **4 s** without downloading
  the whole file, radiance 0.3-12.1 nW/cm2/sr.
- Gotcha: do **not** set `CPL_VSIL_CURL_ALLOWED_EXTENSIONS` for this one. The
  URL ends in `/content`, not `.tif`, and the extension filter rejects it.
- Licence: CC BY 4.0, Earth Observation Group, Colorado School of Mines.

### Official consumption — KERC/BESCOM (resolved, and it constrains the design)
**There is no published Bengaluru-city-only consumption figure.** Both utilities
report whole-service-area totals, so calibration can only be done at the
utility level, not per city or ward.

- **BESCOM 22nd Annual Report FY2023-24** (latest; FY24-25 not published yet):
  `https://bescom.karnataka.gov.in/uploads/media_to_upload1775732706.pdf`
  - Machine-readable text — `pdfplumber` extracts it directly, no OCR.
  - PDF pages 22–24 carry the sales tables, broken down by tariff category
    (LT1–LT7, HT1–HT5), e.g. Domestic 9,141.69 MU, Industrial LT 1,452.04 +
    HT 5,437.88 MU, IP sets 10,230.15 MU.
  - **Total sales FY2023-24 = 36,185.07 MU** (verified by re-extracting the PDF
    myself, not just taking the research agent's word). Interface energy
    39,821 MU, distribution loss 9.13%, 14.43 M consumers.
  - Service area = **8 districts, 41,092 km²** (Bengaluru Urban and Rural,
    Ramanagara, Kolar, Chikkaballapur, Tumakuru, Davanagere, Chitradurga).
- **MESCOM 23rd Annual Report FY2024-25** (for Chikkamagaluru later):
  `https://mescom.karnataka.gov.in/uploads/media_to_upload1768193771.pdf`
  - Machine-readable. **Total sales FY2024-25 = 6,654.73 MU** across 4 districts
    (Dakshina Kannada, Udupi, Shivamogga, Chikkamagaluru), with **no category
    or district split** — only consumer counts per district for subsidy schemes.
- **KERC Combined Tariff Order 2025**: `https://kerc.karnataka.gov.in/uploads/96731743148968.pdf`
  - The per-ESCOM sales tables (4.3, 5.10A–F) are **pasted raster images**, so
    they need OCR. Use the annual reports instead — same data, extractable.
  - Its machine-readable numbers are Commission-**approved projections**
    (BESCOM 38,206.95 MU for FY26), not measured actuals.

### Grid emission factors (resolved)
- **India: CEA CO2 Baseline Database v22.0** (September 2026), national weighted
  average **0.675 tCO2/MWh** for FY2025-26 (down from 0.774 in FY2013-14).
  User guide: `https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf`
- **Rest of world: Ember, served through Our World in Data.** ember-energy.org
  itself returns 403 to scripts; `https://ourworldindata.org/grapher/carbon-intensity-electricity.csv`
  works (follow redirects) and carries Ember's data with its CC BY 4.0 licence.
  India 670.13, USA 384.4, France 41.44 gCO2/kWh (2025).
- **Per-capita electricity** for the demand estimate comes from the same source:
  `https://ourworldindata.org/grapher/per-capita-electricity-generation.csv`
  (India 1,422 kWh/person, 2025). Both are bundled as CSVs under
  `city_scan/data/`, 214 and 213 countries.
- **Diesel: 2.70 kg CO2/litre** (US EPA GHG Emission Factors Hub 2025,
  10.21 kg/US gallon), x 0.30 L/kWh generator consumption = **0.81 t CO2/MWh**.
  That 0.30 L/kWh is the sensitive assumption: an old or lightly loaded genset
  can use 0.4-0.5 L/kWh, pushing the factor past 1.1.

## Accuracy result (Bengaluru pilot)
Calibrating against BESCOM's published FY2023-24 domestic sales:
- Official domestic sales 9,245.52 MU over a service-area population of
  **30,095,552** (GHSL, 8 districts) = **307.2 kWh per person per year**.
- The global model (population x national per-capita x residential share) was
  **15.7% high** before calibration. That is the honest accuracy figure for
  the estimate-only tier, and it is what should be quoted.
- Bengaluru holds 45.6% of the service area's people.
