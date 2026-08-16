"""
Physical PV model on real TMY weather data, then an 8760-hour battery
simulation that sizes the array and storage against a reliability constraint.

This is the 'how many panels do I need' half of the planner, and it is
optimisation rather than machine learning.
"""
import os
import numpy as np
import pandas as pd
import pvlib
from pvlib.location import Location

# ------------------------------------------------- real TMY3 weather (pvlib)
tmy_path = os.path.join(os.path.dirname(pvlib.__file__), "data", "723170TYA.CSV")
tmy, meta = pvlib.iotools.read_tmy3(tmy_path, coerce_year=2019, map_variables=True)
tmy = tmy.iloc[:8760]
lat, lon, tz = meta["latitude"], meta["longitude"], meta["TZ"]
print(f"TMY site: {meta['Name'].strip()}, {meta['State']}  "
      f"lat={lat:.2f} lon={lon:.2f}  {len(tmy)} hourly records")
print(f"annual GHI = {tmy['ghi'].sum()/1000:.0f} kWh/m2   "
      f"mean PSH = {tmy['ghi'].sum()/1000/365:.2f} kWh/m2/day")

site = Location(lat, lon, tz=tz, altitude=meta["altitude"])
solpos = site.get_solarposition(tmy.index)

TILT, AZIMUTH = abs(lat), 180
extra = pvlib.irradiance.get_extra_radiation(tmy.index)
airmass = pvlib.atmosphere.get_relative_airmass(solpos["apparent_zenith"])
poa = pvlib.irradiance.get_total_irradiance(
    surface_tilt=TILT, surface_azimuth=AZIMUTH,
    solar_zenith=solpos["apparent_zenith"], solar_azimuth=solpos["azimuth"],
    dni=tmy["dni"], ghi=tmy["ghi"], dhi=tmy["dhi"],
    dni_extra=extra, airmass=airmass, model="haydavies")

cell_temp = pvlib.temperature.sapm_cell(
    poa_global=poa["poa_global"], temp_air=tmy["temp_air"],
    wind_speed=tmy["wind_speed"],
    **pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_glass"])

PDC0 = 1000.0            # 1 kWp reference array, watts
dc = pvlib.pvsystem.pvwatts_dc(poa["poa_global"], cell_temp, PDC0, gamma_pdc=-0.004)
SOILING_WIRING = 0.95    # soiling, mismatch, wiring losses
ac = pvlib.inverter.pvwatts(dc * SOILING_WIRING, pdc0=PDC0 * 1.1, eta_inv_nom=0.96)

yield_per_kwp = ac.sum() / 1000.0          # kWh per kWp per year
cf = yield_per_kwp / 8760 * 100
print(f"\nPV yield  = {yield_per_kwp:,.0f} kWh per kWp per year "
      f"({yield_per_kwp/365:.2f} kWh/kWp/day)")
poa_kwh = poa["poa_global"].sum() / 1000.0
print(f"capacity factor = {cf:.1f} %")
print(f"tilt gain (POA vs GHI) = {poa_kwh/(tmy['ghi'].sum()/1000):.3f}x   "
      f"performance ratio (yield / POA) = {yield_per_kwp/poa_kwh:.3f}")

# ------------------------------------------------- load profile (real shape)
pred = pd.read_csv("results_predictions.csv", index_col=0, parse_dates=True)
shape = pred["load"].iloc[:8760].values
DAILY_KWH = 20.0
load = shape / shape.mean() * (DAILY_KWH / 24.0)   # scaled to 20 kWh/day
print(f"\nload profile: {load.sum():,.0f} kWh/yr, "
      f"peak {load.max():.2f} kW, mean {load.mean():.2f} kW, "
      f"peak/mean ratio {load.max()/load.mean():.2f}")

# ------------------------------------ textbook rule-of-thumb sizing estimate
PSH = tmy["ghi"].sum() / 1000 / 365
PR = 0.75
rule_kwp = DAILY_KWH / (PSH * PR)
PANEL_W = 550
print(f"\nRule of thumb: {DAILY_KWH}/({PSH:.2f} x {PR}) = {rule_kwp:.2f} kWp "
      f"-> {int(np.ceil(rule_kwp*1000/PANEL_W))} x {PANEL_W} W panels")

# ---------------------------------------------- hourly simulation with battery
def simulate(kwp, batt_kwh, dod=0.80, eta=0.95, soc0=0.5):
    """Returns loss of power supply probability and curtailed fraction."""
    pv = ac.values / 1000.0 * kwp
    usable = batt_kwh * dod
    soc = usable * soc0
    unmet = curtailed = 0.0
    for p, l in zip(pv, load):
        net = p - l
        if net >= 0:
            room = (usable - soc) / eta
            charge = min(net, room)
            soc += charge * eta
            curtailed += net - charge
        else:
            need = -net / eta
            draw = min(need, soc)
            soc -= draw
            unmet += (need - draw) * eta
    return unmet / load.sum(), curtailed / pv.sum()

CAPEX_PV, CAPEX_BATT = 40_000, 18_000    # INR per kWp, INR per kWh (illustrative)
LPSP_TARGET = 0.05

rows = []
for kwp in [4, 5, 6, 7, 8, 10, 12]:
    for batt in [10, 20, 30, 40, 60]:
        lpsp, curt = simulate(kwp, batt)
        rows.append({"PV (kWp)": kwp, "Battery (kWh)": batt,
                     "Panels @550W": int(np.ceil(kwp * 1000 / PANEL_W)),
                     "LPSP (%)": lpsp * 100, "Curtailed (%)": curt * 100,
                     "Capex (INR lakh)": (kwp * CAPEX_PV + batt * CAPEX_BATT) / 1e5})
sweep = pd.DataFrame(rows)
feasible = sweep[sweep["LPSP (%)"] <= LPSP_TARGET * 100]
best = feasible.loc[feasible["Capex (INR lakh)"].idxmin()]

print("\n=== SIZING SWEEP (8760-hour simulation) ===")
print(sweep.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
print(f"\nCheapest configuration meeting LPSP <= {LPSP_TARGET*100:.0f}%:")
print(f"  PV {best['PV (kWp)']:.0f} kWp = {best['Panels @550W']:.0f} panels, "
      f"battery {best['Battery (kWh)']:.0f} kWh, "
      f"LPSP {best['LPSP (%)']:.2f}%, capex ~ INR {best['Capex (INR lakh)']:.2f} lakh")
print(f"  (rule of thumb said {rule_kwp:.2f} kWp and said nothing about storage)")

sweep.to_csv("results_sizing.csv", index=False)
print("\nsaved results_sizing.csv")
