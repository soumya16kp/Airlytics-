import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { useNavigate, NavLink } from 'react-router-dom';
import { logout, reset } from '../store/authSlice';
import locationService from '../services/locationService';
import LocationSelector from './LocationSelector';
import {
  LogOut, User, MapPin,
  TrendingUp, BarChart3, Activity, Wind,
  ArrowUp, ArrowDown, RefreshCw
} from 'lucide-react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from 'recharts';
import RegionalMap from './RegionalMap';
import GroundData from './GroundData';

// Pollutant display config
const POLLUTANT_LABELS = {
  co:  { name: 'CO',  full: 'Carbon Monoxide',   unit: 'mg/m³',   whoLimit: 4,    molarMass: 28.01 },
  no2: { name: 'NO₂', full: 'Nitrogen Dioxide',   unit: 'µg/m³',   whoLimit: 40,   molarMass: 46.01 },
  so2: { name: 'SO₂', full: 'Sulfur Dioxide',     unit: 'µg/m³',   whoLimit: 40,   molarMass: 64.07 },
  o3:  { name: 'O₃',  full: 'Ozone',              unit: 'µg/m³',   whoLimit: 100,  molarMass: 48.00 },
};

const FUTURE_RANGES = ['1D', '1W', '1M', '3M', '6M', '1Y'];
const HISTORY_RANGES = ['H1M', 'H3M', 'H1Y', 'H3Y', 'H5Y'];

// Prediction API router by pollutant
const predictByType = {
  co:  locationService.predictCO,
  no2: locationService.predictNO2,
  o3:  locationService.predictO3,
  so2: locationService.predictSO2,
};

const predictAtByType = {
  co:  locationService.predictCOAt,
  no2: locationService.predictNO2At,
  o3:  locationService.predictO3At,
  so2: locationService.predictSO2At,
};

const PARAMETER_CONFIG = {
  co: [
    { key: 'urban', label: 'Urban Fraction', min: 0, max: 100, step: 1, unit: '%', default: 50 },
    { key: 'night', label: 'Nightlight Intensity', min: 0, max: 63, step: 1, unit: 'DN', default: 30 },
    { key: 'temp', label: 'Temperature', min: 10, max: 50, step: 0.5, unit: '°C', default: 27 },
    { key: 'wind_speed', label: 'Wind Speed', min: 0, max: 20, step: 0.2, unit: 'm/s', default: 3 },
    { key: 'pressure', label: 'Surface Pressure', min: 950, max: 1050, step: 1, unit: 'hPa', default: 1010 },
  ],
  no2: [
    { key: 'pop', label: 'Population', min: 1000, max: 1000000, step: 1000, unit: '', default: 5000 },
    { key: 'temp', label: 'Temperature', min: 10, max: 50, step: 0.5, unit: '°C', default: 27 },
    { key: 'wind_speed', label: 'Wind Speed', min: 0, max: 20, step: 0.2, unit: 'm/s', default: 3 },
    { key: 'cld', label: 'Cloud Cover', min: 0, max: 100, step: 1, unit: '%', default: 20 },
    { key: 'urban', label: 'Urbanization', min: 0, max: 100, step: 1, unit: '%', default: 40 },
  ],
  so2: [
    { key: 'pop', label: 'Population Density', min: 1000, max: 1000000, step: 1000, unit: '', default: 5000 },
    { key: 'temp', label: 'Temperature', min: 10, max: 50, step: 0.5, unit: '°C', default: 27 },
    { key: 'wind_speed', label: 'Wind Speed', min: 0, max: 20, step: 0.2, unit: 'm/s', default: 3 },
    { key: 'cld', label: 'Cloud Cover', min: 0, max: 100, step: 1, unit: '%', default: 20 },
    { key: 'pbl', label: 'PBL Height', min: 100, max: 3000, step: 50, unit: 'm', default: 800 },
  ],
  o3: [
    { key: 'temp', label: 'Temperature', min: 10, max: 50, step: 0.5, unit: '°C', default: 27 },
    { key: 'solar', label: 'Solar Radiation', min: 0, max: 1200, step: 10, unit: 'W/m²', default: 600 },
    { key: 'wind_speed', label: 'Wind Speed', min: 0, max: 20, step: 0.2, unit: 'm/s', default: 3 },
    { key: 'pbl', label: 'PBL Height', min: 100, max: 3000, step: 50, unit: 'm', default: 800 },
    { key: 'pop', label: 'Population', min: 1000, max: 1000000, step: 1000, unit: '', default: 5000 },
  ]
};

