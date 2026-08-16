"""
Wires the site-scan feature into the existing app. Idempotent: safe to run
twice. Backs up every file it touches to <file>.bak-sitescan before writing.

  app.py           registers POST /api/site-scan
  src/App.jsx      map click triggers the scan and renders a result card
  requirements.txt adds pandas, scikit-learn, joblib
"""
import os
import shutil
import sys

CHANGES = []


def patch(path, old, new, label):
    if not os.path.exists(path):
        sys.exit(f"missing {path}, run this from the project root")
    src = open(path, encoding="utf-8").read()
    if new.strip() and new.split("\n")[0].strip() and new.split("\n")[0].strip() in src \
            and old not in src:
        CHANGES.append(f"  = {label}: already applied, skipped")
        return
    if old not in src:
        sys.exit(f"FAILED {label}: anchor not found in {path}\nanchor was:\n{old[:200]}")
    if src.count(old) != 1:
        sys.exit(f"FAILED {label}: anchor appears {src.count(old)} times in {path}")
    bak = path + ".bak-sitescan"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    open(path, "w", encoding="utf-8").write(src.replace(old, new, 1))
    CHANGES.append(f"  + {label}")


# --------------------------------------------------------------- 1. app.py
CORS_LINE = ('CORS(app, origins=[origin.strip() for origin in '
             'os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")])')
patch("app.py", CORS_LINE, CORS_LINE + """

from site_scan import register_site_scan

register_site_scan(app, cache=cache, limiter=limiter)""", "app.py: register /api/site-scan")

# ------------------------------------------------------------ 2. App.jsx
OLD_CLICK = """  const handleMapClick = (latlng) => {
    setFormData((current) => ({
      ...current,
      lat: parseFloat(latlng.lat.toFixed(4)),
      lon: parseFloat(latlng.lng.toFixed(4))
    }));
  };"""

NEW_CLICK = """  const [siteScan, setSiteScan] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanRadius, setScanRadius] = useState(50);

  const runSiteScan = async (lat, lon, radius) => {
    setScanning(true);
    setSiteScan(null);
    try {
      const res = await axios.post(`${API_URL}/api/site-scan`, { lat, lon, radius_m: radius });
      setSiteScan(res.data);
      if (res.data.building_count > 0) {
        setFormData((current) => ({
          ...current,
          buildings: res.data.building_count,
          load: Math.max(1, Math.round(res.data.estimated_daily_kwh))
        }));
      }
    } catch (err) {
      setSiteScan({ error: err?.response?.data?.error || 'Site scan unavailable' });
    } finally {
      setScanning(false);
    }
  };

  const handleMapClick = (latlng) => {
    const lat = parseFloat(latlng.lat.toFixed(4));
    const lon = parseFloat(latlng.lng.toFixed(4));
    setFormData((current) => ({ ...current, lat, lon }));
    runSiteScan(lat, lon, scanRadius);
  };"""

patch("src/App.jsx", OLD_CLICK, NEW_CLICK, "App.jsx: scan on map click")

OLD_COORDS = """              <div className="text-[10px] text-slate-400 mt-1 flex justify-between font-mono">
                <span>Lat: {formData.lat}</span>
                <span>Lon: {formData.lon}</span>
              </div>"""

