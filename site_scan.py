"""
Site scan: given a map click, find the buildings around it and estimate the
demand they represent.

Pipeline
  1. Query OpenStreetMap (Overpass API) for buildings within a radius.
  2. Classify them and estimate daily kWh from published per-connection
     benchmarks. THIS STEP IS NOT MACHINE LEARNING. There is no dataset
     linking OSM footprints to metered consumption, so the kWh figures are
     documented assumptions the user can override in the UI.
  3. Shape that daily total into an hourly profile with the trained model
     from train_demand_model.py, driven by real temperature for the clicked
     point. THIS STEP IS the machine learning.

Every number returned carries a "method" field so the UI can be honest about
which is which.
"""
import math
import os

import numpy as np
import pandas as pd
import requests

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_URL = OVERPASS_URLS[0]
# Overpass returns 406 to the default python-requests user agent.
HEADERS = {"User-Agent": "MicrogridPlanner/1.0 (academic project; contact via app)"}
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "models", "demand_shape.joblib")

# Daily kWh per building. Indian rural/semi-urban benchmarks, deliberately
# conservative. Documented so a reviewer can challenge them.
BENCHMARKS = {
    "house":       {"kwh_day": 3.5,  "label": "Residential"},
    "apartments":  {"kwh_day": 12.0, "label": "Apartments"},
    "commercial":  {"kwh_day": 25.0, "label": "Commercial"},
    "retail":      {"kwh_day": 18.0, "label": "Retail"},
    "industrial":  {"kwh_day": 90.0, "label": "Industrial"},
    "school":      {"kwh_day": 30.0, "label": "School"},
    "hospital":    {"kwh_day": 120.0, "label": "Healthcare"},
    "farm":        {"kwh_day": 15.0, "label": "Agricultural"},
    "other":       {"kwh_day": 5.0,  "label": "Other"},
}
TYPE_MAP = {
    "house": "house", "detached": "house", "residential": "house",
    "bungalow": "house", "hut": "house", "semidetached_house": "house",
    "apartments": "apartments", "dormitory": "apartments",
    "commercial": "commercial", "office": "commercial",
    "retail": "retail", "shop": "retail", "supermarket": "retail",
    "kiosk": "retail", "warehouse": "industrial",
    "industrial": "industrial", "factory": "industrial",
    "school": "school", "college": "school", "university": "school",
    "kindergarten": "school", "hospital": "hospital", "clinic": "hospital",
    "farm": "farm", "farm_auxiliary": "farm", "barn": "farm",
    "greenhouse": "farm", "stable": "farm",
}
# kWh per square metre of floor area per day, for buildings OSM leaves untyped.
# ~29 kWh/m2/year, mid-range for Indian residential per CEA/BEE benchmarks.
AREA_INTENSITY = 0.08

_MODEL_CACHE = {}


# ----------------------------------------------------------------- geometry
def polygon_area_sqm(coords):
    """Planar area of a small lat/lon ring, projected locally. Metres squared."""
    if len(coords) < 3:
        return 0.0
    lat0 = math.radians(sum(c[0] for c in coords) / len(coords))
    mx, my = 111_320.0 * math.cos(lat0), 110_540.0
    pts = [(c[1] * mx, c[0] * my) for c in coords]
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def centroid(coords):
    return (sum(c[0] for c in coords) / len(coords),
            sum(c[1] for c in coords) / len(coords))


# -------------------------------------------------------------- OSM lookup
def fetch_buildings(lat, lon, radius_m):
    """Buildings within radius_m of (lat, lon) from OpenStreetMap."""
    query = f"""
    [out:json][timeout:25];
    (
      way["building"](around:{radius_m},{lat},{lon});
      relation["building"](around:{radius_m},{lat},{lon});
    );
    out geom;
    """
    last = None
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=40)
            r.raise_for_status()
            elements = r.json().get("elements", [])
            break
        except requests.RequestException as exc:
            last = exc
    else:
        raise last


    buildings = []
    for el in elements:
        geom = el.get("geometry")
        if not geom:
            members = el.get("members") or []
            geom = next((m.get("geometry") for m in members
                         if m.get("role") == "outer" and m.get("geometry")), None)
        if not geom:
            continue
        ring = [(p["lat"], p["lon"]) for p in geom]
        tags = el.get("tags", {})
        raw = tags.get("building", "yes")
        kind = TYPE_MAP.get(raw, TYPE_MAP.get(tags.get("amenity", ""), "other"))
        if raw in ("yes", "roof") and tags.get("amenity") in ("school", "hospital", "clinic"):
            kind = TYPE_MAP[tags["amenity"]]
        clat, clon = centroid(ring)
        levels = tags.get("building:levels")
        try:
            levels = max(1, int(float(levels)))
        except (TypeError, ValueError):
            levels = 1
        buildings.append({
            "id": el.get("id"), "type": kind, "raw_tag": raw,
            "name": tags.get("name"), "levels": levels,
            "footprint_sqm": round(polygon_area_sqm(ring), 1),
            "lat": round(clat, 6), "lon": round(clon, 6),
        })
    return buildings


def fetch_temperature_profile(lat, lon):
    """Next 24 h of temperature for the clicked point. Falls back to a
    seasonal constant if the API is unreachable."""
    try:
        r = requests.get(FORECAST_URL, params={
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m", "forecast_days": 2, "timezone": "auto",
        }, headers=HEADERS, timeout=15)
        r.raise_for_status()
        h = r.json()["hourly"]
        idx = pd.to_datetime(h["time"])[:24]
        return pd.Series(h["temperature_2m"][:24], index=idx), "open-meteo"
    except Exception:
        idx = pd.date_range(pd.Timestamp.utcnow().normalize(), periods=24, freq="h")
        return pd.Series([26.0] * 24, index=idx), "fallback-constant"


