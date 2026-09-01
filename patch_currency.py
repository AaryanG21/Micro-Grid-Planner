import io

p = "app.py"
s = io.open(p, encoding="utf-8").read()

old_defaults = (
    '    "pv_cost_per_kw": 1200.0, "wind_cost_per_kw": 1500.0, '
    '"biomass_cost_per_kw": 2000.0,\n'
    '    "battery_cost_per_kwh": 400.0, "inverter_cost_per_kw": 200.0, '
    '"generator_cost_per_kw": 300.0,\n'
    '    "fuel_cost": 1.20, "discount_rate": 0.08, "project_life_years": 20,\n'
)
new_defaults = (
    "    # Costs converted from the original USD assumptions at ~95.5 INR/USD\n"
    "    # (a literal FX conversion of the underlying per-unit costs; not\n"
    "    # re-benchmarked against Indian hardware/fuel pricing).\n"
    '    "pv_cost_per_kw": 114600.0, "wind_cost_per_kw": 143250.0, '
    '"biomass_cost_per_kw": 191000.0,\n'
    '    "battery_cost_per_kwh": 38200.0, "inverter_cost_per_kw": 19100.0, '
    '"generator_cost_per_kw": 28650.0,\n'
    '    "fuel_cost": 114.6, "discount_rate": 0.08, "project_life_years": 20,\n'
)
assert s.count(old_defaults) == 1, "DEFAULT_ASSUMPTIONS anchor not found"
s = s.replace(old_defaults, new_defaults)

old_pdf = (
    '            ["Total Capital Expenditure (CAPEX)", f"${result.get(\'capex_total\', 0):,.2f}"],\n'
    '            ["Annual Operational Expenditure (OPEX)", f"${result.get(\'opex\', 0):,.2f}"],'
)
new_pdf = (
    '            ["Total Capital Expenditure (CAPEX)", f"\u20b9{result.get(\'capex_total\', 0):,.2f}"],\n'
    '            ["Annual Operational Expenditure (OPEX)", f"\u20b9{result.get(\'opex\', 0):,.2f}"],'
)
assert s.count(old_pdf) == 1, "PDF currency anchor not found"
s = s.replace(old_pdf, new_pdf)

io.open(p, "w", encoding="utf-8").write(s)
print("app.py: DEFAULT_ASSUMPTIONS and PDF export converted to INR")
