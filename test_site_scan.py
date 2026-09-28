"""Smoke tests for site_scan. Uses a stubbed Overpass response so it runs
without network access."""
import json
import types

import numpy as np
import pandas as pd

import site_scan


def square_ring(lat, lon, side_m):
    d_lat = side_m / 110540.0
    d_lon = side_m / (111320.0 * np.cos(np.radians(lat)))
    return [{"lat": lat, "lon": lon},
            {"lat": lat + d_lat, "lon": lon},
            {"lat": lat + d_lat, "lon": lon + d_lon},
            {"lat": lat, "lon": lon + d_lon},
            {"lat": lat, "lon": lon}]


FAKE = {"elements": [
    {"type": "way", "id": 1, "tags": {"building": "house"},
     "geometry": square_ring(12.97, 77.59, 10)},
    {"type": "way", "id": 2, "tags": {"building": "house", "name": "Ravi Nivas"},
     "geometry": square_ring(12.9701, 77.5901, 12)},
    {"type": "way", "id": 3, "tags": {"building": "apartments", "building:levels": "4"},
     "geometry": square_ring(12.9702, 77.5902, 20)},
    {"type": "way", "id": 4, "tags": {"building": "yes", "amenity": "school"},
     "geometry": square_ring(12.9703, 77.5903, 30)},
    {"type": "way", "id": 5, "tags": {"building": "shed"},
     "geometry": square_ring(12.9704, 77.5904, 5)},
]}


class FakeResp:
    status_code = 200

    def json(self):
        return FAKE

    def raise_for_status(self):
        return None


def test_area():
    a = site_scan.polygon_area_sqm([(p["lat"], p["lon"]) for p in square_ring(12.97, 77.59, 10)])
    assert 95 < a < 105, a
    print(f"  area of a 10 m square = {a:.1f} m2  OK")


def test_scan(monkeypatch):
    # The fixture this asked for ("monkeypatched") never existed, so the test
    # errored out instead of running. Stub Overpass and the temperature feed,
    # as the module docstring says, so it needs no network.
    monkeypatch.setattr(site_scan.requests, "post", lambda *a, **k: FakeResp())
    monkeypatch.setattr(site_scan, "fetch_temperature_profile", lambda lat, lon: (
        pd.Series([26.0] * 24,
                  index=pd.date_range("2024-06-01", periods=24, freq="h")),
        "test-stub"))
    r = site_scan.scan_site(12.97, 77.59, radius_m=50)
    assert r["building_count"] == 5, r["building_count"]
    # 2 houses @3.5 + 1 apartments 4 levels @12 + school @30 + other @5
    expected = 3.5 * 2 + 12.0 * 4 + 30.0 + 5.0
    assert abs(r["estimated_daily_kwh"] - expected) < 0.01, r["estimated_daily_kwh"]
    assert r["total_footprint_sqm"] > 0
    assert set(r["mix"]) == {"house", "apartments", "school", "other"}
    assert len(r["profile"]["hourly_kw"]) == 24
    assert abs(sum(r["profile"]["hourly_kw"]) - r["estimated_daily_kwh"]) < 0.5
    print(f"  {r['building_count']} buildings, {r['estimated_daily_kwh']} kWh/day, "
          f"peak {r['profile']['peak_kw']} kW, roof {r['total_footprint_sqm']} m2")
    print(f"  roof PV potential {r['roof_pv_potential_kwp']} kWp")
    print(f"  profile method: {r['profile']['method']}")
    for k, v in r["mix"].items():
        print(f"    {v['label']:<14} n={v['count']}  {v['kwh_day']} kWh/day")
    return r


def test_model_roundtrip(tmp_path, monkeypatch):
    """Train a throwaway model on synthetic data to verify the joblib load and
    predict plumbing that scan_site depends on. Not a result, just plumbing."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    import joblib
    from train_demand_model import build_features, FEATURES
    idx = pd.date_range("2024-01-01", periods=24 * 120, freq="h")
    temp = pd.Series(26 + 6 * np.sin(np.arange(len(idx)) / 24 * 2 * np.pi), index=idx)
    x = build_features(idx, temp.values)[FEATURES]
    y = 1 + 0.4 * np.sin(idx.hour / 24 * 2 * np.pi) + 0.01 * temp.values
    m = HistGradientBoostingRegressor(max_iter=40).fit(x, y)
    # Write to a temp path so the real trained model is never touched.
    monkeypatch.setattr(site_scan, "MODEL_PATH", str(tmp_path / "demand_shape.joblib"))
    joblib.dump({"model": m, "features": FEATURES, "engine": "test",
                 "test_mape": 1.23}, site_scan.MODEL_PATH)
    site_scan._MODEL_CACHE.clear()
    p = site_scan.hourly_profile(100.0, 12.97, 77.59)
    assert abs(sum(p["hourly_kw"]) - 100.0) < 0.5, sum(p["hourly_kw"])
    assert p["peak_kw"] > p["mean_kw"] > 0
    print(f"  model path: peak {p['peak_kw']} kW at hour {p['peak_hour']}, "
          f"load factor {p['load_factor']}")
    print(f"  method: {p['method']}")
    site_scan._MODEL_CACHE.clear()


if __name__ == "__main__":
    site_scan.requests = types.SimpleNamespace(
        post=lambda *a, **k: FakeResp(),
        get=lambda *a, **k: (_ for _ in ()).throw(Exception("no network")),
        HTTPError=Exception, RequestException=Exception)
    print("geometry:")
    test_area()
    print("scan_site (model absent, network down -> fallbacks):")
    test_scan(True)
    print("model plumbing:")
    test_model_roundtrip()
    print("\nall smoke tests passed")
