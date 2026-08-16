"""
Day-ahead hourly load forecasting benchmark on real PJM (AEP) data.
Compares seasonal naive, ridge regression, LightGBM (calendar only),
LightGBM (calendar + lags), and LightGBM quantile models.

All lags are >= 24 hours so the setup is a genuine day-ahead forecast,
not a 1-step-ahead forecast that leaks recent load.
"""
import os
import time
import urllib.request
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
RNG = 42

# LightGBM's macOS wheel needs the libomp runtime. If it is missing, fall back
# to scikit-learn's HistGradientBoostingRegressor, which is the same
# histogram-based gradient boosting algorithm and ships its own OpenMP.
try:
    if os.environ.get("MICROGRID_NO_LGB"):
        raise ImportError("forced fallback via MICROGRID_NO_LGB")
    import lightgbm as lgb
    lgb.train({"objective": "regression", "verbose": -1},
              lgb.Dataset(np.zeros((8, 1)), np.arange(8.0)), num_boost_round=1)
    HAS_LGB = True
    GBM_NAME = "LightGBM"
except Exception as exc:
    HAS_LGB = False
    GBM_NAME = "sklearn HistGBM"
    print(f"[note] LightGBM unavailable ({type(exc).__name__}: "
          f"{str(exc).splitlines()[0][:80]})")
    print("[note] falling back to sklearn HistGradientBoostingRegressor\n")

BASE_PARAMS = dict(objective="regression", metric="l1", learning_rate=0.05,
                   num_leaves=64, min_data_in_leaf=40, feature_fraction=0.9,
                   bagging_fraction=0.9, bagging_freq=1, verbose=-1, seed=RNG)


def fit_gbm(x_tr, y_tr, rounds, alpha=None):
    """Train a gradient boosting model; returns (predict_fn, model)."""
    if HAS_LGB:
        p = dict(BASE_PARAMS)
        if alpha is not None:
            p.update(objective="quantile", alpha=alpha, metric="quantile")
        m = lgb.train(p, lgb.Dataset(x_tr, y_tr), num_boost_round=rounds)
        return m.predict, m
    kw = dict(learning_rate=0.05, max_iter=rounds, max_leaf_nodes=64,
              min_samples_leaf=40, early_stopping=False, random_state=RNG)
    if alpha is not None:
        m = HistGradientBoostingRegressor(loss="quantile", quantile=alpha, **kw)
    else:
        m = HistGradientBoostingRegressor(loss="absolute_error", **kw)
    m.fit(x_tr, y_tr)
    return m.predict, m


# ---------------------------------------------------------------- load data
DATA = "data/AEP_hourly.csv"
if not os.path.exists(DATA):
    os.makedirs("data", exist_ok=True)
    url = ("https://raw.githubusercontent.com/MainakRepositor/Datasets/"
           "master/AEP_hourly.csv")
    print(f"downloading {url} ...")
    urllib.request.urlretrieve(url, DATA)

df = pd.read_csv(DATA, parse_dates=["Datetime"])
df = df.rename(columns={"AEP_MW": "load"}).sort_values("Datetime")
df = df.drop_duplicates(subset="Datetime", keep="first").set_index("Datetime")
full = pd.date_range(df.index.min(), df.index.max(), freq="h")
df = df.reindex(full)
df["load"] = df["load"].interpolate(limit=3)
df = df.dropna()
print(f"rows={len(df)}  from {df.index.min()} to {df.index.max()}")

# ------------------------------------------------------------ feature build
d = df.copy()
d["hour"] = d.index.hour
d["dow"] = d.index.dayofweek
d["month"] = d.index.month
d["doy"] = d.index.dayofyear
d["year"] = d.index.year
d["is_weekend"] = (d["dow"] >= 5).astype(int)
d["hour_sin"] = np.sin(2 * np.pi * d["hour"] / 24)
d["hour_cos"] = np.cos(2 * np.pi * d["hour"] / 24)
d["doy_sin"] = np.sin(2 * np.pi * d["doy"] / 365)
d["doy_cos"] = np.cos(2 * np.pi * d["doy"] / 365)

for lag in (24, 48, 72, 168, 336):
    d[f"lag_{lag}"] = d["load"].shift(lag)
d["roll_mean_168"] = d["load"].shift(24).rolling(168).mean()
d["roll_std_168"] = d["load"].shift(24).rolling(168).std()
d["roll_max_24"] = d["load"].shift(24).rolling(24).max()
d["lag24_minus_lag168"] = d["lag_24"] - d["lag_168"]
d = d.dropna()