const POLLUTANT_DETAILS = {
  co: {
    description: "Carbon Monoxide (CO) is a colorless, odorless gas. It is a product of incomplete combustion of fossil fuels, mainly from vehicle emissions and industrial activities.",
    health_advice: {
      'Excellent': { health: "Air quality is ideal. No risk of CO exposure.", action: "Perfect for all outdoor and indoor activities." },
      'Good': { health: "CO levels are within safe limits. No noticeable health effects.", action: "Normal activities. Ensure proper ventilation in rooms with heaters." },
      'Moderate': { health: "Sensitive individuals may experience slight fatigue or reduced exercise tolerance.", action: "Avoid prolonged exposure near heavy traffic or industrial areas." },
      'Poor': { health: "Increased risk of headaches, dizziness, and reduced oxygen delivery to the heart.", action: "Limit outdoor time. Move to areas with better ventilation immediately." },
      'Hazardous': { health: "Dangerous CO levels. Can cause severe headaches, confusion, and cardiovascular distress.", action: "EVACUATE area. Seek fresh air and medical attention immediately." }
    }
  },
  no2: {
    description: "Nitrogen Dioxide (NO₂) is a reddish-brown gas. It primarily comes from burning fuel in vehicles and power plants, contributing to smog and acid rain.",
    health_advice: {
      'Excellent': { health: "Air is very clean. No respiratory risks.", action: "Ideal for outdoor sports and high-intensity activities." },
      'Good': { health: "Safe levels for the general population. Minimal risk.", action: "Normal outdoor activities are recommended." },
      'Moderate': { health: "May cause increased bronchial reactivity in asthmatics.", action: "Asthmatics should monitor symptoms and limit heavy outdoor work." },
      'Poor': { health: "Increased risk of respiratory infection and aggravation of lung disease.", action: "Children and elderly should stay indoors. Avoid high-traffic zones." },
      'Hazardous': { health: "Severe respiratory irritation. Significant risk of asthma attacks.", action: "Everyone should avoid outdoor physical activity. Keep windows closed." }
    }
  },
  so2: {
    description: "Sulfur Dioxide (SO₂) is a pungent, colorless gas produced by volcanic eruptions and industrial processes like coal burning and metal smelting.",
    health_advice: {
      'Excellent': { health: "No sulfurous pollutants detected. Very safe air.", action: "Safe for all outdoor recreational activities." },
      'Good': { health: "SO₂ levels are low and safe for most individuals.", action: "Normal activities. Industrial workers should follow safety protocols." },
      'Moderate': { health: "May cause minor eye or throat irritation for some people.", action: "Reduce time spent near power plants or heavy industrial sites." },
      'Poor': { health: "Wheezing, chest tightness, and shortness of breath likely for asthmatics.", action: "Avoid outdoor activities. Use air filtration if near industrial zones." },
      'Hazardous': { health: "Severe respiratory distress. High risk of permanent lung damage.", action: "STAY INDOORS. Use N95 masks if you must go outside near factories." }
    }
  },
  o3: {
    description: "Ground-level Ozone (O₃) is a secondary pollutant formed when sunlight reacts with other pollutants. It is a major component of urban smog.",
    health_advice: {
      'Excellent': { health: "Ozone levels are at a natural baseline. No risk.", action: "Perfect for hiking and outdoor activities." },
      'Good': { health: "Very low ozone concentration. Air is fresh.", action: "Normal outdoor activities are safe." },
      'Moderate': { health: "Coughing and throat irritation may occur during heavy exercise.", action: "Limit afternoon outdoor activities when sunlight is strongest." },
      'Poor': { health: "Reduced lung function. Chest pain and inflammation of the airways.", action: "Stay indoors between 12 PM and 5 PM. Use air conditioning." },
      'Hazardous': { health: "Severe lung damage. Ozone levels are dangerously high.", action: "Avoid all outdoor exertion. Keep vulnerable people in filtered air." }
    }
  }
};

