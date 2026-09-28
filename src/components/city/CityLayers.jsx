import React, { useEffect } from 'react';
import { GeoJSON, CircleMarker, Tooltip, LayersControl, LayerGroup, useMap } from 'react-leaflet';

/**
 * City-scale overlays for the existing site-picker map.
 *
 * Colour scales are per-city: each cell is shaded against the busiest cell in
 * that city, so shading compares places within one city and never claims a
 * comparison between cities.
 */

const RAMPS = {
  consumption: ['#fef3c7', '#fcd34d', '#f59e0b', '#d97706', '#92400e'],
  population: ['#e0f2fe', '#7dd3fc', '#38bdf8', '#0284c7', '#075985'],
  industry: ['#ede9fe', '#c4b5fd', '#a78bfa', '#7c3aed', '#4c1d95'],
};

function shade(value, max, ramp) {
  if (!max || value <= 0) return 'transparent';
  // Square root: without it a couple of dense cells flatten everything else.
  const t = Math.min(1, Math.sqrt(value / max));
  return ramp[Math.min(ramp.length - 1, Math.floor(t * ramp.length))];
}

function maxOf(geojson, key) {
  if (!geojson?.features?.length) return 0;
  return geojson.features.reduce((m, f) => Math.max(m, f.properties?.[key] || 0), 0);
}

function cellStyle(value, max, ramp) {
  const fill = shade(value, max, ramp);
  return {
    fillColor: fill,
    fillOpacity: fill === 'transparent' ? 0 : 0.55,
    color: '#1e293b',
    weight: 0.2,
  };
}

const number = (n, digits = 0) =>
  (n ?? 0).toLocaleString(undefined, { maximumFractionDigits: digits });

/**
 * Zoom to the analysed city. The map is mounted at world zoom for site
 * picking, where every city layer is far too small to see.
 */
function FitToCity({ bbox }) {
  const map = useMap();
  useEffect(() => {
    if (!bbox) return;
    const [south, west, north, east] = bbox;
    map.fitBounds([[south, west], [north, east]], { padding: [10, 10] });
  }, [bbox, map]);
  return null;
}