CAL = ["hour", "dow", "month", "doy", "is_weekend",
       "hour_sin", "hour_cos", "doy_sin", "doy_cos"]
LAG = ["lag_24", "lag_48", "lag_72", "lag_168", "lag_336",
       "roll_mean_168", "roll_std_168", "roll_max_24", "lag24_minus_lag168"]

TEST_START = "2017-08-01"
train, test = d[d.index < TEST_START], d[d.index >= TEST_START]
print(f"train={len(train)} test={len(test)} (test from {TEST_START})")

y_tr, y_te = train["load"].values, test["load"].values


def score(name, pred, secs):
    err = y_te - pred
    return {
        "Model": name,
        "MAE (MW)": np.mean(np.abs(err)),
        "RMSE (MW)": np.sqrt(np.mean(err ** 2)),
        "MAPE (%)": np.mean(np.abs(err / y_te)) * 100,
        "Train time (s)": secs,
    }


results = []

# 1. seasonal naive: load 168 h ago
results.append(score("Seasonal naive (t-168)", test["lag_168"].values, 0.0))

# 2. ridge on calendar features
t0 = time.time()
sc = StandardScaler().fit(train[CAL])
ridge = Ridge(alpha=1.0).fit(sc.transform(train[CAL]), y_tr)
results.append(score("Ridge (calendar only)",
                     ridge.predict(sc.transform(test[CAL])), time.time() - t0))

params = BASE_PARAMS

# 3. gradient boosting, calendar features only
t0 = time.time()
pred_cal, _ = fit_gbm(train[CAL], y_tr, 600)
results.append(score(f"{GBM_NAME} (calendar only)",
                     pred_cal(test[CAL]), time.time() - t0))

# 4. gradient boosting, calendar + lag features
FEATS = CAL + LAG
t0 = time.time()
pred_fn, m_full = fit_gbm(train[FEATS], y_tr, 1200)
pred_full = pred_fn(test[FEATS])
results.append(score(f"{GBM_NAME} (calendar + lags)", pred_full, time.time() - t0))

res = pd.DataFrame(results)
print("\n=== DAY-AHEAD FORECAST ACCURACY (test = Aug 2017 to Aug 2018) ===")
print(res.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

# ------------------------------------------------- quantile models for sizing
q_preds = {}
for alpha in (0.1, 0.5, 0.9):
    qfn, _ = fit_gbm(train[FEATS], y_tr, 800, alpha=alpha)
    q_preds[alpha] = qfn(test[FEATS])


def pinball(y, p, a):
    dl = y - p
    return np.mean(np.maximum(a * dl, (a - 1) * dl))


print("\n=== QUANTILE MODELS (probabilistic forecast) ===")
for a, p in q_preds.items():
    cov = np.mean(y_te <= p) * 100
    print(f"  P{int(a*100):<3d}  pinball loss = {pinball(y_te, p, a):8.2f} MW"
          f"   empirical coverage = {cov:5.1f}%  (target {a*100:.0f}%)")

under_mean = np.mean(y_te > pred_full) * 100
under_p90 = np.mean(y_te > q_preds[0.9]) * 100
print(f"\n  Hours where actual load EXCEEDS the forecast:")
print(f"    using mean forecast : {under_mean:.1f}% of hours -> under-sized system")
print(f"    using P90 forecast  : {under_p90:.1f}% of hours -> safer for sizing")

# ----------------------------------------------------------- top drivers
print("\n=== TOP 8 FEATURES ===")
if HAS_LGB:
    imp = pd.DataFrame({"feature": m_full.feature_name(),
                        "gain": m_full.feature_importance("gain")})
    imp["share_%"] = 100 * imp["gain"] / imp["gain"].sum()
    print(imp.sort_values("gain", ascending=False).head(8)
          .to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
else:
    sub = test.sample(min(2000, len(test)), random_state=RNG)
    pi = permutation_importance(m_full, sub[FEATS], sub["load"],
                                n_repeats=3, random_state=RNG,
                                scoring="neg_mean_absolute_error")
    imp = pd.DataFrame({"feature": FEATS, "mae_increase": pi.importances_mean})
    imp["share_%"] = 100 * imp["mae_increase"] / imp["mae_increase"].sum()
    print(imp.sort_values("mae_increase", ascending=False).head(8)
          .to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

res.to_csv("results_forecast.csv", index=False)
out = test[["load"]].copy()
out["pred_lgbm"] = pred_full
out["pred_p10"] = q_preds[0.1]
out["pred_p90"] = q_preds[0.9]
out.to_csv("results_predictions.csv")
print("\nsaved results_forecast.csv, results_predictions.csv")
