import React from 'react';

/**
 * What the city scan found, and how much of it is measured rather than guessed.
 *
 * The tier badge and the source list are the point of this panel: the numbers
 * mean very different things depending on whether a utility published them or
 * we estimated them from satellites.
 */

const TIER_STYLE = {
  official: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  calibrated: 'bg-sky-100 text-sky-800 border-sky-300',
  estimated: 'bg-amber-100 text-amber-800 border-amber-300',
};

const TIER_LABEL = {
  official: 'Official data',
  calibrated: 'Calibrated to official total',
  estimated: 'Estimated from global data',
};

const number = (n, digits = 0) =>
  (n ?? 0).toLocaleString(undefined, { maximumFractionDigits: digits });

export default function CitySummary({ scan, onPickSite }) {
  if (!scan) return null;
  const totals = scan.consumption?.totals || {};
  const cal = scan.calibration;
  const failed = scan.failed_layers || [];

  return (
    <div className="space-y-3 text-xs">
      <div className="flex items-center justify-between gap-2">
        <div className="font-bold text-slate-800 text-sm">{scan.city?.name}</div>
        <span className={`px-2 py-0.5 rounded-full border text-[10px] font-semibold ${TIER_STYLE[scan.tier] || TIER_STYLE.estimated}`}>
          {TIER_LABEL[scan.tier] || scan.tier}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Stat label="People" value={number(totals.population)} />
        <Stat label="Demand" value={`${number(totals.gwh_year, 1)} GWh/yr`} />
        <Stat label="Industry" value={`${number(scan.industry?.count)} sites`} />
      </div>

      {cal && (
        <div className="p-2 rounded-lg bg-sky-50 border border-sky-200 text-sky-900 space-y-1">
          <div className="font-semibold">
            Calibrated against {cal.utility} FY{cal.financial_year}
          </div>
          <div>
            {number(cal.official_kwh_per_capita_year, 1)} kWh per person per year, from official
            domestic sales across {number(cal.service_area_population)} people in the service area.
          </div>
          <div>
            Before calibration this model was <strong>{cal.pre_calibration_error_pct}%</strong> off
            that figure. {cal.city_share_of_service_area_pct}% of the service area's people live in
            this city.
          </div>
          <div className="text-[10px] text-sky-700">{cal.caveat}</div>
        </div>
      )}

      {scan.emissions && (
        <div className="p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-900">
          <strong>{number(scan.emissions.facility_co2e_t)} t CO2e</strong> from{' '}
          {scan.emissions.facility_count} facilities ({scan.emissions.year}). City-wide totals from
          Climate TRACE cover {scan.emissions.fua_name}.
        </div>
      )}

      {failed.length > 0 && (
        <div className="p-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-900">
          Unavailable: {failed.join(', ')}. The rest of the scan is unaffected.
        </div>
      )}

      {scan.scoring?.top?.length > 0 && (
        <div>
          <div className="font-semibold text-slate-700 mb-1">Best candidate sites</div>
          <div className="space-y-1">
            {scan.scoring.top.slice(0, 5).map((site) => (
              <button
                type="button"
                key={site.id}
                onClick={() => onPickSite?.({ lat: site.lat, lon: site.lon, rank: site.rank })}
                className="w-full flex items-center justify-between gap-2 p-1.5 rounded-lg border border-slate-200 hover:border-emerald-400 hover:bg-emerald-50 transition text-left"
              >
                <span className="font-semibold text-slate-700">#{site.rank}</span>
                <span className="text-slate-600">{number(site.kwh_day)} kWh/day</span>
                <span className="text-slate-500">{number(site.population)} people</span>
                <span className="text-emerald-700 font-semibold">{site.score}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <details className="text-[10px] text-slate-500">
        <summary className="cursor-pointer font-semibold text-slate-600">Data sources</summary>
        <ul className="mt-1 space-y-1">
          {Object.entries(scan.sources || {}).map(([key, src]) => (
            <li key={key}>
              <span className="font-semibold capitalize">{key.replace('_', ' ')}:</span>{' '}
              {src.name}. {src.licence}
            </li>
          ))}
        </ul>
        <p className="mt-1">{scan.consumption?.method}</p>
      </details>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
      <div className="text-[9px] uppercase tracking-wider text-slate-500 font-bold">{label}</div>
      <div className="text-sm font-bold text-slate-800">{value}</div>
    </div>
  );
}