# ------------------------------------------------------------- ML profile
def load_model():
    if "m" not in _MODEL_CACHE:
        try:
            import joblib
            _MODEL_CACHE["m"] = joblib.load(MODEL_PATH)
        except Exception:
            _MODEL_CACHE["m"] = None
    return _MODEL_CACHE["m"]


def hourly_profile(daily_kwh, lat, lon):
    """24-value hourly profile in kW summing to daily_kwh."""
    temps, temp_src = fetch_temperature_profile(lat, lon)
    bundle = load_model()
    if bundle is None:
        shape = np.ones(24)
        method = "flat profile (model not trained yet)"
        mape = None
    else:
        from train_demand_model import build_features
        x = build_features(pd.DatetimeIndex(temps.index), temps.values)
        shape = np.clip(bundle["model"].predict(x[bundle["features"]]), 0.05, None)
        method = f"{bundle['engine']} shape model, temperature from {temp_src}"
        mape = bundle.get("test_mape")
    shape = shape / shape.sum()
    profile = shape * daily_kwh
    return {
        "hourly_kw": [round(float(v), 3) for v in profile],
        "peak_kw": round(float(profile.max()), 2),
        "mean_kw": round(float(profile.mean()), 2),
        "peak_hour": int(np.argmax(profile)),
        "load_factor": round(float(profile.mean() / profile.max()), 3) if profile.max() else 0,
        "method": method,
        "model_test_mape_pct": mape,
        "temperature_c": [round(float(t), 1) for t in temps.values],
    }


# ------------------------------------------------------------------ public
def scan_site(lat, lon, radius_m=50, kwh_per_house_override=None):
    buildings = fetch_buildings(lat, lon, radius_m)

    mix, daily = {}, 0.0
    for b in buildings:
        kind = b["type"]
        rate = BENCHMARKS[kind]["kwh_day"]
        if kind == "house" and kwh_per_house_override:
            rate = float(kwh_per_house_override)
        # A four-storey block is not one house. Scale flats by storeys.
        units = b["levels"] if kind == "apartments" else 1
        est = rate * units
        if kind == "other" and b["footprint_sqm"] > 0:
            # Most Indian buildings in OSM carry only building=yes. A flat
            # per-building figure badly understates a 300 m2 block, so fall
            # back to floor area at AREA_INTENSITY kWh/m2/day, clamped.
            est = min(200.0, max(rate, b["footprint_sqm"] * b["levels"] * AREA_INTENSITY))
            b["est_basis"] = "floor area"
        b["est_kwh_day"] = round(est, 2)
        daily += b["est_kwh_day"]
        m = mix.setdefault(kind, {"label": BENCHMARKS[kind]["label"], "count": 0,
                                  "kwh_day": 0.0, "footprint_sqm": 0.0})
        m["count"] += 1
        m["kwh_day"] += b["est_kwh_day"]
        m["footprint_sqm"] += b["footprint_sqm"]

    for m in mix.values():
        m["kwh_day"] = round(m["kwh_day"], 1)
        m["footprint_sqm"] = round(m["footprint_sqm"], 1)

    roof = round(sum(b["footprint_sqm"] for b in buildings), 1)
    profile = hourly_profile(daily, lat, lon) if daily > 0 else None

    return {
        "lat": lat, "lon": lon, "radius_m": radius_m,
        "building_count": len(buildings),
        "total_footprint_sqm": roof,
        # ~6.5 m2 per kWp for modern modules, 60% of roof usable.
        "roof_pv_potential_kwp": round(roof * 0.6 / 6.5, 1),
        "mix": mix,
        "estimated_daily_kwh": round(daily, 1),
        "estimated_annual_kwh": round(daily * 365, 0),
        "demand_method": ("per-building benchmarks, with floor-area fallback at "
                          f"{AREA_INTENSITY} kWh/m2/day for untyped buildings. "
                          "An assumption, user-editable, not a learned parameter"),
        "profile": profile,
        "buildings": buildings[:200],
        "source": "OpenStreetMap via Overpass API",
    }


# ------------------------------------------------------------ Flask wiring
def register_site_scan(app, cache=None, limiter=None):
    """Attach POST /api/site-scan to an existing Flask app."""
    from flask import jsonify, request

    def _scan(lat, lon, radius, override):
        return scan_site(lat, lon, radius, override)

    if cache is not None:
        _scan = cache.memoize(timeout=86400)(_scan)

    @app.route("/api/site-scan", methods=["POST"])
    def site_scan_endpoint():
        body = request.get_json(silent=True) or {}
        try:
            lat = float(body["lat"])
            lon = float(body["lon"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "lat and lon are required numbers"}), 400
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return jsonify({"error": "lat or lon out of range"}), 400
        try:
            radius = int(body.get("radius_m", 50))
        except (TypeError, ValueError):
            radius = 50
        radius = max(10, min(radius, 2000))
        override = body.get("kwh_per_house")

        try:
            result = _scan(round(lat, 5), round(lon, 5), radius, override)
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else 502
            msg = ("OpenStreetMap is rate limiting this IP, try again shortly"
                   if code in (429, 504) else "OpenStreetMap lookup failed")
            return jsonify({"error": msg}), 503
        except requests.RequestException:
            return jsonify({"error": "Could not reach OpenStreetMap"}), 503

        if result["building_count"] == 0:
            result["note"] = ("No mapped buildings here. OSM coverage is patchy "
                              "in rural areas; enter the count manually.")
        return jsonify(result)

    if limiter is not None:
        limiter.limit("30 per hour")(site_scan_endpoint)
    return app
