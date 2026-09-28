import { useCallback, useState } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || '';

/**
 * City-scale analysis for the map: consumption, population, industry and CO2.
 *
 * Kept out of App.jsx, which is already long. The hook owns the scan itself and
 * the GeoJSON for each layer, and fetches a layer only when it is first shown,
 * so switching layers off costs nothing.
 */
export default function useCityScan() {
  const [scan, setScan] = useState(null);
  const [layers, setLayers] = useState({});
  const [points, setPoints] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const analyse = useCallback(async (name, { cellSize = 1000, refresh = false } = {}) => {
    if (!name || !name.trim()) return null;
    setLoading(true);
    setError('');
    setLayers({});
    setPoints({});
    try {
      const res = await axios.post(`${API_URL}/api/city-scan`, {
        name: name.trim(), cell_size_m: cellSize, refresh,
      });
      setScan(res.data);
      return res.data;
    } catch (err) {
      const detail = err?.response?.data?.error;
      setError(detail || 'City analysis unavailable, try again shortly');
      setScan(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadLayer = useCallback(async (layer) => {
    if (!scan?.id || layers[layer]) return;
    try {
      const res = await axios.get(`${API_URL}/api/city-scan/${scan.id}/layers/${layer}`);
      setLayers((prev) => ({ ...prev, [layer]: res.data }));
    } catch {
      setError(`Could not load the ${layer} layer`);
    }
  }, [scan, layers]);

  const loadPoints = useCallback(async (kind) => {
    if (!scan?.id || points[kind]) return;
    try {
      const res = await axios.get(`${API_URL}/api/city-scan/${scan.id}/points/${kind}`);
      setPoints((prev) => ({ ...prev, [kind]: res.data.items || [] }));
    } catch {
      setError(`Could not load ${kind}`);
    }
  }, [scan, points]);

  const reset = useCallback(() => {
    setScan(null); setLayers({}); setPoints({}); setError('');
  }, []);

  return { scan, layers, points, loading, error, analyse, loadLayer, loadPoints, reset };
}