export default function CityLayers({ scan, layers, points, loadLayer, loadPoints, onPickSite }) {
  const hasScan = Boolean(scan?.id);

  // Every layer loads with the scan. Lazy loading on overlayadd was the first
  // attempt, but eventHandlers on LayersControl.Overlay never fire, so the
  // layers silently stayed empty. The payloads are one city's cells, already
  // cached server-side, so fetching them up front is cheap and predictable.
  useEffect(() => {
    if (!hasScan) return;
    ['score', 'consumption', 'population', 'industry'].forEach(loadLayer);
    ['industry', 'emitters'].forEach(loadPoints);
  }, [hasScan, scan?.id, loadLayer, loadPoints]);

  if (!hasScan) return null;

  const consumptionMax = maxOf(layers.consumption, 'kwh_day');
  const populationMax = maxOf(layers.population, 'population');
  const industryMax = maxOf(layers.industry, 'industrial_kwh_day');
  const scoreCells = layers.score?.features || [];

  return (
    <React.Fragment>
      <FitToCity bbox={scan.city?.bbox} />
      <LayersControl position="topright">
      {/* GeoJSON renders its data once at mount, so every key below carries
          the feature count: layers load after the control mounts, and without
          that the overlay stays empty for ever. The overlay NAME cannot change
          after mount either, so counts stay out of the labels. */}
      <LayersControl.Overlay checked name="Top candidate sites">
        <GeoJSON
          key={`score-${scan.id}-${scoreCells.length}`}
          data={layers.score || { type: 'FeatureCollection', features: [] }}
          style={(f) => ({
            fillColor: '#10b981',
            fillOpacity: 0.25 + 0.5 * (f.properties.score || 0),
            color: '#047857',
            weight: 1.5,
          })}
          onEachFeature={(feature, layer) => {
            const p = feature.properties;
            layer.bindTooltip(
              `#${p.rank} - score ${p.score}<br/>${number(p.kwh_day)} kWh/day` +
              `<br/>${number(p.population)} people<br/><em>click to plan here</em>`,
              { sticky: true },
            );
            layer.on('click', () => {
              const [[lon0, lat0], , [lon1, lat1]] = feature.geometry.coordinates[0];
              onPickSite?.({ lat: (lat0 + lat1) / 2, lon: (lon0 + lon1) / 2, rank: p.rank });
            });
          }}
        />
      </LayersControl.Overlay>

      <LayersControl.Overlay name="Estimated consumption">
        <GeoJSON
          key={`consumption-${scan.id}-${layers.consumption?.features?.length || 0}`}
          data={layers.consumption || { type: 'FeatureCollection', features: [] }}
          style={(f) => cellStyle(f.properties.kwh_day, consumptionMax, RAMPS.consumption)}
          onEachFeature={(f, layer) => layer.bindTooltip(
            `${number(f.properties.kwh_day)} kWh/day (${f.properties.tier})`, { sticky: true },
          )}
        />
      </LayersControl.Overlay>

      <LayersControl.Overlay name="Population density">
        <GeoJSON
          key={`population-${scan.id}-${layers.population?.features?.length || 0}`}
          data={layers.population || { type: 'FeatureCollection', features: [] }}
          style={(f) => cellStyle(f.properties.population, populationMax, RAMPS.population)}
          onEachFeature={(f, layer) => layer.bindTooltip(
            `${number(f.properties.population)} people`, { sticky: true },
          )}
        />
      </LayersControl.Overlay>

      <LayersControl.Overlay name="Industrial load">
        <GeoJSON
          key={`industry-${scan.id}-${layers.industry?.features?.length || 0}`}
          data={layers.industry || { type: 'FeatureCollection', features: [] }}
          style={(f) => cellStyle(f.properties.industrial_kwh_day, industryMax, RAMPS.industry)}
          onEachFeature={(f, layer) => layer.bindTooltip(
            `${f.properties.industrial_sites} sites - ${number(f.properties.industrial_kwh_day)} kWh/day`,
            { sticky: true },
          )}
        />
      </LayersControl.Overlay>

      <LayersControl.Overlay name="Industrial sites">
        <LayerGroupOfPoints
          items={points.industry}
          colour="#7c3aed"
          radius={(s) => Math.max(4, Math.min(14, Math.sqrt(s.footprint_sqm) / 12))}
          label={(s) => `${s.name || s.kind.replace('_', ' ')}<br/>${number(s.est_kwh_day)} kWh/day est.`}
        />
      </LayersControl.Overlay>

      <LayersControl.Overlay name="CO2 emitters">
        <LayerGroupOfPoints
          items={(points.emitters || []).filter((s) => !s.is_aggregate)}
          colour="#dc2626"
          radius={(s) => Math.max(5, Math.min(18, Math.sqrt(s.co2e_t) / 60))}
          label={(s) => `${s.name}<br/>${s.sector}<br/>${number(s.co2e_t)} t CO2e (${s.year})`}
        />
      </LayersControl.Overlay>
      </LayersControl>
    </React.Fragment>
  );
}

function LayerGroupOfPoints({ items, colour, radius, label }) {
  // LayerGroup, not a Fragment: LayersControl.Overlay takes ONE layer child,
  // and a Fragment of markers registers each marker as its own overlay row.
  return (
    <LayerGroup>
      {(items || []).map((item) => (
        <CircleMarker
          key={item.id}
          center={[item.lat, item.lon]}
          radius={radius(item)}
          pathOptions={{ color: colour, fillColor: colour, fillOpacity: 0.45, weight: 1 }}
        >
          <Tooltip sticky>
            <span dangerouslySetInnerHTML={{ __html: label(item) }} />
          </Tooltip>
        </CircleMarker>
      ))}
    </LayerGroup>
  );
}
