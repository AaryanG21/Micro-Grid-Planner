import json
import os

import numpy as np
import pandas as pd
import requests
from sklearn.metrics import mean_absolute_error

MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "demand_shape.joblib")
LOAD_CSV = "data/AEP_hourly.csv"
TEMP_CSV = "data/aep_temperature.csv"

# AEP's service territory is centred on central Ohio / Appalachia.
TEMP_LAT, TEMP_LON = 39.96, -83.00

try:
    import lightgbm as lgb
    lgb.train({"objective": "regression", "verbose": -1},
              lgb.Dataset(np.zeros((8, 1)), np.arange(8.0)), num_boost_round=1)
    HAS_LGB = True
except Exception:
    HAS_LGB = False
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
import joblib  # noqa: E402


def fetch_temperature(start, end):
    """Hourly 2 m temperature for the load region, cached to disk."""
    if os.path.exists(TEMP_CSV):
        return pd.read_csv(TEMP_CSV, parse_dates=["time"]).set_index("time")["temp_c"]
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={TEMP_LAT}&longitude={TEMP_LON}"
        f"&start_date={start:%Y-%m-%d}&end_date={end:%Y-%m-%d}"
        "&hourly=temperature_2m&timezone=UTC"
    )
    print("fetching hourly temperature from Open-Meteo ...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    h = r.json()["hourly"]
    s = pd.Series(h["temperature_2m"], index=pd.to_datetime(h["time"]), name="temp_c")
    s.index.name = "time"
    os.makedirs("data", exist_ok=True)
    s.to_frame().to_csv(TEMP_CSV)
    return s


def build_features(index, temp_c):
    """Feature frame from a DatetimeIndex plus a temperature series."""
    f = pd.DataFrame(index=index)
    hour = index.hour.values
    doy = index.dayofyear.values
    f["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    f["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    f["doy_sin"] = np.sin(2 * np.pi * doy / 365)
    f["doy_cos"] = np.cos(2 * np.pi * doy / 365)
    f["hour"] = hour
    f["dow"] = index.dayofweek.values
    f["month"] = index.month.values
    f["is_weekend"] = (index.dayofweek.values >= 5).astype(int)
    t = np.asarray(temp_c, dtype=float)
    f["temp_c"] = t
    # Degree-day style features: the load response to temperature is V-shaped,
    # so give the model the two arms explicitly.
    f["cooling_deg"] = np.clip(t - 18.0, 0, None)
    f["heating_deg"] = np.clip(18.0 - t, 0, None)
    f["temp_roll_24"] = pd.Series(t, index=index).rolling(24, min_periods=1).mean().values
    return f


FEATURES = ["hour_sin", "hour_cos", "doy_sin", "doy_cos", "hour", "dow", "month",
            "is_weekend", "temp_c", "cooling_deg", "heating_deg", "temp_roll_24"]


def main():
    load = pd.read_csv(LOAD_CSV, parse_dates=["Datetime"])
    load = load.rename(columns={"AEP_MW": "load"}).sort_values("Datetime")
    load = load.drop_duplicates("Datetime", keep="first").set_index("Datetime")["load"]
    load = load.reindex(pd.date_range(load.index.min(), load.index.max(), freq="h"))
    load = load.interpolate(limit=3).dropna()

    temp = fetch_temperature(load.index.min(), load.index.max())
    temp = temp.reindex(load.index).interpolate(limit=6)
    ok = temp.notna()
    load, temp = load[ok], temp[ok]
    print(f"{len(load):,} aligned hourly records, "
          f"{load.index.min():%Y-%m-%d} to {load.index.max():%Y-%m-%d}")
    print(f"temperature range {temp.min():.1f} to {temp.max():.1f} C")

    x = build_features(load.index, temp)[FEATURES]
    scale = float(load.mean())
    y = (load / scale).values          # dimensionless shape multiplier

    cut = "2017-08-01"
    tr, te = load.index < cut, load.index >= cut
    print(f"train={tr.sum():,}  test={te.sum():,}")

    if HAS_LGB:
        model = lgb.LGBMRegressor(objective="l1", learning_rate=0.05, n_estimators=900,
                                  num_leaves=64, min_child_samples=40, verbose=-1,
                                  random_state=42)
        engine = "LightGBM"
    else:
        model = HistGradientBoostingRegressor(loss="absolute_error", learning_rate=0.05,
                                              max_iter=900, max_leaf_nodes=64,
                                              min_samples_leaf=40, early_stopping=False,
                                              random_state=42)
        engine = "sklearn HistGBM"
    model.fit(x[tr], y[tr])

    pred = model.predict(x[te])
    mape = float(np.mean(np.abs(pred - y[te]) / y[te]) * 100)
    mae_mw = mean_absolute_error(y[te] * scale, pred * scale)
    naive = np.full(te.sum(), 1.0)     # flat profile, the thing to beat
    naive_mape = float(np.mean(np.abs(naive - y[te]) / y[te]) * 100)

    print(f"\n=== DEPLOYABLE SHAPE MODEL ({engine}, no lag features) ===")
    print(f"  flat-profile baseline MAPE : {naive_mape:6.2f} %")
    print(f"  model MAPE                 : {mape:6.2f} %")
    print(f"  model MAE                  : {mae_mw:,.0f} MW "
          f"(on a mean load of {scale:,.0f} MW)")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "engine": engine,
                 "test_mape": mape, "baseline_mape": naive_mape}, MODEL_PATH)
    with open(os.path.join(MODEL_DIR, "demand_shape_metrics.json"), "w") as fh:
        json.dump({"engine": engine, "test_mape_pct": round(mape, 2),
                   "flat_baseline_mape_pct": round(naive_mape, 2),
                   "train_rows": int(tr.sum()), "test_rows": int(te.sum()),
                   "features": FEATURES}, fh, indent=2)
    print(f"\nsaved {MODEL_PATH}")


if __name__ == "__main__":
    main()
