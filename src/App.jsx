import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  ArrowLeft, Calendar, TrendingUp, Leaf, Building2, Zap, Battery, Sun, Wind,
  DollarSign, MapPin, Maximize, FileText, Save, LogIn, UserPlus,
  Cpu, BarChart3, CheckCircle2, ArrowRight, Sparkles, Lock, Mail, LogOut, Globe,
  Car, Clock, CreditCard, Activity, Search, Radar, ListChecks
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend,
  LineChart, Line
} from 'recharts';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import useCityScan from './hooks/useCityScan';
import CityLayers from './components/city/CityLayers';
import CitySummary from './components/city/CitySummary';

// Fix Leaflet marker icon URLs in React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'
});

function LocationMarker({ position, setPosition }) {
  useMapEvents({
    click(e) {
      setPosition(e.latlng);
    },
  });
  return position === null ? null : <Marker position={position}></Marker>;
}

// Commercial Hardware Catalog Presets
const HARDWARE_CATALOG = {
  // Costs converted from the original USD catalog at ~95.5 INR/USD (literal FX
  // conversion, not re-benchmarked against Indian hardware pricing)
  pv: [
    { id: 'generic_pv', name: 'Generic Tier-1 Solar PV', cost: 114600, spec: '380W Monocrystalline' },
    { id: 'sunpower', name: 'SunPower Maxeon 6 High-Efficiency', cost: 138475, spec: '440W High Efficiency (22.8%)' },
    { id: 'first_solar', name: 'First Solar Series 7 Utility PV', cost: 105050, spec: '535W Thin-Film Utility' },
  ],
  wind: [
    { id: 'generic_wind', name: 'Generic Commercial Wind Turbine', cost: 143250, spec: '1.5MW Onshore' },
    { id: 'vestas', name: 'Vestas V90 2.0 MW Turbine', cost: 160440, spec: '2.0MW 90m Rotor Onshore' },
    { id: 'ge_vernova', name: 'GE Vernova 2.8MW Utility Wind', cost: 135610, spec: '2.8MW High-Yield Onshore' },
  ],
  battery: [
    { id: 'generic_bess', name: 'Generic Lithium LFP Battery', cost: 38200, spec: 'LFP 90% Round-trip' },
    { id: 'tesla_megapack', name: 'Tesla Megapack 2XL Utility BESS', cost: 42020, spec: '3.9 MWh LFP Liquid Cooled' },
    { id: 'byd_bess', name: 'BYD Chez Commercial Energy Storage', cost: 35812, spec: 'High Density LFP Modular' },
  ]
};

