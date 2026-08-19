import io

p = "app.py"
s = io.open(p, encoding="utf-8").read()

old_default = (
    '    "battery_dod": 0.90, "battery_roundtrip_efficiency": 0.90, '
    '"performance_ratio": 0.75,\n}'
)
new_default = (
    '    "battery_dod": 0.90, "battery_roundtrip_efficiency": 0.90, '
    '"performance_ratio": 0.75,\n'
    "    # Floor on each renewable's share of daily load, so a single very cheap\n"
    "    # resource (e.g. strong, steady wind) can't drive the LP to a 100%\n"
    "    # single-source design. A pure cost-minimising LP always picks a corner\n"
    "    # solution otherwise; real systems diversify for resilience against any\n"
    "    # one resource underperforming (a calm week, a cloudy spell).\n"
    '    "min_solar_share": 0.15, "min_wind_share": 0.15,\n}'
)
assert s.count(old_default) == 1, "default assumptions anchor not found"
s = s.replace(old_default, new_default)

old_lp = (
    "    max_pv = plan.area_sqm / 5\n"
    "    result = linprog(\n"
    "        capital_costs,\n"
    "        A_ub=[[-daily_generation[0], -daily_generation[1], "
    "-daily_generation[2]], [-daily_generation[0], -daily_generation[1], 0]],\n"
    "        b_ub=[-load, -(plan.renewables_target * load)],\n"
    "        bounds=[(0, max_pv), (0, None), (0, None)], method=\"highs\",\n"
    "    )"
)
new_lp = (
    "    max_pv = plan.area_sqm / 5\n\n"
    "    # Diversification floor: each of solar and wind must cover at least\n"
    "    # min_*_share of the daily load, whenever the resource can physically\n"
    "    # deliver that (enough irradiance/wind, and enough roof area for PV).\n"
    "    # Without this an LP minimising capex per unit generation collapses to\n"
    "    # whichever single source is cheapest per kWh at this site, e.g. a very\n"
    "    # windy location gets 0% solar even though diversifying reduces the risk\n"
    "    # of a multi-day shortfall if that one resource underperforms.\n"
    "    pv_min = 0.0\n"
    "    if pv_kwh_per_kw_day > 0.05:\n"
    '        pv_min = min(max_pv, assumptions["min_solar_share"] * load / pv_kwh_per_kw_day)\n'
    "    wind_min = 0.0\n"
    "    if daily_generation[1] > 0.05:\n"
    '        wind_min = assumptions["min_wind_share"] * load / daily_generation[1]\n\n'
    "    result = linprog(\n"
    "        capital_costs,\n"
    "        A_ub=[[-daily_generation[0], -daily_generation[1], "
    "-daily_generation[2]], [-daily_generation[0], -daily_generation[1], 0]],\n"
    "        b_ub=[-load, -(plan.renewables_target * load)],\n"
    "        bounds=[(pv_min, max_pv), (wind_min, None), (0, None)], method=\"highs\",\n"
    "    )"
)
assert s.count(old_lp) == 1, "linprog anchor not found"
s = s.replace(old_lp, new_lp)

io.open(p, "w", encoding="utf-8").write(s)
print("diversification floor added")