NEW_COORDS = OLD_COORDS + """

              {/* SITE SCAN: buildings + ML demand estimate for the clicked point */}
              <div className="mt-2 p-3 rounded-lg border border-blue-200 bg-blue-50/60 text-xs">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-blue-900 uppercase tracking-wider text-[10px]">
                    Site Scan
                  </span>
                  <select
                    value={scanRadius}
                    onChange={(e) => {
                      const r = Number(e.target.value);
                      setScanRadius(r);
                      runSiteScan(formData.lat, formData.lon, r);
                    }}
                    className="text-[10px] bg-white border border-blue-200 rounded px-1 py-0.5 text-blue-900"
                  >
                    <option value={50}>50 m</option>
                    <option value={100}>100 m</option>
                    <option value={250}>250 m</option>
                    <option value={500}>500 m</option>
                  </select>
                </div>

                {scanning && (
                  <div className="text-blue-700 animate-pulse">Scanning OpenStreetMap…</div>
                )}

                {!scanning && !siteScan && (
                  <div className="text-slate-500">Click the map to scan buildings nearby.</div>
                )}

                {!scanning && siteScan?.error && (
                  <div className="text-amber-700">{siteScan.error}</div>
                )}

                {!scanning && siteScan && !siteScan.error && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-white rounded p-2 border border-blue-100">
                        <div className="text-[9px] text-slate-500 uppercase">Buildings</div>
                        <div className="text-base font-bold text-slate-800">{siteScan.building_count}</div>
                      </div>
                      <div className="bg-white rounded p-2 border border-blue-100">
                        <div className="text-[9px] text-slate-500 uppercase">Est. Demand</div>
                        <div className="text-base font-bold text-slate-800">
                          {siteScan.estimated_daily_kwh} <span className="text-[10px] font-normal">kWh/day</span>
                        </div>
                      </div>
                      <div className="bg-white rounded p-2 border border-blue-100">
                        <div className="text-[9px] text-slate-500 uppercase">Peak Load</div>
                        <div className="text-base font-bold text-slate-800">
                          {siteScan.profile ? siteScan.profile.peak_kw : '—'} <span className="text-[10px] font-normal">kW</span>
                        </div>
                      </div>
                      <div className="bg-white rounded p-2 border border-blue-100">
                        <div className="text-[9px] text-slate-500 uppercase">Roof PV Potential</div>
                        <div className="text-base font-bold text-slate-800">
                          {siteScan.roof_pv_potential_kwp} <span className="text-[10px] font-normal">kWp</span>
                        </div>
                      </div>
                    </div>

                    {siteScan.mix && Object.keys(siteScan.mix).length > 0 && (
                      <div className="bg-white rounded p-2 border border-blue-100 space-y-1">
                        {Object.entries(siteScan.mix).map(([key, m]) => (
                          <div key={key} className="flex justify-between text-[10px] text-slate-600">
                            <span>{m.label} × {m.count}</span>
                            <span className="font-mono">{m.kwh_day} kWh/day</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {siteScan.profile && (
                      <div className="bg-white rounded p-2 border border-blue-100">
                        <div className="flex items-end gap-[2px] h-10">
                          {siteScan.profile.hourly_kw.map((v, i) => {
                            const max = Math.max(...siteScan.profile.hourly_kw) || 1;
                            return (
                              <div
                                key={i}
                                title={`${i}:00 — ${v} kW`}
                                style={{ height: `${Math.max(4, (v / max) * 100)}%` }}
                                className="flex-1 bg-blue-400 rounded-sm"
                              />
                            );
                          })}
                        </div>
                        <div className="flex justify-between text-[9px] text-slate-400 mt-1 font-mono">
                          <span>00:00</span>
                          <span>peak {siteScan.profile.peak_hour}:00</span>
                          <span>23:00</span>
                        </div>
                      </div>
                    )}

                    {siteScan.note && <div className="text-amber-700">{siteScan.note}</div>}

                    <div className="text-[9px] text-slate-500 leading-snug border-t border-blue-100 pt-1">
                      Buildings from {siteScan.source}. Demand is estimated from per-building
                      benchmarks, not measured — edit the fields below to override. Hourly shape
                      predicted by {siteScan.profile ? siteScan.profile.method : 'n/a'}
                      {siteScan.profile?.model_test_mape_pct
                        ? ` (test MAPE ${siteScan.profile.model_test_mape_pct.toFixed(1)}%)`
                        : ''}.
                    </div>
                  </div>
                )}
              </div>"""

patch("src/App.jsx", OLD_COORDS, NEW_COORDS, "App.jsx: site scan result card")

# ------------------------------------------------------- 3. requirements
req = open("requirements.txt", encoding="utf-8").read()
need = [p for p in ("pandas>=2.0.0", "scikit-learn>=1.4.0", "joblib>=1.3.0")
        if p.split(">=")[0] not in req]
if need:
    shutil.copy2("requirements.txt", "requirements.txt.bak-sitescan")
    open("requirements.txt", "a", encoding="utf-8").write(
        ("" if req.endswith("\n") else "\n") + "\n".join(need) + "\n")
    CHANGES.append(f"  + requirements.txt: added {', '.join(need)}")
else:
    CHANGES.append("  = requirements.txt: already has ML deps, skipped")

# ------------------------------------------------------------ 4. gitignore
gi = open(".gitignore", encoding="utf-8").read() if os.path.exists(".gitignore") else ""
ignores = ["data/", "models/", "results_*.csv", "fig_*.png", "run_*.log", "*.bak-sitescan"]
missing = [i for i in ignores if i not in gi]
if missing:
    open(".gitignore", "a", encoding="utf-8").write(
        ("" if gi.endswith("\n") or not gi else "\n")
        + "\n# site-scan / ML artefacts\n" + "\n".join(missing) + "\n")
    CHANGES.append(f"  + .gitignore: added {len(missing)} entries")

print("patch complete:")
print("\n".join(CHANGES))
