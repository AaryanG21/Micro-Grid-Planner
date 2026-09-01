"""
Adds the solar panel count to the Site Scan card.

The scan already returns roof_pv_potential_kwp (usable roof area converted to
installable capacity). Users asked for the answer in panels, not just kWp, so
this derives panel count at a standard 550 W module and shows it under the
capacity figure.

  panels = ceil(kWp * 1000 / 550)
"""
import io
import shutil

path = "src/App.jsx"
shutil.copy2(path, path + ".bak-panels")
src = io.open(path, encoding="utf-8").read()

old = """                      <div className="bg-white rounded p-2 border border-blue-100">
                        <div className="text-[9px] text-slate-500 uppercase">Roof PV Potential</div>
                        <div className="text-base font-bold text-slate-800">
                          {siteScan.roof_pv_potential_kwp} <span className="text-[10px] font-normal">kWp</span>
                        </div>
                      </div>"""

new = """                      <div className="bg-white rounded p-2 border border-blue-100">
                        <div className="text-[9px] text-slate-500 uppercase">Roof PV Potential</div>
                        <div className="text-base font-bold text-slate-800">
                          {siteScan.roof_pv_potential_kwp} <span className="text-[10px] font-normal">kWp</span>
                        </div>
                        <div className="text-[9px] text-emerald-700 font-semibold mt-0.5">
                          ≈ {Math.ceil((siteScan.roof_pv_potential_kwp * 1000) / 550).toLocaleString()} panels @ 550 W
                        </div>
                      </div>"""

assert src.count(old) == 1, f"anchor found {src.count(old)} times"
src = src.replace(old, new)
io.open(path, "w", encoding="utf-8").write(src)
print("App.jsx: added panel count to Roof PV Potential tile")
