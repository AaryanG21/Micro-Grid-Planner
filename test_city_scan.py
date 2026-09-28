"""Tests for the city scan. Every network and raster call is faked, so these
run offline and do not hammer Overpass, Climate TRACE or Zenodo."""
import numpy as np
import pytest

from city_scan import (calibration, consumption, emission_factors, emissions,
                       grid, industry, nightlights, population, scoring)

# A 0.1 x 0.1 degree box, roughly 11 km square, near Bengaluru.
BBOX = (12.90, 77.50, 13.00, 77.60)
SQUARE = {"type": "Polygon", "coordinates": [[
    [77.50, 12.90], [77.60, 12.90], [77.60, 13.00], [77.50, 13.00], [77.50, 12.90]]]}


def make_cells(n=4):
    g = grid.make_grid(BBOX, None, cell_m=5000)
    return g["cells"][:n]


# ------------------------------------------------------------------- grid
def test_grid_covers_bbox_and_sizes_cells():
    g = grid.make_grid(BBOX, None, cell_m=1000)
    assert g["rows"] >= 11 and g["cols"] >= 10
    cell = g["cells"][0]
    assert cell["area_sqkm"] == pytest.approx(1.0, abs=0.01)
    south, west, north, east = cell["bounds"]
    assert south >= BBOX[0] - 1e-6 and east <= BBOX[3] + 1e-6


def test_grid_clips_to_boundary():
    half = {"type": "Polygon", "coordinates": [[
        [77.50, 12.90], [77.55, 12.90], [77.55, 13.00], [77.50, 13.00], [77.50, 12.90]]]}
    full = grid.make_grid(BBOX, None, cell_m=1000)
    clipped = grid.make_grid(BBOX, half, cell_m=1000)
    assert len(clipped["cells"]) < len(full["cells"])
    assert all(c["coverage"] > 0 for c in clipped["cells"])
    assert max(c["lon"] for c in clipped["cells"]) < 77.57


def test_grid_refuses_too_many_cells():
    with pytest.raises(ValueError, match="exceeds max_cells"):
        grid.make_grid(BBOX, None, cell_m=10, max_cells=1000)


def test_grid_rejects_backwards_bbox():
    with pytest.raises(ValueError, match="Invalid bbox"):
        grid.make_grid((13.0, 77.6, 12.9, 77.5), None)


def test_geojson_shape():
    fc = grid.to_geojson(make_cells(2), ("population",))
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 2
    ring = fc["features"][0]["geometry"]["coordinates"][0]
    assert len(ring) == 5 and ring[0] == ring[-1]      # closed polygon


# ------------------------------------------------------- population raster
class FakeRaster:
    """Stands in for a GHSL tile: every pixel holds 10 people."""
    def __init__(self, value=10.0):
        self.value = value
        self.bounds = type("B", (), {"left": 70.0, "right": 80.0,
                                     "bottom": 9.0, "top": 19.0})()
        self.transform = None

    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def read(self, _band, window=None, boundless=False):
        return np.full((10, 10), self.value, dtype="float32")


def test_population_sums_raster(monkeypatch):
    cells = make_cells(3)
    monkeypatch.setattr(population, "tile_path", lambda r, c, download=True: "fake.tif")
    monkeypatch.setattr(population.rasterio, "open", lambda p: FakeRaster())
    monkeypatch.setattr(population, "from_bounds", lambda *a, **k: None)

    src = population.population_for_cells(cells, BBOX)
    assert src["resolution_m"] == 93
    assert all(c["population"] == 1000.0 for c in cells)    # 100 px x 10 people


def test_population_reports_missing_tile(monkeypatch):
    def boom(row, col, download=True):
        raise FileNotFoundError("no tile")
    monkeypatch.setattr(population, "tile_path", boom)
    with pytest.raises(RuntimeError, match="unavailable"):
        population.population_for_cells(make_cells(1), BBOX)


def test_tile_ids_for_bengaluru():
    assert (8, 26) in population.tile_ids(BBOX)


# ------------------------------------------------------------- consumption
def test_consumption_uses_country_rate():
    cells = make_cells(2)
    for c in cells:
        c["population"] = 1000.0
        c["industrial_kwh_day"] = 50.0
    method = consumption.estimate(cells, "IN", per_capita={"IN": 1460.0},
                                  residential_share=0.25)
    # 1000 people x 1460 kWh/yr x 0.25 / 365 = 1000 kWh/day, plus industry.
    assert cells[0]["residential_kwh_day"] == pytest.approx(1000.0, abs=1.0)
    assert cells[0]["kwh_day"] == pytest.approx(1050.0, abs=1.0)
    assert method["tier"] == "estimated" and not method["used_fallback_per_capita"]


