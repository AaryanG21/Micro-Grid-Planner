import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

pred = pd.read_csv("results_predictions.csv", index_col=0, parse_dates=True)
wk = pred.loc["2018-01-15":"2018-01-22"]

fig, ax = plt.subplots(figsize=(10, 4.2))
ax.fill_between(wk.index, wk["pred_p10"], wk["pred_p90"], alpha=0.25,
                color="#4C72B0", label="P10 to P90 interval")
ax.plot(wk.index, wk["load"], color="#222222", lw=1.6, label="Actual load")
ax.plot(wk.index, wk["pred_lgbm"], color="#C44E52", lw=1.4, ls="--",
        label="LightGBM day-ahead forecast")
ax.set_ylabel("Load (MW)")
ax.set_title("Day-ahead load forecast vs actual, winter test week (PJM AEP)")
ax.legend(loc="upper right", fontsize=8)
ax.grid(alpha=0.3)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig("fig_forecast_week.png", dpi=160)

sweep = pd.read_csv("results_sizing.csv")
fig, ax = plt.subplots(figsize=(7.5, 4.4))
for b, g in sweep.groupby("Battery (kWh)"):
    ax.plot(g["PV (kWp)"], g["LPSP (%)"], marker="o", ms=4,
            label=f"{b} kWh battery")
ax.axhline(5, color="red", ls=":", lw=1.2)
ax.text(11.4, 5.6, "LPSP target 5%", color="red", fontsize=8, ha="right")
ax.set_xlabel("PV array size (kWp)")
ax.set_ylabel("Loss of power supply probability (%)")
ax.set_title("Reliability vs array and storage size, 20 kWh/day load")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig("fig_sizing_lpsp.png", dpi=160)
print("figures written")