const Dashboard = ({ pollutantType = 'co' }) => {
  const pollutant = POLLUTANT_LABELS[pollutantType] || POLLUTANT_LABELS.co;
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { user, isLoggedIn, profile } = useSelector((state) => state.auth);

  const [predData, setPredData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [aiInsight, setAiInsight] = useState(null);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [hasAutoLocated, setHasAutoLocated] = useState(false);
  const [showLocationSelector, setShowLocationSelector] = useState(false);
  const [syncedAt, setSyncedAt] = useState(null);
  const [syncedAgo, setSyncedAgo] = useState(null);
  const [selectedCoords, setSelectedCoords] = useState(null);

  const [timeRange, setTimeRange] = useState('1D');
  const [simData, setSimData] = useState(null); 
  const [overrides, setOverrides] = useState({});
  const [isSimulating, setIsSimulating] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState(null);
  
  const WHO_SAFE_LIMIT = pollutant.whoLimit;

  const getStatus = useCallback((val, limit = WHO_SAFE_LIMIT) => {
    if (!val || !limit) return null;
    const ratio = val / limit;
    if (ratio <= 0.5) return { label: 'Excellent', color: '#059669', emoji: '🟢' };
    if (ratio <= 1.0) return { label: 'Good',      color: '#10b981', emoji: '🟢' };
    if (ratio <= 1.5) return { label: 'Moderate',   color: '#f59e0b', emoji: '🟡' };
    if (ratio <= 2.0) return { label: 'Poor',       color: '#f97316', emoji: '🟠' };
    return              { label: 'Hazardous', color: '#ef4444', emoji: '🔴' };
  }, [WHO_SAFE_LIMIT]);

  // ── Scientific Conversion Layer ──
  const processPollutantData = useCallback((data) => {
    if (!data) return data;
    
    const rawValue = data.base_value_2026;
    const needsConversion = ['co', 'no2', 'so2', 'o3'].includes(pollutantType);
    
    if (!needsConversion) return data;

    const pbl = data.weather_snapshot?.pbl || 1000; 
    const molarMass = pollutant.molarMass;
    
    let MULTIPLIER = (molarMass * 1000000) / pbl;
    if (pollutantType === 'co') MULTIPLIER = (molarMass * 1000) / pbl;
    if (pollutantType === 'so2') MULTIPLIER = molarMass / pbl;
    if (pollutantType === 'o3') MULTIPLIER = (molarMass * 0.1) / pbl; // Ozone specific scaling for surface concentration

    let processed = { ...data };
    processed.base_value_2026 = processed.base_value_2026 * MULTIPLIER;
    if (processed.timeline) {
      processed.timeline = processed.timeline.map(t => {
        const pointPbl = t.pbl || pbl;
        let m;
        if (pollutantType === 'co')  m = (molarMass * 1000) / pointPbl;
        else if (pollutantType === 'so2') m = molarMass / pointPbl;
        else if (pollutantType === 'o3')  m = (molarMass * 0.1) / pointPbl;
        else m = (molarMass * 1000000) / pointPbl; // no2
        return { ...t, value: t.value * m };
      });
    }
    if (processed.comparison_table) {
      // For SO2 and O3: the backend already computes both predicted and observed
      // in the same native training units (µmol/m² for SO2, scaled DU for O3)
      // and pre-computes variance_pct from those aligned values.
      // Applying a single current-snapshot PBL multiplier here would inflate
      // the displayed numbers and make the model look inaccurate — skip conversion.
      // The table is displayed as-is in native units with variance_pct from backend.
      if (pollutantType === 'so2' || pollutantType === 'o3') {
        // No conversion — keep native units for accuracy
      } else {
        processed.comparison_table = processed.comparison_table.map(row => {
          return {
            ...row,
            model_predicted_avg: row.model_predicted_avg !== null ? row.model_predicted_avg * MULTIPLIER : null,
            real_observed_avg: row.real_observed_avg !== null ? row.real_observed_avg * MULTIPLIER : null,
          };
        });
      }
    }
    return processed;
  }, [pollutantType, pollutant.molarMass]);

  // ── AI Insight Fetcher ──
  const fetchAiInsight = useCallback(async (name, val, unit, label) => {
    // Don't call Gemini if we don't have a valid status label
    if (!label || !val || val <= 0) {
      setIsAiLoading(false);
      return;
    }
    setIsAiLoading(true);
    try {
      const res = await locationService.getPollutionInsight(name, val, unit, label);
      setAiInsight(res.insight);
    } catch (e) {
      console.warn("Gemini fetch failed:", e);
      setAiInsight(null);
    } finally {
      setIsAiLoading(false);
    }
  }, []);

  // ── Data fetching ─────────────────────────────────────────────────────────

  // ── Data fetching ─────────────────────────────────────────────────────────

  const fetchPrediction = useCallback(async (range = '1Y') => {
    if (!profile?.latitude || !profile?.longitude) return;
    setLoading(true);
    setError(null);
    try {
      const predictFn = predictByType[pollutantType] || predictByType.co;
      let data = await predictFn(null, range, {});
      setSyncedAt(Date.now());
      const processed = processPollutantData(data);
      setSelectedCoords(null);
      setPredData(processed);
      
      const status = getStatus(processed.base_value_2026, pollutant.whoLimit);
      fetchAiInsight(pollutant.name, processed.base_value_2026, pollutant.unit, status?.label);
    } catch (e) {
      setError(e.response?.data?.error || `Failed to load ${pollutant.name} data`);
    } finally {
      setLoading(false);
    }
  }, [profile?.latitude, profile?.longitude, pollutantType, pollutant.name, pollutant.whoLimit, pollutant.unit, processPollutantData, fetchAiInsight, getStatus]);

  const fetchAtCoords = useCallback(async (lat, lon, range = '1Y') => {
    setLoading(true);
    setError(null);
    try {
      const predictAtFn = predictAtByType[pollutantType] || predictAtByType.co;
      let data = await predictAtFn(lat, lon, range, {});
      setSyncedAt(Date.now());
      const processed = processPollutantData(data);
      setSelectedCoords({ lat, lon });
      setPredData(processed);

      const status = getStatus(processed.base_value_2026, pollutant.whoLimit);
      fetchAiInsight(pollutant.name, processed.base_value_2026, pollutant.unit, status?.label);
    } catch (e) {
      setError(e.response?.data?.error || `Prediction failed for ${pollutant.name}`);
    } finally {
      setLoading(false);
    }
  }, [pollutantType, pollutant.name, pollutant.whoLimit, pollutant.unit, processPollutantData, fetchAiInsight, getStatus]);

  // ── Auto-location & Initial Data Fetch ────────────────────────────────────

  useEffect(() => {
    if (!isLoggedIn) { navigate('/login'); return; }
    if (hasAutoLocated) return;

    const fallbackToPreferred = () => {
      setHasAutoLocated(true);
      setShowLocationSelector(false); // Close selector if we have a preferred town
      if (!profile?.latitude || !profile?.longitude) {
        setShowLocationSelector(true);
        setLoading(false);
      } else {
        fetchPrediction(timeRange);
      }
    };

    if (navigator.geolocation) {
      setLoading(true);
      navigator.geolocation.getCurrentPosition(
        async ({ coords }) => {
          try {
            await fetchAtCoords(coords.latitude, coords.longitude, timeRange);
            setHasAutoLocated(true);
            setShowLocationSelector(false);
          } catch {
            fallbackToPreferred();
          }
        },
        () => fallbackToPreferred(),
        { timeout: 5000 }
      );
    } else {
      fallbackToPreferred();
    }
  }, [isLoggedIn, navigate, hasAutoLocated, fetchAtCoords, fetchPrediction, timeRange, profile?.latitude, profile?.longitude]);

  // ── Parameter Synchronisation Effect ──────────────────────────────────────
  // Triggers when pollutant type or time range changes, for the CURRENT location
  useEffect(() => {
    if (!hasAutoLocated) return;

    if (selectedCoords?.lat != null && selectedCoords?.lon != null) {
      fetchAtCoords(selectedCoords.lat, selectedCoords.lon, timeRange);
    } else if (profile?.latitude && profile?.longitude) {
      fetchPrediction(timeRange);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollutantType, timeRange, profile?.latitude, profile?.longitude]); 


  // Separate effect for simulation — only triggers on WEATHER overrides, not time_focus
  useEffect(() => {
    const { time_focus, ...weatherOverrides } = overrides;
    
    if (Object.keys(weatherOverrides).length === 0) {
      setSimData(null);
      setIsSimulating(false);
      setSimError(null);
      return;
    }

    const fetchSimulation = async () => {
      setSimLoading(true);
      setSimError(null);
      try {
        const predictFn = predictByType[pollutantType];
        const predictAtFn = predictAtByType[pollutantType];
        
        let data;
        if (predData?.is_custom) {
          data = await predictAtFn(predData.latitude, predData.longitude, timeRange, weatherOverrides);
        } else {
          data = await predictFn(null, timeRange, weatherOverrides);
        }
        if (data?.error) {
          setSimError(data.error);
        } else {
          const processed = processPollutantData(data);
          setSimData(processed);

          const status = getStatus(processed.base_value_2026, pollutant.whoLimit);
          fetchAiInsight(pollutant.name, processed.base_value_2026, pollutant.unit, status?.label);
        }
      } catch (e) {
        console.error("Simulation failed", e);
        setSimError('Simulation failed. Please try again.');
      } finally {
        setSimLoading(false);
      }
    };

    const timer = setTimeout(fetchSimulation, 600);
    return () => clearTimeout(timer);
  }, [overrides, pollutantType, predData, profile?.latitude, profile?.longitude, timeRange, processPollutantData, getStatus, fetchAiInsight, pollutant.name, pollutant.whoLimit, pollutant.unit]);

  const handleOverrideChange = (key, value) => {
    const numericValue = parseFloat(value);
    setOverrides(prev => ({ ...prev, [key]: numericValue }));
    setIsSimulating(true);
  };

  const resetOverrides = () => {
    setOverrides({});
    setSimData(null);
    setIsSimulating(false);
  };

  // ── Freshness counter ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!syncedAt) return;
    const tick = () => {
      const s = Math.floor((Date.now() - syncedAt) / 1000);
      setSyncedAgo(s < 60 ? `${s}s ago` : `${Math.floor(s / 60)}m ago`);
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [syncedAt]);

  // Map sync handler
  const handleMapSync = useCallback((data) => {
    if (data.error) {
      setError(data.error);
      setLoading(false);
      return;
    }

    const lat = data?.latitude ?? data?.lat;
    const lon = data?.longitude ?? data?.lon;

    if (lat == null || lon == null) return;

    if (data.loading) {
      setLoading(true);
      setSelectedCoords({ lat, lon });
      return;
    }

    if (data.error) {
      setError(data.error);
      setLoading(false);
      return;
    }

    if (data.timeline) {
      const processed = processPollutantData(data);
      setSelectedCoords({ lat, lon });
      setPredData(processed);
      setSyncedAt(Date.now());

      const status = getStatus(processed.base_value_2026, pollutant.whoLimit);
      fetchAiInsight(pollutant.name, processed.base_value_2026, pollutant.unit, status?.label);
      setLoading(false);
    } else {
      fetchAtCoords(lat, lon, timeRange);
    }
  }, [fetchAtCoords, timeRange, processPollutantData, getStatus, pollutant.whoLimit, pollutant.name, pollutant.unit, fetchAiInsight]);

  const onLogout = () => {
    dispatch(logout());
    dispatch(reset());
    navigate('/login');
  };

  // ── Derived computed values ───────────────────────────────────────────────

  const timeline = useMemo(() => {
    if (!predData?.timeline) return [];
    return predData.timeline.map(item => ({
      label:        item.label,
      month:        item.month,
      year:         item.year,
      value:        Math.round(item.value * 1e6) / 1e6,
      isPrediction: item.is_prediction,
    }));
  }, [predData]);

  const barData = useMemo(() => {
    return timeline.map(item => ({
      label:     item.label,
      predicted: item.value,
      safeLimit: WHO_SAFE_LIMIT,
    }));
  }, [timeline, WHO_SAFE_LIMIT]);

  const globalYMax = useMemo(() => {
    if (!timeline.length) return WHO_SAFE_LIMIT * 1.5;
    return Math.max(...timeline.map(d => d.value), WHO_SAFE_LIMIT) * 1.2;
  }, [timeline, WHO_SAFE_LIMIT]);

  const currentValue = useMemo(() => {
    if (!predData?.base_value_2026) return null;
    return parseFloat(Number(predData.base_value_2026).toFixed(6));
  }, [predData]);

  const simulatedValue = useMemo(() => {
    if (!simData) return null;
    if (overrides.time_focus && simData.timeline) {
      const focus = parseInt(overrides.time_focus);
      const point = simData.timeline.find(t => 
        (timeRange === '1D' ? t.hour === focus : t.month === focus)
      );
      if (point) return parseFloat(Number(point.value).toFixed(6));
    }
    if (!simData.base_value_2026) return null;
    return parseFloat(Number(simData.base_value_2026).toFixed(6));
  }, [simData, overrides.time_focus, timeRange]);

  const peakPoint = useMemo(() => {
    if (!timeline.length) return null;
    return timeline.reduce((prev, curr) => prev.value > curr.value ? prev : curr);
  }, [timeline]);

  const lowestPoint = useMemo(() => {
    if (!timeline.length) return null;
    return timeline.reduce((prev, curr) => prev.value < curr.value ? prev : curr);
  }, [timeline]);

  const whoStatus = useMemo(() => getStatus(currentValue), [currentValue, getStatus]);

  const severityClass = useMemo(() => {
    if (!currentValue || !WHO_SAFE_LIMIT) return '';
    const ratio = currentValue / WHO_SAFE_LIMIT;
    if (ratio <= 1.0) return 'severity-safe';
    if (ratio <= 1.5) return 'severity-moderate';
    if (ratio <= 2.0) return 'severity-poor';
    return 'severity-hazardous';
  }, [currentValue, WHO_SAFE_LIMIT]);

  const weatherData = predData?.weather_snapshot || null;
  const hasHistory = pollutantType === 'so2' || pollutantType === 'o3';
  const isCustomLocation = selectedCoords?.lat != null && selectedCoords?.lon != null;
  const displayLat = predData?.latitude ?? selectedCoords?.lat;
  const displayLon = predData?.longitude ?? selectedCoords?.lon;
  
  const locationLabel = isCustomLocation
    ? 'Live Location'
    : (predData?.town_name || profile?.preferred_town_name || 'Select location');
    
  const locationSubLabel = isCustomLocation && displayLat != null && displayLon != null
    ? `${Number(displayLat).toFixed(4)}°N, ${Number(displayLon).toFixed(4)}°E`
    : (predData?.district_name || profile?.preferred_district_name || 'Odisha');

  if (showLocationSelector) {
    return <LocationSelector onSelect={() => setShowLocationSelector(false)} />;
  }

  return (
    <div className="dashboard-container">
      <nav className="dashboard-nav">
        <div className="navbar-logo">
          <Wind className="nav-icon" />
          <span>Odisha CarbonInsight</span>
        </div>

        <div className="pollutant-tabs">
          <NavLink to="/dashboard/co" className={({ isActive }) => `pollutant-tab ${isActive ? 'active' : ''}`}>
            <svg className="pollutant-tab-icon" viewBox="0 0 24 24" fill="none"><path d="M4 18c0-2.21 1.79-4 4-4h1c.55 0 1-.45 1-1s.45-1 1-1h1c1.66 0 3 1.34 3 3s-1.34 3-3 3H8c-2.21 0-4-1.79-4-4z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M12 15h4c1.66 0 3-1.34 3-3s-1.34-3-3-3h-1c-.55 0-1 .45-1 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            <span>CO</span>
          </NavLink>
          <NavLink to="/dashboard/no2" className={({ isActive }) => `pollutant-tab ${isActive ? 'active' : ''}`}>
            <svg className="pollutant-tab-icon" viewBox="0 0 24 24" fill="none"><rect x="3" y="14" width="18" height="7" rx="1" stroke="currentColor" strokeWidth="1.5"/><rect x="6" y="8" width="3" height="6" stroke="currentColor" strokeWidth="1.5"/><rect x="13" y="10" width="3" height="4" stroke="currentColor" strokeWidth="1.5"/></svg>
            <span>NO<sub>2</sub></span>
          </NavLink>
          <NavLink to="/dashboard/so2" className={({ isActive }) => `pollutant-tab ${isActive ? 'active' : ''}`}>
            <svg className="pollutant-tab-icon" viewBox="0 0 24 24" fill="none"><path d="M6 16a3 3 0 0 1-.2-6A5 5 0 0 1 16 10h.5a3.5 3.5 0 0 1 .5 7H6z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            <span>SO<sub>2</sub></span>
          </NavLink>
          <NavLink to="/dashboard/o3" className={({ isActive }) => `pollutant-tab ${isActive ? 'active' : ''}`}>
            <svg className="pollutant-tab-icon" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3.5" stroke="currentColor" strokeWidth="1.5"/><line x1="12" y1="2" x2="12" y2="5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><line x1="12" y1="19" x2="12" y2="22" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            <span>O<sub>3</sub></span>
          </NavLink>
          <NavLink to="/dashboard/ground" className={({ isActive }) => `pollutant-tab ${isActive ? 'active' : ''}`}>
            <svg className="pollutant-tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            <span>Ground Station</span>
          </NavLink>
        </div>

        <div className="navbar-actions">
          <div className="current-loc" onClick={() => setShowLocationSelector(true)}>
            <MapPin size={18} />
            <span>{locationLabel}, {locationSubLabel}</span>
          </div>
          <div className="navbar-user">
            <User className="user-icon" />
            <span>{user?.username}</span>
            <button onClick={onLogout} className="logout-btn">
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </nav>

      <main className="dashboard-main dashboard-analytics">
        {pollutantType === 'ground' ? (
          <GroundData latitude={displayLat} longitude={displayLon} />
        ) : (
          <>
            <div className="header-flex">
          <div className="welcome-section">
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              <h1>{predData?.is_custom ? 'Live Location' : (predData?.town_name || profile?.preferred_town_name)} — {pollutant.name} Dashboard</h1>
              {isSimulating && <span className="badge-ai warning">SIMULATION MODE</span>}
            </div>
            <p style={{ marginTop: '8px', opacity: 0.8 }}>
              {pollutant.full} Forecast · 
              <span style={{ color: 'var(--primary)', fontWeight: 700 }}> Triple-Stack ML Ensemble</span> · 
              Satellite & Weather Derived
            </p>
            {predData?.latitude && (
              <div className="coord-badge">
                {Number(predData.latitude).toFixed(4)}°N, {Number(predData.longitude).toFixed(4)}°E
              </div>
            )}
            {!loading && !error && predData && (
              <div className="live-badge">
                <div className="live-dot"></div>
                <span className="live-text">Live Synced · AI Inference</span>
                {syncedAgo && <span className="synced-ago">⚡ {syncedAgo}</span>}
              </div>
            )}
          </div>
          <div className="quick-stats-container">
            <div className="time-range-selector">
              {['1D', '1W', '1M'].map(range => (
                <button 
                  key={range} 
                  className={`range-btn ${timeRange === range ? 'active' : ''}`}
                  onClick={() => setTimeRange(range)}
                >
                  {range === '1D' ? 'Today' : range === '1W' ? 'Week' : 'Month'}
                </button>
              ))}
            </div>
            <div className="quick-stats">
              <div className="mini-stat">
                <Activity size={20} className="text-secondary" />
                <div>
                  <span className="label">
                    {timeRange === '1D' ? 'Daily Mean' : 
                     timeRange === '1W' ? 'Weekly Mean' : 
                     timeRange === '1M' ? 'Monthly Mean' : 'Annual Forecast'}
                  </span>
                  <span className="value">
                    {loading ? <div className="dot-typing" style={{ transform: 'scale(0.6)', width: '20px' }}></div> : (currentValue ?? '--')} 
                    <small>{pollutant.unit}</small>
                  </span>
                </div>
              </div>
              <div className="mini-stat">
                <TrendingUp size={20} className="text-indigo" />
                <div>
                  <span className="label">High Point</span>
                  <span className="value">
                    {loading ? <div className="dot-typing" style={{ transform: 'scale(0.6)', width: '20px' }}></div> : (peakPoint?.value?.toFixed(4) ?? '--')} 
                    <small>({peakPoint?.label ?? '--'})</small>
                  </span>
                </div>
              </div>
              <div className="mini-stat">
                <Wind size={20} className="text-primary" />
                <div>
                  <span className="label">Exposure Level</span>
                  <span className="value" style={{ color: whoStatus?.color }}>
                    {loading ? <div className="dot-typing" style={{ transform: 'scale(0.6)', width: '20px' }}></div> : (whoStatus?.label ?? '--')}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {loading && !predData && (
          <div className="dashboard-grid">
            <div className="chart-card wide map-card skeleton-card">
              <div className="skeleton skeleton-line w-40"></div>
              <div className="skeleton skeleton-map"></div>
            </div>
          </div>
        )}

        {error && (
          <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '12px', padding: '16px', color: '#dc2626', margin: '16px 0' }}>
            ⚠ {error}
          </div>
        )}

        {(!loading || predData) && !error && predData && (
          <>
            {weatherData && (
              <div className="weather-ingredients">
                <div className="weather-card">
                  <div className="weather-icon">🌡️</div>
                  <div className="weather-info">
                    <div className="weather-label">Temperature</div>
                    <div className="weather-value">{weatherData.temp?.toFixed(1)}°C</div>
                  </div>
                </div>
                <div className="weather-card">
                  <div className="weather-icon">☁️</div>
                  <div className="weather-info">
                    <div className="weather-label">Cloud Cover</div>
                    <div className="weather-value">{weatherData.cld}%</div>
                  </div>
                </div>
                <div className="weather-card">
                  <div className="weather-icon">💨</div>
                  <div className="weather-info">
                    <div className="weather-label">Wind Speed</div>
                    <div className="weather-value">{weatherData.wind_speed?.toFixed(1)} m/s</div>
                  </div>
                </div>
                <div className="weather-card">
                  <div className="weather-icon">🌊</div>
                  <div className="weather-info">
                    <div className="weather-label">Pressure</div>
                    <div className="weather-value">{weatherData.pressure?.toFixed(0)} hPa</div>
                  </div>
                </div>
                <div className="weather-card">
                  <div className="weather-icon">💧</div>
                  <div className="weather-info">
                    <div className="weather-label">Dewpoint</div>
                    <div className="weather-value">{weatherData.dewpoint?.toFixed(1)}°C</div>
                  </div>
                </div>
                <div className="weather-card">
                  <div className="weather-icon">☀️</div>
                  <div className="weather-info">
                    <div className="weather-label">Solar Radiation</div>
                    <div className="weather-value">
                      {typeof (overrides.solar || weatherData.solar) === 'number' 
                        ? (overrides.solar || weatherData.solar).toFixed(0) 
                        : (overrides.solar || weatherData.solar || '--')} W/m²
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="chart-card full simulation-card card-enter" style={{ background: '#f8fafc', marginBottom: '48px' }}>
              <div className="card-header" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '24px', marginBottom: '32px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                  <div className="title-with-badge">
                    <h3 style={{ fontSize: '22px', color: '#0f172a' }}>🧪 What-If Analysis: Interactive Parameters</h3>
                    <span className="badge-ai primary" style={{ marginLeft: '16px' }}>Live Sensitivity</span>
                  </div>
                  {isSimulating && (
                    <button onClick={resetOverrides} className="btn-reset">
                      <TrendingUp size={16} /> Reset to Default
                    </button>
                  )}
                </div>
                <p className="prediction-note" style={{ marginTop: 12, fontSize: '14px', color: 'var(--text-muted)', textAlign: 'left' }}>
                  Adjust parameters below to see how {pollutant.name} levels react to environmental and demographic changes.
                </p>
              </div>
              
              <div className="simulation-grid" style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', 
                gap: '24px', 
                padding: '0' 
              }}>
                {(PARAMETER_CONFIG[pollutantType] || []).map(param => (
                  <div className="sim-control" key={param.key}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                      <label style={{ fontSize: '13px', fontWeight: 700, color: '#475569' }}>
                        {param.label}
                      </label>
                      <div className="sim-value-box">
                        {overrides[param.key] || (weatherData?.[param.key]?.toFixed?.(1) || weatherData?.[param.key] || param.default)}{param.unit}
                      </div>
                    </div>
                    <input 
                      type="range" min={param.min} max={param.max} step={param.step}
                      value={overrides[param.key] || (weatherData?.[param.key] || param.default)} 
                      onChange={(e) => handleOverrideChange(param.key, e.target.value)}
                      style={{ width: '100%', accentColor: 'var(--primary)', cursor: 'pointer' }}
                    />
                  </div>
                ))}
              </div>

              {isSimulating && (
                <div style={{ 
                  marginTop: '40px', 
                  padding: '40px', 
                  background: 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)', 
                  borderRadius: '32px', 
                  boxShadow: 'var(--shadow-lg)',
                  display: 'flex',
                  flexWrap: 'wrap',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '24px',
                  border: '1px solid #e2e8f0',
                  position: 'relative'
                }}>
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 800, color: 'var(--primary)', textTransform: 'uppercase', marginBottom: '12px' }}>Scenario Projection</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      {simLoading ? (
                        <div className="dot-typing"></div>
                      ) : (
                        <>
                          <span style={{ fontSize: '48px', fontWeight: 800 }}>{simulatedValue ?? '--'}</span>
                          <span style={{ fontSize: '18px', color: 'var(--text-muted)' }}>{pollutant.unit}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="dashboard-grid">
              <div className={`chart-card full comparison-analysis card-enter ${severityClass}`} style={{ marginBottom: '32px' }}>
                <div className="card-header">
                  <h3>{pollutant.name} Comparison Analysis</h3>
                  <Wind size={20} className="text-primary" />
                </div>
                <div className="comparison-stack">
                  <div className="comparison-item current highlight">
                    <div className="label-area">
                      <span className="label">Model Average (2026)</span>
                    </div>
                    <span className="value">
                      {loading ? <div className="dot-typing"></div> : (currentValue ?? '--')} {pollutant.unit}
                    </span>
                  </div>
                  <div className="comparison-item standard">
                    <div className="label-area">
                      <span className="label">WHO Standard</span>
                    </div>
                    <span className="value">{WHO_SAFE_LIMIT} {pollutant.unit}</span>
                  </div>
                </div>
                <div className="standard-status-indicator" style={{ marginTop: '16px' }}>
                  <span className="value" style={{ fontWeight: 800, color: whoStatus?.color }}>
                    {loading ? 'Analyzing...' : (whoStatus ? `${whoStatus.emoji} ${whoStatus.label}` : 'Calculating...')}
                  </span>
                </div>
              </div>

              <div className="chart-card wide map-card card-enter" style={{ gridColumn: 'span 3' }}>
                <div className="card-header">
                  <h3>Location Analysis &amp; Regional Heatmap</h3>
                  <span className="badge-location">{locationLabel}</span>
                </div>
                <RegionalMap
                  townName={profile?.preferred_town_name}
                  currentCOValue={currentValue ?? 0}
                  townCoords={predData?.latitude && predData?.longitude ? [predData.latitude, predData.longitude] : null}
                  onDataUpdate={handleMapSync}
                  pollutantType={pollutantType}
                />
              </div>

              <div className="chart-card wide card-enter" style={{ gridColumn: 'span 3' }}>
                <div className="card-container">
                  <ResponsiveContainer width="100%" height={400}>
                    <BarChart data={barData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="label" />
                      <YAxis domain={[0, globalYMax]} />
                      <Tooltip />
                      <Legend />
                      <ReferenceLine y={WHO_SAFE_LIMIT} stroke="#10b981" strokeDasharray="3 3" />
                      <Bar dataKey="predicted" fill="#f43f5e" name={`Predicted ${pollutant.name}`} />
                      <Bar dataKey="safeLimit" fill="#10b981" name="WHO Safe Limit" opacity={0.4} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {hasHistory && predData?.comparison_table && (
                <div className="chart-card wide card-enter" style={{ gridColumn: 'span 3' }}>
                   <div className="card-header">
                      <h3>📊 Model Accuracy — Historical Validation</h3>
                      {(pollutantType === 'so2' || pollutantType === 'o3') && (
                        <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px' }}>
                          * Note: Native satellite units used for {pollutant.name} (SO₂ in µmol/m², O₃ in DU).
                        </p>
                      )}
                   </div>
                   {predData.comparison_table.every(row => !row.data_points || row.data_points === 0) ? (
                     <div style={{ background: '#fef3c7', border: '1px solid #fde68a', borderRadius: '12px', padding: '16px', color: '#b45309' }}>
                       ⚠ No historical satellite observations or weather data found near these coordinates. Try selecting a different location.
                     </div>
                   ) : (
                     <div className="table-responsive">
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                          <thead>
                            <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                              <th style={{ padding: '12px' }}>Period</th>
                              <th style={{ padding: '12px' }}>🔮 Predicted ({pollutantType === 'so2' ? 'µmol/m²' : pollutantType === 'o3' ? 'DU' : pollutant.unit})</th>
                              <th style={{ padding: '12px' }}>📡 Real Observed ({pollutantType === 'so2' ? 'µmol/m²' : pollutantType === 'o3' ? 'DU' : pollutant.unit})</th>
                              <th style={{ padding: '12px' }}>Variance</th>
                            </tr>
                          </thead>
                          <tbody>
                            {predData.comparison_table.map((row, idx) => (
                              <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                <td style={{ padding: '12px' }}>{row.period}</td>
                                <td style={{ padding: '12px' }}>{row.model_predicted_avg != null ? row.model_predicted_avg.toFixed(5) : '--'}</td>
                                <td style={{ padding: '12px' }}>{row.real_observed_avg != null ? row.real_observed_avg.toFixed(5) : '--'}</td>
                                <td style={{ padding: '12px', fontWeight: 600, color: row.variance_pct > 0 ? '#ef4444' : '#10b981' }}>
                                  {row.variance_pct != null ? `${row.variance_pct.toFixed(1)}%` : '--'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                     </div>
                   )}
                </div>
              )}

              <div className="chart-card full card-enter" style={{ gridColumn: 'span 3', marginTop: '32px' }}>
                <div className="card-header">
                  <h3>🩺 Health & Environmental Insight</h3>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '40px' }}>
                  <div>
                    <h4 style={{ color: 'var(--primary)', marginBottom: '12px' }}>About {pollutant.name}</h4>
                    <p>{POLLUTANT_DETAILS[pollutantType]?.description}</p>
                  </div>
                  <div>
                    <h4 style={{ color: whoStatus?.color || 'var(--text-main)' }}>{whoStatus?.label || 'Calculating...'} Range Advice</h4>
                    <p><strong>Health:</strong> {whoStatus?.label ? POLLUTANT_DETAILS[pollutantType]?.health_advice[whoStatus.label]?.health : 'Analyzing atmospheric conditions...'}</p>
                    <p><strong>Action:</strong> {whoStatus?.label ? POLLUTANT_DETAILS[pollutantType]?.health_advice[whoStatus.label]?.action : 'Please wait for model synchronization.'}</p>
                  </div>
                </div>

                <div style={{ marginTop: '32px', padding: '32px', background: 'rgba(99, 102, 241, 0.05)', borderRadius: '32px', border: '1px solid rgba(99, 102, 241, 0.15)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
                    <h4 style={{ margin: 0 }}>Gemini AI Deep Analysis</h4>
                    <button onClick={() => fetchAiInsight(pollutant.name, currentValue, pollutant.unit, whoStatus?.label)} disabled={isAiLoading} className="btn-refetch">
                      <RefreshCw size={14} className={isAiLoading ? 'spin' : ''} /> Refetch Analysis
                    </button>
                  </div>
                  {isAiLoading ? (
                    <div className="dot-typing" style={{ margin: '40px auto' }}></div>
                  ) : aiInsight && typeof aiInsight === 'object' ? (
                    <div className="ai-insight-grid">
                      <div className="ai-insight-item">
                        <strong>Short-term Effects</strong>
                        <p>{String(aiInsight.short_term_effects || 'No data')}</p>
                      </div>
                      <div className="ai-insight-item">
                        <strong>Long-term Risks</strong>
                        <p>{String(aiInsight.long_term_effects || 'No data')}</p>
                      </div>
                      <div className="ai-insight-item">
                        <strong>Vulnerable Groups</strong>
                        <p>{String(aiInsight.vulnerable_groups || 'No data')}</p>
                      </div>
                      <div className="ai-insight-item">
                        <strong>Environmental Impact</strong>
                        <p>{String(aiInsight.environmental_impact || 'No data')}</p>
                      </div>
                      <div className="ai-insight-item full-width" style={{ gridColumn: 'span 2' }}>
                        <strong>Personalized Action Plan</strong>
                        <ul className="ai-action-list">
                          {Array.isArray(aiInsight.action_plan) ? aiInsight.action_plan.map((step, i) => (
                            <li key={i} className="ai-action-item">
                              <div className="ai-action-dot"></div>
                              {String(step)}
                            </li>
                          )) : <li>{String(aiInsight.action_plan || 'No specific actions')}</li>}
                        </ul>
                      </div>
                      <div className="ai-insight-item scientific">
                        <strong>Scientific Fact</strong>
                        <p style={{ fontStyle: 'italic', opacity: 0.9 }}>{String(aiInsight.scientific_fact || 'No data')}</p>
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: '15px', color: '#334155', lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
                      {aiInsight || "Analyzing atmospheric chemistry for personalized recommendations..."}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
          </>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