def test_consumption_falls_back_for_unknown_country():
    cells = make_cells(1)
    cells[0]["population"] = 100.0
    method = consumption.estimate(cells, "ZZ", per_capita={"IN": 1460.0})
    assert method["used_fallback_per_capita"] is True
    assert cells[0]["kwh_day"] > 0


# ------------------------------------------------------------- calibration
def test_calibration_applies_official_per_capita_rate():
    cells = make_cells(2)
    for c in cells:
        c["population"] = 1_000_000.0
        c["residential_kwh_day"] = 500_000.0
        c["industrial_kwh_day"] = 1000.0

    result = calibration.apply(
        cells, official_residential_mwh_year=3_650_000.0,   # 3.65 TWh
        service_area_population=10_000_000, area_name="TEST service area",
        source={"name": "test"}, financial_year="2023-24")

    # 3.65 TWh / 10 M people = 365 kWh/person/yr = 1 kWh/person/day.
    assert result["official_kwh_per_capita_year"] == pytest.approx(365.0)
    assert cells[0]["residential_kwh_day"] == pytest.approx(1_000_000.0)
    assert cells[0]["kwh_day"] == pytest.approx(1_001_000.0)
    assert cells[0]["tier"] == "calibrated"
    # Industrial load must survive calibration untouched.
    assert cells[0]["industrial_kwh_day"] == 1000.0
    assert result["city_share_of_service_area_pct"] == pytest.approx(20.0)


def test_calibration_reports_model_error():
    cells = make_cells(1)
    cells[0]["population"] = 1_000_000.0
    cells[0]["residential_kwh_day"] = 2_000_000.0        # model says 2 kWh/person/day
    result = calibration.apply(cells, 365_000.0, 1_000_000, "A", {"name": "t"})
    # Official is 1 kWh/person/day, so the model was 100% too high.
    assert result["pre_calibration_error_pct"] == pytest.approx(100.0, abs=0.1)


def test_calibration_rejects_bad_inputs():
    with pytest.raises(ValueError):
        calibration.apply(make_cells(1), 0, 1000, "A", {})
    with pytest.raises(ValueError):
        calibration.apply(make_cells(1), 100.0, 0, "A", {})


# ---------------------------------------------------------------- industry
def test_industry_parses_and_bins(monkeypatch):
    zone = {"id": 1, "tags": {"landuse": "industrial", "name": "Test Estate"},
            "geometry": [{"lat": 12.91, "lon": 77.51}, {"lat": 12.91, "lon": 77.52},
                         {"lat": 12.92, "lon": 77.52}, {"lat": 12.92, "lon": 77.51}]}
    shed = {"id": 2, "tags": {"building": "factory", "building:levels": "2"},
            "geometry": [{"lat": 12.95, "lon": 77.55}, {"lat": 12.95, "lon": 77.5505},
                         {"lat": 12.9505, "lon": 77.5505}, {"lat": 12.9505, "lon": 77.55}]}
    monkeypatch.setattr(industry, "overpass_query", lambda q, deadline_s=180: [zone, shed])

    result = industry.fetch_industry(BBOX)
    assert result["count"] == 2 and result["named_count"] == 1
    kinds = {s["kind"] for s in result["sites"]}
    assert kinds == {"industrial_zone", "industrial_building"}

    cells = make_cells(6)
    industry.assign_to_cells(cells, result["sites"])
    assert sum(c["industrial_sites"] for c in cells) == 2
    assert sum(c["industrial_kwh_day"] for c in cells) == pytest.approx(
        result["total_kwh_day"], rel=0.01)


def test_industry_skips_slivers(monkeypatch):
    sliver = {"id": 3, "tags": {"building": "industrial"},
              "geometry": [{"lat": 12.9, "lon": 77.5}, {"lat": 12.9, "lon": 77.50001},
                           {"lat": 12.90001, "lon": 77.50001}, {"lat": 12.90001, "lon": 77.5}]}
    monkeypatch.setattr(industry, "overpass_query", lambda q, deadline_s=180: [sliver])
    assert industry.fetch_industry(BBOX)["count"] == 0