function App({ initialView = 'dashboard', initialAuthMode = 'login', onNavigateHome }) {
  const [view, setView] = useState(initialView); // 'landing' | 'login' | 'dashboard'
  const [authMode, setAuthMode] = useState(initialAuthMode); // 'login' | 'register'
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'dispatch' | 'financing' | 'tou' | 'ev'
  
  useEffect(() => {
    if (view === 'landing' && onNavigateHome) {
      onNavigateHome();
    }
  }, [view, onNavigateHome]);
  
  const [loading, setLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState('');
  const [authSuccess, setAuthSuccess] = useState('');
  const [result, setResult] = useState(null);

  const [auth, setAuth] = useState({
    email: '',
    password: '',
    orgName: '',
    token: localStorage.getItem('microgrid_token') || '',
    user: JSON.parse(localStorage.getItem('microgrid_user') || 'null')
  });

  const [projectId, setProjectId] = useState(localStorage.getItem('microgrid_project_id') || '');
  const [analysisId, setAnalysisId] = useState(null);
  const [portfolio, setPortfolio] = useState([]);
  const [sensitivity, setSensitivity] = useState(null);

  // Core Parameters Form State
  const [formData, setFormData] = useState({
    lat: 12.3829,
    lon: 77.3947,
    load: 1000,
    buildings: 15,
    area_sqm: 5000,
    fuel_cost: 114.6, // was $1.20/L, converted at ~95.5 INR/USD
    renewables_target: 0.95,
    autonomy_days: 1,
    load_factor: 0.6,
    weather_case: 'P50'
  });

  // Feature 2: Selected Hardware Presets
  const [selectedHardware, setSelectedHardware] = useState({
    pv: 'generic_pv',
    wind: 'generic_wind',
    battery: 'generic_bess'
  });

  // Feature 3: Debt & Financing State
  const [financing, setFinancing] = useState({
    debtRatio: 0.70, // 70% Debt
    interestRate: 0.075, // 7.5%
    termYears: 15 // 15 Years
  });

  // Feature 4: Time-of-Use (TOU) Tariff State
  const [touTariff, setTouTariff] = useState({
    peakRate: 33.42, // was $0.35/kWh, converted at ~95.5 INR/USD (a literal FX
                      // conversion, not a locally-calibrated Indian tariff -- edit freely)
    offPeakRate: 11.46, // was $0.12/kWh, same conversion note as above
    peakHours: 6 // hours/day
  });

  // Feature 5: EV Fleet & Carbon Credit State
  const [evCarbon, setEvCarbon] = useState({
    evChargersCount: 4, // 50kW DC fast chargers
    carbonCreditPrice: 4297.5 // was $45/tonne CO2, converted at ~95.5 INR/USD
  });

  const loadPortfolio = React.useCallback(async () => {
    if (!auth.token) return;
    try {
      const API_URL = process.env.REACT_APP_API_URL || '';
      const response = await axios.get(`${API_URL}/api/portfolio`, {
        headers: { Authorization: `Bearer ${auth.token}` }
      });
      setPortfolio(response.data);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
  }, [auth.token]);

  useEffect(() => {
    if (auth.token) {
      loadPortfolio();
    }
  }, [auth.token, loadPortfolio]);

  const [siteScan, setSiteScan] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanRadius, setScanRadius] = useState(50);

  const runSiteScan = async (lat, lon, radius) => {
    const API_URL = process.env.REACT_APP_API_URL || '';
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
  };

  // ---- Search-by-name (Nominatim / OpenStreetMap geocoding, free, no key) ----
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [coordDraft, setCoordDraft] = useState({ lat: formData.lat, lon: formData.lon });

  useEffect(() => {
    setCoordDraft({ lat: formData.lat, lon: formData.lon });
  }, [formData.lat, formData.lon]);

  const city = useCityScan();

  // Clicking a ranked cell moves the site pin there and runs the existing
  // site scan, so the city view feeds straight into the normal planning flow.
  const handlePickCitySite = ({ lat, lon }) => {
    handleMapClick({ lat, lng: lon });
  };

  const handleCityAnalyse = async () => {
    const found = await city.analyse(searchQuery);
    if (found?.city) {
      handleMapClick({ lat: found.city.lat, lng: found.city.lon });
    }
  };

  const handleGeocodeSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchError('');
    try {
      const res = await axios.get('https://nominatim.openstreetmap.org/search', {
        params: { format: 'json', q: searchQuery, limit: 1 }
      });
      if (!res.data || res.data.length === 0) {
        setSearchError(`No location found for "${searchQuery}"`);
        return;
      }
      const { lat, lon } = res.data[0];
      handleMapClick({ lat: parseFloat(lat), lng: parseFloat(lon) });
    } catch (err) {
      setSearchError('Search unavailable, try again shortly');
    } finally {
      setSearching(false);
    }
  };

  const handleCoordApply = () => {
    const lat = parseFloat(coordDraft.lat);
    const lon = parseFloat(coordDraft.lon);
    if (Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      handleMapClick({ lat, lng: lon });
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((current) => ({
      ...current,
      [name]: value === '' ? '' : Number(value)
    }));
  };

  const handleHardwareSelect = (category, hardwareId) => {
    const hardware = HARDWARE_CATALOG[category].find(h => h.id === hardwareId);
    if (!hardware) return;

    setSelectedHardware(prev => ({ ...prev, [category]: hardwareId }));

    // Auto-update assumptions cost
    setFormData(prev => {
      const updatedAssumptions = { ...(prev.assumptions || {}) };
      if (category === 'pv') updatedAssumptions.pv_cost_per_kw = hardware.cost;
      if (category === 'wind') updatedAssumptions.wind_cost_per_kw = hardware.cost;
      if (category === 'battery') updatedAssumptions.battery_cost_per_kwh = hardware.cost;
      return { ...prev, assumptions: updatedAssumptions };
    });
  };

  const handleNewAnalysis = () => {
    setResult(null);
    setError('');
  };

  const handleRunAnalysis = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError('');

    // Feature 5 EV load adjustment calculation
    const evAddedDailyLoad = evCarbon.evChargersCount * 50 * 3; // 50kW chargers * 3h daily
    const adjustedPayload = {
      ...formData,
      load: formData.load + evAddedDailyLoad
    };

    const API_URL = process.env.REACT_APP_API_URL || '';

    try {
      let res;
      if (auth.token && projectId) {
        try {
          res = await axios.post(`${API_URL}/api/projects/${projectId}/analyze`, adjustedPayload, {
            headers: { Authorization: `Bearer ${auth.token}` }
          });
        } catch (projErr) {
          if (projErr.response && (projErr.response.status === 422 || projErr.response.status === 401 || projErr.response.status === 404)) {
            // Stale or invalid JWT token / session - clear token & fallback to public plan
            localStorage.removeItem('microgrid_token');
            localStorage.removeItem('microgrid_project_id');
            setAuth(prev => ({ ...prev, token: '', user: null }));
            setProjectId('');
            res = await axios.post(`${API_URL}/api/plan`, adjustedPayload);
          } else {
            throw projErr;
          }
        }
      } else {
        res = await axios.post(`${API_URL}/api/plan`, adjustedPayload);
      }
      setResult(res.data.results || res.data);
      setAnalysisId(res.data.analysis_id || null);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setAuthSuccess('');
    setAuthLoading(true);

    const API_URL = process.env.REACT_APP_API_URL || '';

    try {
      if (authMode === 'register') {
        await axios.post(`${API_URL}/api/auth/register`, {
          email: auth.email,
          password: auth.password,
          organization_name: auth.orgName || undefined
        });
        setAuthSuccess('Account created successfully! Logging in...');
      }

      const response = await axios.post(`${API_URL}/api/auth/login`, {
        email: auth.email,
        password: auth.password
      });

      const token = response.data.access_token;
      const userData = response.data.user;

      localStorage.setItem('microgrid_token', token);
      localStorage.setItem('microgrid_user', JSON.stringify(userData));

      setAuth(prev => ({ ...prev, token, user: userData }));
      setAuthSuccess('Authenticated successfully! Redirecting to workspace...');
      
      setTimeout(() => {
        setView('dashboard');
        loadPortfolio();
      }, 600);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('microgrid_token');
    localStorage.removeItem('microgrid_user');
    localStorage.removeItem('microgrid_project_id');
    setAuth({ email: '', password: '', orgName: '', token: '', user: null });
    setProjectId('');
    setPortfolio([]);
    setView('landing');
  };

  const createProject = async () => {
    if (!auth.token) {
      setError('Please sign in to save projects.');
      setView('login');
      return;
    }
    try {
      const API_URL = process.env.REACT_APP_API_URL || '';
      const response = await axios.post(`${API_URL}/api/projects`, {
        name: `Microgrid Site (${formData.lat}°, ${formData.lon}°)`,
        lat: formData.lat,
        lon: formData.lon
      }, { headers: { Authorization: `Bearer ${auth.token}` } });
      localStorage.setItem('microgrid_project_id', response.data.id);
      setProjectId(String(response.data.id));
      setError('');
      loadPortfolio();
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
  };

  const runSensitivity = async () => {
    setError('');
    try {
      const API_URL = process.env.REACT_APP_API_URL || '';
      let response;
      if (auth.token && projectId) {
        response = await axios.post(`${API_URL}/api/projects/${projectId}/sensitivity`, {
          ...formData,
          variable: 'fuel_cost',
          values: [0.8, 1.0, 1.2, 1.5]
        }, { headers: { Authorization: `Bearer ${auth.token}` } });
      } else {
        response = await axios.post(`${API_URL}/api/sensitivity`, {
          ...formData,
          variable: 'fuel_cost',
          values: [0.8, 1.0, 1.2, 1.5]
        });
      }
      setSensitivity(response.data.scenarios);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
  };

  const downloadReport = async () => {
    setError('');
    try {
      const API_URL = process.env.REACT_APP_API_URL || '';
      let response;
      if (auth.token && projectId && analysisId) {
        response = await axios.get(`${API_URL}/api/projects/${projectId}/report/${analysisId}.pdf`, {
          headers: { Authorization: `Bearer ${auth.token}` },
          responseType: 'blob'
        });
      } else {
        response = await axios.post(`${API_URL}/api/report/export.pdf`, formData, {
          responseType: 'blob'
        });
      }
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `microgrid-feasibility-report.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
  };

  const formatMoney = (val) => {
    if (!val) return '₹0';
    const abs = Math.abs(val);
    if (abs >= 10000000) {
      return `₹${(val / 10000000).toFixed(2)} Cr`;
    }
    if (abs >= 100000) {
      return `₹${(val / 100000).toFixed(2)} L`;
    }
    if (abs >= 1000) {
      return `₹${(val / 1000).toFixed(1)}K`;
    }
    return `₹${val.toFixed(1)}`;
  };

  // Helper calculations for Feature 3: Debt Schedule
  const computeDebtSchedule = () => {
    if (!result) return { debtAmount: 0, equityAmount: 0, annualPayment: 0, schedule: [] };
    const capex = result.capex_total || 0;
    const debtAmount = capex * financing.debtRatio;
    const equityAmount = capex - debtAmount;
    const r = financing.interestRate;
    const n = financing.termYears;

    let annualPayment = 0;
    if (r === 0) {
      annualPayment = debtAmount / n;
    } else {
      annualPayment = debtAmount * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
    }

    let balance = debtAmount;
    const schedule = [];
    for (let yr = 1; yr <= n; yr++) {
      const interest = balance * r;
      const principal = Math.min(balance, annualPayment - interest);
      balance = Math.max(0, balance - principal);
      schedule.append ? schedule.append({}) : schedule.push({
        year: yr,
        payment: annualPayment,
        interest,
        principal,
        balance
      });
    }
    return { debtAmount, equityAmount, annualPayment, schedule };
  };

  // Helper calculations for Feature 4: TOU Arbitrage
  const computeTouArbitrage = () => {
    if (!result) return { annualArbitrageSavings: 0, deltaRate: 0 };
    const battKwh = result.batt_kwh || 0;
    const deltaRate = Math.max(0, touTariff.peakRate - touTariff.offPeakRate);
    const annualArbitrageSavings = battKwh * 0.85 * 365 * deltaRate;
    return { annualArbitrageSavings, deltaRate };
  };

  // Helper calculations for Feature 5: Carbon Credit Revenue
  const computeCarbonRevenue = () => {
    if (!result) return 0;
    const co2Tonnes = result.co2_avoided_t || 0;
    return co2Tonnes * evCarbon.carbonCreditPrice;
  };

  // ----------------------------------------------------
  // VIEW 1: LANDING PAGE
  // ----------------------------------------------------
  if (view === 'landing') {
    if (onNavigateHome) {
      onNavigateHome();
      return null;
    }
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans selection:bg-blue-500 selection:text-white">
        <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setView('landing')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 via-indigo-600 to-emerald-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div>
              <span className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                Microgrid Feasibility Engine
              </span>
              <span className="block text-[10px] text-blue-400 font-semibold tracking-wider uppercase">Enterprise Platform</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {auth.token ? (
              <>
                <button
                  type="button"
                  onClick={() => setView('dashboard')}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg text-sm transition flex items-center gap-2 shadow-lg shadow-blue-600/30"
                >
                  <BarChart3 className="w-4 h-4" /> Go to Workspace
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="px-3 py-2 text-slate-400 hover:text-white text-sm transition"
                >
                  Sign Out
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => { setAuthMode('login'); setView('login'); }}
                  className="px-4 py-2 text-slate-300 hover:text-white text-sm font-semibold transition"
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => { setAuthMode('register'); setView('login'); }}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg text-sm transition shadow-lg shadow-blue-600/25 flex items-center gap-2"
                >
                  Create Account <ArrowRight className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </header>

        <section className="relative overflow-hidden pt-20 pb-16 px-6 max-w-6xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-semibold mb-8">
            <Sparkles className="w-4 h-4 text-blue-400" /> Commercial Microgrid Optimization & Dispatch Simulation
          </div>

          <h1 className="text-4xl md:text-6xl font-black tracking-tight text-white max-w-4xl mx-auto leading-tight mb-6">
            Complete Microgrid Feasibility, <span className="bg-gradient-to-r from-blue-400 via-indigo-300 to-emerald-400 bg-clip-text text-transparent">Financing & Dispatch</span> Platform
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Instantly model hybrid solar/wind/battery microgrids, select hardware models, simulate 24-hour dispatch curves, calculate TOU arbitrage & carbon credit revenues, and export executive PDF reports.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16">
            <button
              type="button"
              onClick={() => setView('dashboard')}
              className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl text-base transition shadow-xl shadow-blue-600/30 flex items-center justify-center gap-3"
            >
              Try Interactive Simulator <ArrowRight className="w-5 h-5" />
            </button>
            <button
              type="button"
              onClick={() => { setAuthMode('register'); setView('login'); }}
              className="w-full sm:w-auto px-8 py-4 border border-slate-700 hover:border-slate-500 bg-slate-800/60 text-slate-200 font-semibold rounded-xl text-base transition"
            >
              Sign Up / Register
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 max-w-5xl mx-auto pt-8 border-t border-slate-800">
            <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-800">
              <Activity className="w-5 h-5 text-blue-400 mx-auto mb-1.5" />
              <div className="text-xs font-bold text-white">24h Dispatch Curves</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-800">
              <Cpu className="w-5 h-5 text-amber-400 mx-auto mb-1.5" />
              <div className="text-xs font-bold text-white">Hardware Catalog</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-800">
              <CreditCard className="w-5 h-5 text-emerald-400 mx-auto mb-1.5" />
              <div className="text-xs font-bold text-white">Debt Amortization</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-800">
              <Clock className="w-5 h-5 text-purple-400 mx-auto mb-1.5" />
              <div className="text-xs font-bold text-white">TOU Arbitrage</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-800">
              <Car className="w-5 h-5 text-green-400 mx-auto mb-1.5" />
              <div className="text-xs font-bold text-white">EV & Carbon Credits</div>
            </div>
          </div>
        </section>

        <footer className="mt-auto border-t border-slate-800 px-6 py-8 text-center text-xs text-slate-500">
          Microgrid Feasibility Engine &copy; {new Date().getFullYear()} — SciPy HiGHS Solver & ReportLab Engine
        </footer>
      </div>
    );
  }

  // ----------------------------------------------------
  // VIEW 2: AUTHENTICATION (LOGIN / REGISTER)
  // ----------------------------------------------------
  if (view === 'login') {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col justify-center items-center p-6 selection:bg-blue-500 selection:text-white">
        <div className="w-full max-w-md bg-slate-800/90 border border-slate-700/80 rounded-2xl p-8 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center justify-between mb-8">
            <button
              type="button"
              onClick={() => setView('landing')}
              className="text-xs font-semibold text-slate-400 hover:text-white flex items-center gap-1 transition"
            >
              <ArrowLeft className="w-4 h-4" /> Back to Home
            </button>
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-blue-400" />
              <span className="font-bold text-sm text-white">Microgrid Planner</span>
            </div>
          </div>

          <h2 className="text-2xl font-black text-white text-center mb-2">
            {authMode === 'login' ? 'Welcome Back' : 'Create Organization Account'}
          </h2>
          <p className="text-xs text-slate-400 text-center mb-6">
            {authMode === 'login' ? 'Sign in to access saved microgrid projects.' : 'Register your organization to manage portfolio projects and export PDF reports.'}
          </p>

          <div className="grid grid-cols-2 bg-slate-900/80 rounded-xl p-1 mb-6 border border-slate-700/60">
            <button
              type="button"
              onClick={() => { setAuthMode('login'); setError(''); setAuthSuccess(''); }}
              className={`py-2 text-xs font-bold rounded-lg transition ${authMode === 'login' ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}
            >
              <LogIn className="w-3.5 h-3.5 inline mr-1" /> Sign In
            </button>
            <button
              type="button"
              onClick={() => { setAuthMode('register'); setError(''); setAuthSuccess(''); }}
              className={`py-2 text-xs font-bold rounded-lg transition ${authMode === 'register' ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}
            >
              <UserPlus className="w-3.5 h-3.5 inline mr-1" /> Create Account
            </button>
          </div>

          {error && <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs font-medium">{error}</div>}
          {authSuccess && <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs font-medium flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" /> {authSuccess}</div>}

          <form onSubmit={handleAuthSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={auth.email}
                  onChange={(e) => setAuth(prev => ({ ...prev, email: e.target.value }))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  minLength={8}
                  placeholder="At least 8 characters"
                  value={auth.password}
                  onChange={(e) => setAuth(prev => ({ ...prev, password: e.target.value }))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
                />
              </div>
            </div>

            {authMode === 'register' && (
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Organization Name (Optional)</label>
                <div className="relative">
                  <Building2 className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="text"
                    placeholder="Acme Microgrid Corp"
                    value={auth.orgName}
                    onChange={(e) => setAuth(prev => ({ ...prev, orgName: e.target.value }))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={authLoading}
              className="w-full mt-2 bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-xl text-sm transition shadow-lg shadow-blue-600/30 flex justify-center items-center gap-2"
            >
              {authLoading ? 'Processing...' : (authMode === 'login' ? 'Sign In to Workspace' : 'Create Account & Sign In')}
            </button>
          </form>

          <div className="relative my-6 text-center">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-700"></div></div>
            <span className="relative px-3 bg-slate-800 text-[11px] text-slate-500 font-semibold uppercase tracking-wider">or</span>
          </div>

          <button
            type="button"
            onClick={() => setView('dashboard')}
            className="w-full py-2.5 bg-slate-900/60 hover:bg-slate-900 border border-slate-700/80 text-slate-300 font-semibold rounded-xl text-xs transition flex justify-center items-center gap-2"
          >
            <Globe className="w-3.5 h-3.5 text-slate-400" /> Continue as Guest (Trial Simulator)
          </button>
        </div>
      </div>
    );
  }

  // ----------------------------------------------------
  // VIEW 3: DASHBOARD / SIMULATOR PAGE
  // ----------------------------------------------------
  const debtDetails = computeDebtSchedule();
  const touDetails = computeTouArbitrage();
  const carbonRev = computeCarbonRevenue();

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-800 font-sans flex flex-col selection:bg-blue-500 selection:text-white">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between sticky top-0 z-40 shadow-sm">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setView('landing')}
            className="flex items-center gap-2 text-slate-500 hover:text-slate-800 transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm font-medium">Home</span>
          </button>
          <div className="h-6 w-px bg-slate-200"></div>
          <div>
            <h1 className="text-lg font-bold text-slate-900 leading-tight flex items-center gap-2">
              <Zap className="w-5 h-5 text-blue-600" /> Microgrid Feasibility Platform
            </h1>
            <p className="text-xs text-slate-500">{formData.lat}°, {formData.lon}° — Interactive Optimizer</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex gap-2">
            <span className="px-3 py-1 bg-green-50 text-green-700 text-xs font-semibold rounded-full border border-green-200 flex items-center gap-1">
              <Sun className="w-3 h-3"/> NASA POWER
            </span>
            <span className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-semibold rounded-full border border-blue-200 flex items-center gap-1">
              <Wind className="w-3 h-3"/> Open-Meteo
            </span>
          </div>

          {auth.token ? (
            <div className="flex items-center gap-3 pl-3 border-l border-slate-200">
              <span className="text-xs font-semibold text-slate-700 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
                {auth.user?.email || 'User'} ({auth.user?.role || 'admin'})
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="text-xs font-semibold text-slate-500 hover:text-red-600 transition flex items-center gap-1"
              >
                <LogOut className="w-3.5 h-3.5" /> Sign Out
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => { setAuthMode('login'); setView('login'); }}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-bold px-4 py-2 rounded-lg transition shadow-sm"
            >
              Sign In to Save
            </button>
          )}
        </div>
      </header>

      {/* Select Location: prominent search + map + coordinate entry, matching the
          "easy to reach, eye-catching" layout requested. Feeds the same
          formData/site-scan pipeline the rest of the app already uses. */}
      <div className="max-w-7xl mx-auto p-6 pb-0 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Select Location card */}
          <div className="lg:col-span-2 bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
            <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-emerald-500 px-6 py-5">
              <div className="flex items-center gap-2 text-white font-bold text-base">
                <MapPin className="w-5 h-5" /> Select Location
              </div>
              <p className="text-blue-50 text-xs mt-0.5">Search a place, click the map, or enter coordinates directly</p>
            </div>

            <div className="p-5 space-y-4">
              <form onSubmit={handleGeocodeSearch} className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search location (e.g., Bengaluru, India)"
                    className="w-full pl-9 pr-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <button
                  type="submit"
                  disabled={searching}
                  className="px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-lg text-sm transition disabled:opacity-60"
                >
                  {searching ? 'Searching…' : 'Search'}
                </button>
                <button
                  type="button"
                  onClick={handleCityAnalyse}
                  disabled={city.loading || !searchQuery.trim()}
                  title="Map consumption, population, industry and CO2 across the whole city"
                  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg text-sm transition disabled:opacity-60"
                >
                  {city.loading ? 'Analysing…' : 'Analyse city'}
                </button>
              </form>
              {searchError && <p className="text-xs text-red-600">{searchError}</p>}
              {city.error && <p className="text-xs text-amber-700">{city.error}</p>}

              <div className="h-80 rounded-xl overflow-hidden border border-slate-200 z-0">
                <MapContainer
                  center={[formData.lat, formData.lon]}
                  zoom={4}
                  scrollWheelZoom={true}
                  style={{ height: '100%', width: '100%', zIndex: 0 }}
                >
                  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  <LocationMarker position={{ lat: formData.lat, lng: formData.lon }} setPosition={handleMapClick} />
                  <CityLayers
                    scan={city.scan}
                    layers={city.layers}
                    points={city.points}
                    loadLayer={city.loadLayer}
                    loadPoints={city.loadPoints}
                    onPickSite={handlePickCitySite}
                  />
                </MapContainer>
              </div>

              {city.scan && (
                <div className="p-3 rounded-xl border border-slate-200 bg-white">
                  <CitySummary scan={city.scan} onPickSite={handlePickCitySite} />
                </div>
              )}

              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={coordDraft.lat}
                    onChange={(e) => setCoordDraft((c) => ({ ...c, lat: e.target.value }))}
                    className="w-32 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={coordDraft.lon}
                    onChange={(e) => setCoordDraft((c) => ({ ...c, lon: e.target.value }))}
                    className="w-32 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleCoordApply}
                  className="px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold rounded-lg text-sm border border-blue-200 transition"
                >
                  Go to Coordinates
                </button>
              </div>
            </div>
          </div>

          {/* Right column: Analysis Control + How it works */}
          <div className="space-y-6">
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
              <h3 className="font-bold text-slate-900 text-sm mb-1">Analysis Control</h3>
              <p className="text-xs text-slate-500 mb-4">Start your energy analysis</p>

              <button
                type="button"
                onClick={() => handleRunAnalysis()}
                disabled={loading}
                className="w-full mb-4 px-4 py-3 bg-gradient-to-r from-emerald-500 to-blue-600 hover:from-emerald-400 hover:to-blue-500 text-white font-bold rounded-xl text-sm transition shadow-md flex items-center justify-center gap-2 disabled:opacity-60"
              >
                <Zap className="w-4 h-4" /> {loading ? 'Analyzing…' : 'Analyze Location'}
              </button>

              <ul className="space-y-2.5 text-xs text-slate-600">
                <li className="flex items-center gap-2"><Building2 className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" /> Building Detection</li>
                <li className="flex items-center gap-2"><Sun className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" /> Renewable Resource Analysis</li>
                <li className="flex items-center gap-2"><DollarSign className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" /> Financial Modeling</li>
                <li className="flex items-center gap-2"><Leaf className="w-3.5 h-3.5 text-green-500 flex-shrink-0" /> Carbon Impact Assessment</li>
              </ul>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
              <h3 className="font-bold text-slate-900 text-sm mb-3 flex items-center gap-2">
                <ListChecks className="w-4 h-4 text-blue-600" /> How it works
              </h3>
              <ol className="space-y-3 text-xs text-slate-600">
                <li className="flex gap-2">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-[10px]">1</span>
                  Pick a location on the map, search by name, or enter coordinates.
                </li>
                <li className="flex gap-2">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-[10px]">2</span>
                  Real-time data from NASA POWER, Open-Meteo and OpenStreetMap is fetched.
                </li>
                <li className="flex gap-2">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-[10px]">3</span>
                  We optimize a hybrid solar + wind + biomass mix and run a 20-year financial &amp; carbon model.
                </li>
              </ol>
            </div>
          </div>
        </div>
      </div>

      <main className="flex-1 max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-4 gap-6 w-full">
        {/* Left Column: Form Controls & Feature Settings */}
        <div className="lg:col-span-1 space-y-6">
          <form onSubmit={handleRunAnalysis} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-800">Parameters</h2>
              {result && (
                <button
                  type="button"
                  onClick={handleNewAnalysis}
                  className="text-xs text-blue-600 hover:text-blue-800 font-semibold"
                >
                  Reset
                </button>
              )}
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
                <MapPin className="w-3 h-3 text-blue-600"/> Location
              </label>
              <div className="flex items-center justify-between text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 font-mono">
                <span>{formData.lat}°, {formData.lon}°</span>
                <span className="text-slate-400 font-sans">↑ use map above</span>
              </div>

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
                        <div className="text-[9px] text-emerald-700 font-semibold mt-0.5">
                          ≈ {Math.ceil((siteScan.roof_pv_potential_kwp * 1000) / 550).toLocaleString()} panels @ 550 W
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
              </div>
            </div>

            {/* FEATURE 2: HARDWARE CATALOG SELECTOR */}
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
              <div className="text-xs font-bold text-slate-700 flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5 text-blue-600" /> Commercial Hardware Presets
              </div>
              
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase">Solar PV Model</label>
                <select
                  value={selectedHardware.pv}
                  onChange={(e) => handleHardwareSelect('pv', e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded p-1.5 text-xs text-slate-800"
                >
                  {HARDWARE_CATALOG.pv.map(h => (
                    <option key={h.id} value={h.id}>{h.name} (₹{h.cost.toLocaleString('en-IN')}/kW)</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase">Wind Turbine Model</label>
                <select
                  value={selectedHardware.wind}
                  onChange={(e) => handleHardwareSelect('wind', e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded p-1.5 text-xs text-slate-800"
                >
                  {HARDWARE_CATALOG.wind.map(h => (
                    <option key={h.id} value={h.id}>{h.name} (₹{h.cost.toLocaleString('en-IN')}/kW)</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase">BESS Battery Storage</label>
                <select
                  value={selectedHardware.battery}
                  onChange={(e) => handleHardwareSelect('battery', e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded p-1.5 text-xs text-slate-800"
                >
                  {HARDWARE_CATALOG.battery.map(h => (
                    <option key={h.id} value={h.id}>{h.name} (₹{h.cost.toLocaleString('en-IN')}/kWh)</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
                <Maximize className="w-3 h-3 text-slate-400"/> Available Area (sq m)
              </label>
              <input
                type="number"
                step="any"
                min="1"
                name="area_sqm"
                value={formData.area_sqm}
                onChange={handleChange}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-slate-800 text-sm focus:outline-none focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Base Daily Load (kWh)</label>
              <input
                type="number"
                step="any"
                min="1"
                name="load"
                value={formData.load}
                onChange={handleChange}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-slate-800 text-sm focus:outline-none focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Buildings Served</label>
              <input
                type="number"
                min="1"
                step="1"
                name="buildings"
                value={formData.buildings}
                onChange={handleChange}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-slate-800 text-sm focus:outline-none focus:border-blue-500"
                required
              />
            </div>

            {/* FEATURE 5: EV FLEET FAST CHARGERS INPUT */}
            <div className="p-3 bg-indigo-50/60 rounded-lg border border-indigo-200 space-y-2">
              <label className="block text-xs font-bold text-indigo-900 flex items-center justify-between">
                <span className="flex items-center gap-1"><Car className="w-3.5 h-3.5 text-indigo-600" /> EV DC Fast Chargers (50kW)</span>
                <span className="font-mono text-indigo-700">{evCarbon.evChargersCount} units</span>
              </label>
              <input
                type="range"
                min="0"
                max="20"
                step="1"
                value={evCarbon.evChargersCount}
                onChange={(e) => setEvCarbon(prev => ({ ...prev, evChargersCount: Number(e.target.value) }))}
                className="w-full accent-indigo-600 cursor-pointer"
              />
              <div className="text-[10px] text-indigo-700 font-medium">
                Adds +{(evCarbon.evChargersCount * 50 * 3).toLocaleString()} kWh/day fleet charging surge
              </div>
            </div>

            <details className="rounded-lg border border-slate-200 p-3 bg-slate-50/50">
              <summary className="cursor-pointer text-xs font-bold text-slate-600 select-none">Advanced Planning Assumptions</summary>
              <div className="mt-3 space-y-3">
                <label className="block text-xs text-slate-500">
                  Fuel cost (₹/L)
                  <input type="number" step="0.01" min="0" name="fuel_cost" value={formData.fuel_cost} onChange={handleChange} className="mt-1 w-full bg-white border border-slate-200 rounded p-2 text-slate-800" />
                </label>
                <label className="block text-xs text-slate-500">
                  Renewable target (0 to 1)
                  <input type="number" step="0.05" min="0" max="1" name="renewables_target" value={formData.renewables_target} onChange={handleChange} className="mt-1 w-full bg-white border border-slate-200 rounded p-2 text-slate-800" />
                </label>
                <label className="block text-xs text-slate-500">
                  Battery autonomy (days)
                  <input type="number" step="0.25" min="0" max="7" name="autonomy_days" value={formData.autonomy_days} onChange={handleChange} className="mt-1 w-full bg-white border border-slate-200 rounded p-2 text-slate-800" />
                </label>
                <label className="block text-xs text-slate-500">
                  Weather risk case
                  <select name="weather_case" value={formData.weather_case} onChange={(e) => setFormData(curr => ({ ...curr, weather_case: e.target.value }))} className="mt-1 w-full bg-white border border-slate-200 rounded p-2 text-slate-800">
                    <option value="P50">P50 (Median Weather)</option>
                    <option value="P90">P90 (Conservative Weather)</option>
                  </select>
                </label>
              </div>
            </details>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2.5 px-4 rounded-lg text-sm transition shadow-md shadow-blue-600/20 flex justify-center items-center gap-2"
            >
              {loading ? 'Solving Optimization...' : 'Run Feasibility Analysis'}
            </button>
          </form>

          {/* Project Workspace Box */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <h2 className="text-base font-bold text-slate-800 flex items-center justify-between">
              Workspace Projects
              <Save className="w-4 h-4 text-slate-400" />
            </h2>

            {!auth.token ? (
              <div className="space-y-3 pt-1">
                <p className="text-xs text-slate-500">
                  Sign in or create an account to persist saved projects and access portfolio analytics.
                </p>
                <button
                  type="button"
                  onClick={() => { setAuthMode('login'); setView('login'); }}
                  className="w-full py-2 bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-lg text-xs transition flex justify-center items-center gap-1.5"
                >
                  <LogIn className="w-3.5 h-3.5" /> Sign In / Register
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-2 font-medium">
                  Signed in as <span className="font-bold">{auth.user?.email}</span>
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={createProject}
                    className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg p-2 transition flex items-center justify-center gap-1"
                  >
                    <Save className="w-3.5 h-3.5" /> Save Project
                  </button>
                  <button
                    type="button"
                    onClick={loadPortfolio}
                    className="text-xs border border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold rounded-lg p-2 transition"
                  >
                    Load Portfolio
                  </button>
                </div>

                {portfolio.length > 0 && (
                  <div>
                    <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Select Project</label>
                    <select
                      value={projectId}
                      onChange={(e) => {
                        setProjectId(e.target.value);
                        localStorage.setItem('microgrid_project_id', e.target.value);
                      }}
                      className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs font-medium text-slate-800"
                    >
                      <option value="">Choose saved project</option>
                      {portfolio.map((item) => (
                        <option key={item.project.id} value={item.project.id}>
                          {item.project.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}
          </div>

          {error && (
            <div className="p-4 text-red-600 bg-red-50 border border-red-200 rounded-xl text-sm font-medium">
              {error}
            </div>
          )}
        </div>

        {/* Right Column: Multi-Tab Analytics Dashboard */}
        <div className="lg:col-span-3 space-y-6">
          {!result && !error && (
            <div className="p-12 text-slate-500 bg-white rounded-xl text-center border border-slate-200 shadow-sm flex flex-col items-center justify-center space-y-3">
              <Zap className="w-12 h-12 text-slate-300" />
              <div className="text-base font-bold text-slate-700">Ready to Compute Feasibility</div>
              <p className="text-xs text-slate-400 max-w-md">
                Configure your location on the map and click <span className="font-semibold text-slate-600">"Run Feasibility Analysis"</span> to generate microgrid metrics, 24h dispatch curves, debt schedules, and TOU arbitrage.
              </p>
            </div>
          )}

          {result && (
            <>
              {/* Action & Navigation Ribbon */}
              <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-sm">
                <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
                  <button
                    type="button"
                    onClick={() => setActiveTab('overview')}
                    className={`px-3 py-1.5 text-xs font-bold rounded-md transition ${activeTab === 'overview' ? 'bg-blue-600 text-white shadow' : 'text-slate-600 hover:text-slate-900'}`}
                  >
                    Overview
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('dispatch')}
                    className={`px-3 py-1.5 text-xs font-bold rounded-md transition ${activeTab === 'dispatch' ? 'bg-blue-600 text-white shadow' : 'text-slate-600 hover:text-slate-900'}`}
                  >
                    24h Dispatch Curve
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('financing')}
                    className={`px-3 py-1.5 text-xs font-bold rounded-md transition ${activeTab === 'financing' ? 'bg-blue-600 text-white shadow' : 'text-slate-600 hover:text-slate-900'}`}
                  >
                    Debt & Financing
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('tou')}
                    className={`px-3 py-1.5 text-xs font-bold rounded-md transition ${activeTab === 'tou' ? 'bg-blue-600 text-white shadow' : 'text-slate-600 hover:text-slate-900'}`}
                  >
                    TOU & EV Revenue
                  </button>
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={runSensitivity}
                    className="text-xs bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-lg px-3 py-2 transition"
                  >
                    Fuel Sensitivity
                  </button>
                  <button
                    type="button"
                    onClick={downloadReport}
                    className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg px-3 py-2 transition flex items-center gap-1"
                  >
                    <FileText className="w-3.5 h-3.5" /> Export Executive PDF
                  </button>
                </div>
              </div>

              {/* ---------------------------------------------------- */}
              {/* TAB 1: OVERVIEW & KPIS */}
              {/* ---------------------------------------------------- */}
              {activeTab === 'overview' && (
                <>
                  {/* Top 4 KPI Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="bg-orange-50/60 border border-orange-200 rounded-xl p-5 flex flex-col justify-between relative shadow-sm">
                      <div className="text-xs font-bold text-orange-600 uppercase tracking-wider mb-2">Total Investment</div>
                      <div className="text-3xl font-extrabold text-orange-700">{formatMoney(result.capex_total)}</div>
                      <div className="text-xs text-orange-600/80 mt-1">OPEX: {formatMoney(result.opex)}/yr</div>
                      <DollarSign className="w-5 h-5 text-orange-300 absolute top-4 right-4" />
                    </div>

                    <div className="bg-emerald-50/60 border border-emerald-200 rounded-xl p-5 flex flex-col justify-between relative shadow-sm">
                      <div className="text-xs font-bold text-emerald-600 uppercase tracking-wider mb-2">Payback Period</div>
                      <div className="text-3xl font-extrabold text-emerald-700">{result.payback_period}</div>
                      <div className="text-xs text-emerald-600/80 mt-1">20-Year Lifetime</div>
                      <Calendar className="w-5 h-5 text-emerald-300 absolute top-4 right-4" />
                    </div>

                    <div className="bg-blue-50/60 border border-blue-200 rounded-xl p-5 flex flex-col justify-between relative shadow-sm">
                      <div className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-2">20-Year ROI</div>
                      <div className="text-3xl font-extrabold text-blue-700">{result.roi_20yr?.toFixed(0)}%</div>
                      <div className="text-xs text-blue-600/80 mt-1">IRR: {result.irr?.toFixed(1)}%</div>
                      <TrendingUp className="w-5 h-5 text-blue-300 absolute top-4 right-4" />
                    </div>

                    <div className="bg-purple-50/60 border border-purple-200 rounded-xl p-5 flex flex-col justify-between relative shadow-sm">
                      <div className="text-xs font-bold text-purple-600 uppercase tracking-wider mb-2">CO2 Avoided / Yr</div>
                      <div className="text-3xl font-extrabold text-purple-700">{result.co2_avoided_t?.toFixed(1)} t</div>
                      <div className="text-xs text-purple-600/80 mt-1">≈ {(result.co2_avoided_t * 50).toFixed(0)} trees planted</div>
                      <Leaf className="w-5 h-5 text-purple-300 absolute top-4 right-4" />
                    </div>
                  </div>

                  {/* Specifications Strip */}
                  <div className="bg-white border border-slate-200 rounded-xl p-4 grid grid-cols-2 md:grid-cols-5 gap-4 shadow-sm">
                    <div className="flex items-center gap-3 border-r border-slate-100 last:border-0 pr-4">
                      <Building2 className="w-6 h-6 text-slate-400" />
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase font-bold">Buildings</div>
                        <div className="font-semibold text-slate-700">{result.buildings}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 border-r border-slate-100 last:border-0 pr-4">
                      <Zap className="w-6 h-6 text-slate-400" />
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase font-bold">System Capacity</div>
                        <div className="font-semibold text-slate-700">{result.system_capacity} kW</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 border-r border-slate-100 last:border-0 pr-4">
                      <Battery className="w-6 h-6 text-slate-400" />
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase font-bold">Battery Storage</div>
                        <div className="font-semibold text-slate-700">{result.batt_kwh} kWh</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 border-r border-slate-100 last:border-0 pr-4">
                      <Sun className="w-6 h-6 text-slate-400" />
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase font-bold">Solar Irradiance</div>
                        <div className="font-semibold text-slate-700">{result.solar_irradiance} kWh/m²</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Wind className="w-6 h-6 text-slate-400" />
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase font-bold">Wind Speed</div>
                        <div className="font-semibold text-slate-700">{result.wind_speed} m/s</div>
                      </div>
                    </div>
                  </div>

                  {/* Main Charts */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Energy Mix Chart */}
                    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col h-[380px]">
                      <div className="flex items-center gap-2 mb-1">
                        <TrendingUp className="w-4 h-4 text-slate-400"/>
                        <h2 className="text-base font-bold text-slate-800">Recommended Energy Mix</h2>
                      </div>
                      <p className="text-xs text-slate-500 mb-4">Optimal renewable allocation for this site</p>

                      <div className="flex-1 min-h-0 w-full relative">
                        {result.energy_mix && (
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={[
                                  { name: 'Solar', value: result.energy_mix.Solar, fill: '#f59e0b' },
                                  { name: 'Wind', value: result.energy_mix.Wind, fill: '#3b82f6' },
                                  { name: 'Biomass', value: result.energy_mix.Biomass, fill: '#22c55e' }
                                ]}
                                cx="50%" cy="50%"
                                innerRadius="60%" outerRadius="80%"
                                paddingAngle={2}
                                dataKey="value"
                              >
                                <Cell fill="#f59e0b" />
                                <Cell fill="#3b82f6" />
                                <Cell fill="#22c55e" />
                              </Pie>
                              <RechartsTooltip formatter={(val) => `${val}%`} />
                              <Legend verticalAlign="bottom" height={36}/>
                            </PieChart>
                          </ResponsiveContainer>
                        )}
                      </div>
                    </div>

                    {/* Area Chart: 20-Year Cashflow */}
                    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col h-[380px]">
                      <div className="flex items-center gap-2 mb-1">
                        <DollarSign className="w-4 h-4 text-slate-400"/>
                        <h2 className="text-base font-bold text-slate-800">20-Year Cumulative Cashflow</h2>
                      </div>
                      <p className="text-xs text-slate-500 mb-4">Investment recovery over project lifetime</p>

                      <div className="flex-1 min-h-0 w-full">
                        {result.cumulative_cashflow && (
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart
                              data={result.cumulative_cashflow.map((val, idx) => ({ year: idx, value: val }))}
                              margin={{ top: 10, right: 10, left: 10, bottom: 0 }}
                            >
                              <defs>
                                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                                </linearGradient>
                              </defs>
                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                              <XAxis dataKey="year" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                              <YAxis
                                axisLine={false}
                                tickLine={false}
                                tick={{ fill: '#64748b', fontSize: 12 }}
                                tickFormatter={(val) => {
                                  if (val === 0) return '0';
                                  return `${val > 0 ? '' : '-'}$${Math.abs(val)/1000}K`;
                                }}
                              />
                              <RechartsTooltip
                                formatter={(val) => `$${val.toLocaleString()}`}
                                labelFormatter={(label) => `Year ${label}`}
                              />
                              <Area
                                type="monotone"
                                dataKey="value"
                                stroke="#10b981"
                                strokeWidth={2}
                                fillOpacity={1}
                                fill="url(#colorValue)"
                              />
                            </AreaChart>
                          </ResponsiveContainer>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Sensitivity Grid */}
                  {sensitivity && (
                    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
                      <h2 className="font-bold text-slate-800 text-sm">Fuel-Cost Sensitivity Scenarios</h2>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {sensitivity.map((scenario) => (
                          <div key={scenario.value} className="border border-slate-200 rounded-lg p-3 text-xs bg-slate-50/50">
                            <div className="text-slate-500 font-bold">${scenario.value}/L Fuel</div>
                            <div className="font-semibold text-slate-800 mt-1">IRR: {scenario.irr}%</div>
                            <div className="text-slate-600">CAPEX: {formatMoney(scenario.capex_total)}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* ---------------------------------------------------- */}
              {/* FEATURE 1: 24-HOUR ENERGY DISPATCH VISUALIZER */}
              {/* ---------------------------------------------------- */}
              {activeTab === 'dispatch' && (
                <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                        <Activity className="w-5 h-5 text-blue-600" /> 24-Hour Energy Generation & Dispatch Curve
                      </h2>
                      <p className="text-xs text-slate-500">Hour-by-hour simulation of load demand vs. Solar PV, Wind, Biomass, BESS discharge, and Diesel backup.</p>
                    </div>
                  </div>

                  <div className="h-[420px] w-full pt-4">
                    {result.hourly_dispatch && (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={result.hourly_dispatch} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                          <XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 11 }} />
                          <YAxis tick={{ fill: '#64748b', fontSize: 11 }} unit=" kWh" />
                          <RechartsTooltip formatter={(val, name) => [`${val} kWh`, name]} />
                          <Legend verticalAlign="top" height={36} />
                          <Line type="monotone" dataKey="load" name="Load Demand" stroke="#0f172a" strokeWidth={3} dot={false} />
                          <Line type="monotone" dataKey="solar" name="Solar PV" stroke="#f59e0b" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="wind" name="Wind Power" stroke="#3b82f6" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="discharge" name="BESS Battery Discharge" stroke="#10b981" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="diesel" name="Diesel Genset" stroke="#ef4444" strokeWidth={2} strokeDasharray="4 4" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>
              )}

              {/* ---------------------------------------------------- */}
              {/* FEATURE 3: DEBT & FINANCING AMORTIZATION MODULE */}
              {/* ---------------------------------------------------- */}
              {activeTab === 'financing' && (
                <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-6">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                      <CreditCard className="w-5 h-5 text-blue-600" /> Debt & Capital Structure Calculator
                    </h2>
                    <p className="text-xs text-slate-500">Configure debt-to-equity ratio, interest rates, and loan terms to evaluate annual debt service payments.</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 p-4 bg-slate-50 rounded-xl border border-slate-200">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">
                        Debt Ratio: {(financing.debtRatio * 100).toFixed(0)}%
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={financing.debtRatio}
                        onChange={(e) => setFinancing(prev => ({ ...prev, debtRatio: Number(e.target.value) }))}
                        className="w-full accent-blue-600 cursor-pointer"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">
                        Interest Rate: {(financing.interestRate * 100).toFixed(1)}%
                      </label>
                      <input
                        type="range"
                        min="0.01"
                        max="0.15"
                        step="0.005"
                        value={financing.interestRate}
                        onChange={(e) => setFinancing(prev => ({ ...prev, interestRate: Number(e.target.value) }))}
                        className="w-full accent-blue-600 cursor-pointer"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">
                        Loan Term: {financing.termYears} Years
                      </label>
                      <input
                        type="range"
                        min="5"
                        max="30"
                        step="1"
                        value={financing.termYears}
                        onChange={(e) => setFinancing(prev => ({ ...prev, termYears: Number(e.target.value) }))}
                        className="w-full accent-blue-600 cursor-pointer"
                      />
                    </div>
                  </div>

                  {/* Summary Cards */}
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl">
                      <div className="text-[10px] font-bold text-blue-600 uppercase">Debt Amount</div>
                      <div className="text-xl font-black text-blue-800">{formatMoney(debtDetails.debtAmount)}</div>
                    </div>
                    <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
                      <div className="text-[10px] font-bold text-emerald-600 uppercase">Equity Required</div>
                      <div className="text-xl font-black text-emerald-800">{formatMoney(debtDetails.equityAmount)}</div>
                    </div>
                    <div className="p-4 bg-purple-50 border border-purple-200 rounded-xl">
                      <div className="text-[10px] font-bold text-purple-600 uppercase">Annual Debt Service</div>
                      <div className="text-xl font-black text-purple-800">{formatMoney(debtDetails.annualPayment)}/yr</div>
                    </div>
                  </div>

                  {/* Schedule Table */}
                  <div className="overflow-x-auto border border-slate-200 rounded-xl">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                        <tr>
                          <th className="p-3">Year</th>
                          <th className="p-3">Annual Payment</th>
                          <th className="p-3">Interest Paid</th>
                          <th className="p-3">Principal Paid</th>
                          <th className="p-3">Remaining Balance</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {debtDetails.schedule.map(row => (
                          <tr key={row.year} className="hover:bg-slate-50">
                            <td className="p-3 font-bold text-slate-800">Year {row.year}</td>
                            <td className="p-3 font-semibold">{formatMoney(row.payment)}</td>
                            <td className="p-3 text-slate-500">{formatMoney(row.interest)}</td>
                            <td className="p-3 text-emerald-600 font-semibold">{formatMoney(row.principal)}</td>
                            <td className="p-3 font-mono">{formatMoney(row.balance)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* ---------------------------------------------------- */}
              {/* FEATURE 4 & 5: TOU ARBITRAGE & CARBON CREDIT REVENUES */}
              {/* ---------------------------------------------------- */}
              {activeTab === 'tou' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* FEATURE 4: TOU ARBITRAGE */}
                  <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
                    <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <Clock className="w-5 h-5 text-purple-600" /> Time-of-Use (TOU) Grid Arbitrage
                    </h2>
                    <p className="text-xs text-slate-500">Calculate annual revenue savings from BESS charging off-peak and discharging peak grid hours.</p>

                    <div className="space-y-3 pt-2">
                      <div>
                        <label className="block text-xs font-bold text-slate-600 mb-1">Grid Peak Tariff (₹/kWh)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={touTariff.peakRate}
                          onChange={(e) => setTouTariff(prev => ({ ...prev, peakRate: Number(e.target.value) }))}
                          className="w-full bg-slate-50 border border-slate-200 rounded p-2 text-xs font-bold"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-600 mb-1">Grid Off-Peak Tariff (₹/kWh)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={touTariff.offPeakRate}
                          onChange={(e) => setTouTariff(prev => ({ ...prev, offPeakRate: Number(e.target.value) }))}
                          className="w-full bg-slate-50 border border-slate-200 rounded p-2 text-xs font-bold"
                        />
                      </div>
                    </div>

                    <div className="p-4 bg-purple-50 border border-purple-200 rounded-xl text-center">
                      <div className="text-xs font-bold text-purple-600 uppercase">Est. Annual Arbitrage Savings</div>
                      <div className="text-2xl font-black text-purple-800 mt-1">{formatMoney(touDetails.annualArbitrageSavings)}</div>
                      <div className="text-[11px] text-purple-600 mt-1">Based on ${touDetails.deltaRate.toFixed(2)}/kWh peak delta</div>
                    </div>
                  </div>

                  {/* FEATURE 5: CARBON CREDITS & EV REVENUE */}
                  <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
                    <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <Leaf className="w-5 h-5 text-emerald-600" /> Carbon Credit Revenue Modeling
                    </h2>
                    <p className="text-xs text-slate-500">Estimate additional revenue by monetizing avoided carbon emissions under carbon offset credit programs.</p>

                    <div className="space-y-3 pt-2">
                      <div>
                        <label className="block text-xs font-bold text-slate-600 mb-1">Carbon Credit Market Price (₹/tonne CO2)</label>
                        <input
                          type="number"
                          step="5"
                          value={evCarbon.carbonCreditPrice}
                          onChange={(e) => setEvCarbon(prev => ({ ...prev, carbonCreditPrice: Number(e.target.value) }))}
                          className="w-full bg-slate-50 border border-slate-200 rounded p-2 text-xs font-bold"
                        />
                      </div>
                    </div>

                    <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-center">
                      <div className="text-xs font-bold text-emerald-600 uppercase">Est. Carbon Credit Income</div>
                      <div className="text-2xl font-black text-emerald-800 mt-1">{formatMoney(carbonRev)}/year</div>
                      <div className="text-[11px] text-emerald-600 mt-1">From {result.co2_avoided_t?.toFixed(1)} tonnes avoided CO2</div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