# --------------------------------------------------------------- emissions
def test_emissions_excludes_aggregates_from_cells(monkeypatch):
    rows = [
        {"id": 1, "name": "Plant A", "sector": "power", "subsector": "coal",
         "sourceType": "asset", "centroid": {"latitude": 12.91, "longitude": 77.51},
         "emissionsQuantity": 1000.0, "year": 2024},
        {"id": 2, "name": "Whole city road transport", "sector": "transportation",
         "sourceType": "city-aggregation",
         "centroid": {"latitude": 12.95, "longitude": 77.55},
         "emissionsQuantity": 500000.0, "year": 2024},
    ]
    monkeypatch.setattr(emissions, "find_city_id",
                        lambda bbox=None, name=None: {"id": "x", "name": "Test", "others": []})

    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return rows
    monkeypatch.setattr(emissions.requests, "get", lambda *a, **k: R())

    result = emissions.fetch_emissions(bbox=BBOX)
    assert result["count"] == 2 and result["facility_count"] == 1
    assert result["facility_co2e_t"] == 1000.0

    cells = make_cells(6)
    emissions.assign_to_cells(cells, result["sources"])
    assert sum(c["co2e_t"] for c in cells) == 1000.0     # aggregate excluded
    assert sum(c["emitter_count"] for c in cells) == 1


def test_emissions_missing_city_raises(monkeypatch):
    monkeypatch.setattr(emissions, "find_city_id", lambda bbox=None, name=None: None)
    with pytest.raises(LookupError):
        emissions.fetch_emissions(bbox=BBOX)


# -------------------------------------------------------- emission factors
def test_grid_factor_prefers_national_regulator():
    india = emission_factors.grid_factor("IN")
    assert india["t_co2_per_mwh"] == 0.675
    assert india["basis"] == "national regulator"
    assert "CEA" in india["source"]["name"]


def test_grid_factor_falls_back_to_world_average():
    unknown = emission_factors.grid_factor("ZZ")
    assert unknown["basis"] == "world average fallback"


def test_avoided_co2_blends_grid_and_diesel():
    grid_only = emission_factors.avoided_co2_t(1_000_000, "IN", grid_share=1.0)
    diesel_only = emission_factors.avoided_co2_t(1_000_000, "IN", grid_share=0.0)
    assert grid_only["co2_avoided_t"] == pytest.approx(675.0, abs=1)
    assert diesel_only["co2_avoided_t"] == pytest.approx(810.0, abs=1)
    assert "grid" in grid_only["method"]


# ------------------------------------------------------- nightlights, score
def test_demand_weights_blend_population_and_light():
    cells = make_cells(2)
    cells[0].update(population=1000.0, radiance=0.0)
    cells[1].update(population=0.0, radiance=10.0)
    nightlights.demand_weights(cells, population_weight=0.6)
    assert cells[0]["demand_weight"] == pytest.approx(0.6)
    assert cells[1]["demand_weight"] == pytest.approx(0.4)


def test_scoring_ranks_by_weighted_inputs():
    cells = make_cells(3)
    for i, c in enumerate(cells):
        c.update(kwh_day=100.0 * (i + 1), population=10.0 * (i + 1),
                 industrial_kwh_day=0.0, co2e_t=0.0)
    result = scoring.score_cells(cells, top_n=2)
    assert len(result["top"]) == 2
    assert result["top"][0]["id"] == cells[-1]["id"]      # biggest cell wins
    assert result["top"][0]["score"] >= result["top"][1]["score"]
    assert sum(result["weights"].values()) == pytest.approx(1.0)


def test_scoring_handles_all_zero_layer():
    cells = make_cells(2)
    for c in cells:
        c.update(kwh_day=0.0, population=0.0, industrial_kwh_day=0.0, co2e_t=0.0)
    result = scoring.score_cells(cells)
    assert all(t["score"] == 0.0 for t in result["top"])


# ---------------------------------------------------------------- pipeline
def test_pipeline_survives_a_failing_layer():
    from city_scan import pipeline
    result = {"layer_status": {}}
    value = pipeline.run_layer(result, "boom", lambda: 1 / 0)
    assert value is None
    assert result["layer_status"]["boom"]["ok"] is False
    assert "ZeroDivisionError" in result["layer_status"]["boom"]["error"]
    ok = pipeline.run_layer(result, "fine", lambda: "value")
    assert ok == "value" and result["layer_status"]["fine"]["ok"] is True
