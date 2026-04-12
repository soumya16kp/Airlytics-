import React, { useEffect, useState, useMemo } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { useNavigate, NavLink } from 'react-router-dom';
import { logout, reset } from '../store/authSlice';
import locationService from '../services/locationService';
import LocationSelector from './LocationSelector';
import {
  LogOut, User, MapPin,
  TrendingUp, BarChart3, Activity, Wind
} from 'lucide-react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from 'recharts';
import RegionalMap from './RegionalMap';

// Pollutant display config
const POLLUTANT_LABELS = {
  co:  { name: 'CO',  full: 'Carbon Monoxide',   unit: 'mol/m²',  whoLimit: 0.035 },
  no2: { name: 'NO₂', full: 'Nitrogen Dioxide',   unit: 'µmol/m²', whoLimit: 40 },
  so2: { name: 'SO₂', full: 'Sulfur Dioxide',     unit: 'DU',      whoLimit: 40 },
  o3:  { name: 'O₃',  full: 'Ozone',              unit: 'DU',      whoLimit: 100 },
};

const TIME_RANGES = ['1D', '1W', '1M', '3M', '6M', '1Y'];

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

const Dashboard = ({ pollutantType = 'co' }) => {
  const pollutant = POLLUTANT_LABELS[pollutantType] || POLLUTANT_LABELS.co;
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { user, isLoggedIn, profile } = useSelector((state) => state.auth);

  const [predData, setPredData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasAutoLocated, setHasAutoLocated] = useState(false);
  const [showLocationSelector, setShowLocationSelector] = useState(false);
  const [syncedAt, setSyncedAt] = useState(null);
  const [syncedAgo, setSyncedAgo] = useState(null);

  // Time selector
  const [timeRange, setTimeRange] = useState('1Y');

  const WHO_SAFE_LIMIT = pollutant.whoLimit;

  // ── Scaling for NO2 (mol/m² → µmol/m² visual range) ──────────────────────
  const processPollutantData = (data) => {
    if (pollutantType === 'no2') {
      const MULTIPLIER = 1000000;
      let processed = { ...data };
      if (processed.base_value_2026 !== undefined)
        processed.base_value_2026 = processed.base_value_2026 * MULTIPLIER;
      if (processed.timeline) {
        processed.timeline = processed.timeline.map(t => ({
          ...t, value: t.value * MULTIPLIER
        }));
      }
      return processed;
    }
    return data;
  };

  // ── Data fetching ─────────────────────────────────────────────────────────

  const fetchPrediction = async (range = '1Y') => {
    if (!profile?.preferred_town) return;
    setLoading(true);
    setError(null);
    try {
      const predictFn = predictByType[pollutantType] || predictByType.co;
      let data = await predictFn(profile.preferred_town, range);
      setSyncedAt(Date.now());
      setPredData(processPollutantData(data));
    } catch (e) {
      setError(e.response?.data?.error || `Failed to load ${pollutant.name} data`);
    } finally {
      setLoading(false);
    }
  };

  const fetchAtCoords = async (lat, lon, range = '1Y') => {
    setLoading(true);
    setError(null);
    try {
      const predictAtFn = predictAtByType[pollutantType] || predictAtByType.co;
      let data = await predictAtFn(lat, lon, range);
      setSyncedAt(Date.now());
      setPredData(processPollutantData(data));
    } catch (e) {
      setError(e.response?.data?.error || `Prediction failed for ${pollutant.name}`);
    } finally {
      setLoading(false);
    }
  };

  // ── Auto-location on mount ────────────────────────────────────────────────

  useEffect(() => {
    if (!isLoggedIn) { navigate('/login'); return; }

    if (!hasAutoLocated) {
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
    } else if (profile?.preferred_town) {
      fetchPrediction(timeRange);
    }
  }, [isLoggedIn, navigate, profile?.preferred_town]);

  const fallbackToPreferred = () => {
    setHasAutoLocated(true);
    if (!profile?.preferred_town) {
      setShowLocationSelector(true);
      setLoading(false);
    } else {
      setShowLocationSelector(false);
      fetchPrediction(timeRange);
    }
  };

  // Refetch when pollutant tab changes
  useEffect(() => {
    if (hasAutoLocated && profile?.preferred_town) {
      fetchPrediction(timeRange);
    }
  }, [pollutantType]);

  // Refetch when time range changes
  useEffect(() => {
    if (hasAutoLocated && predData) {
      if (predData?.is_custom && predData?.latitude && predData?.longitude) {
        fetchAtCoords(predData.latitude, predData.longitude, timeRange);
      } else if (profile?.preferred_town) {
        fetchPrediction(timeRange);
      }
    }
  }, [timeRange]);

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

  // Map sync handler (preserves already-scaled data)
  const handleMapSync = (data) => {
    setPredData(data);
    setSyncedAt(Date.now());
  };

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

  // Bar chart: Predicted vs WHO Safe Limit
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

  // Current value (last timeline point or average)
  const currentValue = useMemo(() => {
    if (!predData?.base_value_2026) return null;
    return parseFloat(predData.base_value_2026.toFixed(6));
  }, [predData]);

  // Peak
  const peakPoint = useMemo(() => {
    if (!timeline.length) return null;
    return timeline.reduce((prev, curr) => prev.value > curr.value ? prev : curr);
  }, [timeline]);

  // Lowest
  const lowestPoint = useMemo(() => {
    if (!timeline.length) return null;
    return timeline.reduce((prev, curr) => prev.value < curr.value ? prev : curr);
  }, [timeline]);

  // WHO comparison
  const whoStatus = useMemo(() => {
    if (!currentValue) return null;
    const ratio = currentValue / WHO_SAFE_LIMIT;
    if (ratio <= 0.5) return { label: 'Excellent', color: '#059669', emoji: '🟢' };
    if (ratio <= 1.0) return { label: 'Good',      color: '#10b981', emoji: '🟢' };
    if (ratio <= 1.5) return { label: 'Moderate',   color: '#f59e0b', emoji: '🟡' };
    if (ratio <= 2.0) return { label: 'Poor',       color: '#f97316', emoji: '🟠' };
    return              { label: 'Hazardous', color: '#ef4444', emoji: '🔴' };
  }, [currentValue, WHO_SAFE_LIMIT]);

  const severityClass = useMemo(() => {
    if (!currentValue || !WHO_SAFE_LIMIT) return '';
    const ratio = currentValue / WHO_SAFE_LIMIT;
    if (ratio <= 1.0) return 'severity-safe';
    if (ratio <= 1.5) return 'severity-moderate';
    if (ratio <= 2.0) return 'severity-poor';
    return 'severity-hazardous';
  }, [currentValue, WHO_SAFE_LIMIT]);

  // Derived weather data from prediction response
  const weatherData = predData?.weather_snapshot || null;

  // ── Render ────────────────────────────────────────────────────────────────

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

        {/* Pollutant selector */}
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
        </div>

        <div className="navbar-actions">
          <div className="current-loc" onClick={() => setShowLocationSelector(true)}>
            <MapPin size={18} />
            <span>{profile?.preferred_town_name}, {profile?.preferred_district_name}</span>
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
        <div className="header-flex">
          <div className="welcome-section">
            <h1>{predData?.is_custom ? 'Live Location' : (predData?.town_name || profile?.preferred_town_name)} — {pollutant.name} Dashboard</h1>
            <p>{pollutant.full} · 2026 ML Prediction · Real model output for every data point</p>
            {predData?.latitude && (
              <div className="coord-badge">
                {predData.latitude.toFixed(4)}°N, {predData.longitude.toFixed(4)}°E
              </div>
            )}
            {!loading && !error && predData && (
              <div className="live-badge">
                <div className="live-dot"></div>
                <span>Live Weather Synced · Real-Time AI Inference</span>
                {syncedAgo && <span className="synced-ago">&nbsp;· ⚡ {syncedAgo}</span>}
              </div>
            )}
          </div>
          <div className="quick-stats">
            <div className="mini-stat">
              <Activity size={20} className="text-secondary" />
              <div>
                <span className="label">Average 2026</span>
                <span className="value">{currentValue ?? '--'} <small>{pollutant.unit}</small></span>
              </div>
            </div>
            <div className="mini-stat">
              <TrendingUp size={20} className="text-indigo" />
              <div>
                <span className="label">Peak Forecast</span>
                <span className="value">{peakPoint?.value?.toFixed(4) ?? '--'} <small>({peakPoint?.label})</small></span>
              </div>
            </div>
            <div className="mini-stat">
              <BarChart3 size={20} className="text-secondary" />
              <div>
                <span className="label">Lowest</span>
                <span className="value">{lowestPoint?.value?.toFixed(4) ?? '--'} <small>({lowestPoint?.label})</small></span>
              </div>
            </div>
            <div className="mini-stat">
              <Wind size={20} className="text-primary" />
              <div>
                <span className="label">WHO Status</span>
                <span className="value" style={{ color: whoStatus?.color }}>
                  {whoStatus?.emoji} {whoStatus?.label ?? '--'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {loading && (
          <div className="dashboard-grid">
            <div className="chart-card wide map-card skeleton-card">
              <div className="skeleton skeleton-line w-40"></div>
              <div className="skeleton skeleton-map"></div>
            </div>
            <div className="chart-card skeleton-card">
              <div className="skeleton skeleton-line w-60"></div>
              <div className="skeleton skeleton-stat" style={{ marginBottom: 12 }}></div>
              <div className="skeleton skeleton-stat"></div>
              <div className="skeleton skeleton-line w-40" style={{ marginTop: 20 }}></div>
            </div>
            <div className="chart-card wide skeleton-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
                <div className="skeleton skeleton-line w-40" style={{ marginBottom: 0 }}></div>
                <div className="skeleton" style={{ width: 180, height: 32, borderRadius: 12 }}></div>
              </div>
              <div className="skeleton skeleton-chart"></div>
            </div>
            <div className="chart-card wide skeleton-card">
              <div className="skeleton skeleton-line w-40"></div>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12, margin: '16px 0' }}>
                <div className="skeleton skeleton-stat"></div>
                <div className="skeleton skeleton-stat"></div>
                <div className="skeleton skeleton-stat"></div>
              </div>
              <div className="skeleton skeleton-chart" style={{ height: 280 }}></div>
            </div>
          </div>
        )}

        {error && (
          <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '12px', padding: '16px', color: '#dc2626', margin: '16px 0' }}>
            ⚠ {error}
          </div>
        )}

        {!loading && !error && predData && (
          <>
            {/* Weather Ingredients — ML Model Inputs */}
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
                    <div className="weather-value">{weatherData.solar?.toFixed(0)} W/m²</div>
                  </div>
                </div>
              </div>
            )}

            <div className="dashboard-grid">

            {/* Regional Map */}
            <div className="chart-card wide map-card card-enter">
              <div className="card-header">
                <h3>Location Analysis &amp; Regional Heatmap</h3>
                <span className="badge-location">{profile?.preferred_town_name}, Odisha</span>
              </div>
              <RegionalMap
                townName={profile?.preferred_town_name}
                currentCOValue={currentValue ?? 0}
                townCoords={predData?.latitude && predData?.longitude
                  ? [predData.latitude, predData.longitude]
                  : null
                }
                onDataUpdate={handleMapSync}
                pollutantType={pollutantType}
              />
            </div>

            {/* Comparison card */}
            <div className={`chart-card comparison-analysis card-enter ${severityClass}`}>
              <div className="card-header">
                <h3>{pollutant.name} Comparison Analysis</h3>
                <Wind size={20} className="text-primary" />
              </div>
              <div className="comparison-stack">
                <div className="comparison-item current highlight">
                  <div className="label-area">
                    <span className="label">Model Average (2026)</span>
                    <span className="source-prediction">ML Model Output</span>
                  </div>
                  <span className="value">{currentValue ?? '--'} {pollutant.unit}</span>
                </div>
                <div className="comparison-item standard">
                  <div className="label-area">
                    <span className="label">WHO Standard</span>
                    <span className="source">Safe threshold</span>
                  </div>
                  <span className="value">{WHO_SAFE_LIMIT} {pollutant.unit}</span>
                </div>
              </div>
              <div className="standard-status-indicator">
                <div className="status-label">Air Quality:</div>
                <div className="status-flex">
                  <span className="value" style={{ fontWeight: 800, color: whoStatus?.color }}>
                    {whoStatus?.emoji} {whoStatus?.label ?? 'Calculating...'}
                  </span>
                </div>
              </div>
            </div>

            {/* VS WHO Standard — Bar Chart */}
            <div className="chart-card wide card-enter">
              <div className="card-header">
                <div className="title-with-badge">
                  <h3>{pollutant.name} vs WHO Standard</h3>
                  <span className="badge-ai">Real Model</span>
                </div>
                <div className="time-selector-group">
                  {TIME_RANGES.map(r => (
                    <button
                      key={r}
                      className={`time-pill ${timeRange === r ? 'active' : ''}`}
                      onClick={() => setTimeRange(r)}
                    >{r}</button>
                  ))}
                </div>
              </div>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={barData} barGap={2} barCategoryGap="20%">
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} interval={barData.length > 20 ? 5 : barData.length > 10 ? 2 : 0} />
                    <YAxis axisLine={false} tickLine={false} width={60} tickFormatter={v => v >= 1000 ? v.toExponential(1) : v < 0.01 ? v.toExponential(1) : v.toFixed(3)} domain={[0, globalYMax]} />
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                      formatter={(value, name) => [
                        (value >= 1000 ? value.toExponential(2) : value < 0.01 ? value.toExponential(2) : value.toFixed(5)) + ' ' + pollutant.unit,
                        name === 'predicted' ? `🔮 Predicted ${pollutant.name}` : '🟢 WHO Safe Limit'
                      ]}
                    />
                    <Legend verticalAlign="bottom" height={36} formatter={(v) => v === 'predicted' ? `Predicted ${pollutant.name}` : 'WHO Safe Limit'} />
                    <ReferenceLine y={WHO_SAFE_LIMIT} stroke="#10b981" strokeDasharray="3 3" strokeWidth={1.5} />
                    <Bar dataKey="predicted" fill="#f43f5e" radius={[4, 4, 0, 0]} name="predicted" />
                    <Bar dataKey="safeLimit" fill="#10b981" radius={[4, 4, 0, 0]} name="safeLimit" opacity={0.4} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Main Line Chart */}
            <div className={`chart-card wide co-prediction-card card-enter ${severityClass}`}>
              <div className="card-header">
                <div className="title-with-badge">
                  <h3>{pollutant.name} Prediction — 2026</h3>
                  <span className="badge-ai">Live ML Model</span>
                </div>
                <Activity size={20} className="text-secondary" />
              </div>
              <div className="co-stats-grid">
                <div className="co-main-stat">
                  <span className="label">Model Average</span>
                  <span className="value">{currentValue ?? '--'} {pollutant.unit}</span>
                </div>
                <div className="co-mini-stat">
                  <span className="label">Peak ({peakPoint?.label})</span>
                  <span className="value-mini">{peakPoint?.value?.toFixed(5) ?? '--'}</span>
                </div>
                <div className="co-mini-stat">
                  <span className="label">Low ({lowestPoint?.label})</span>
                  <span className="value-mini">{lowestPoint?.value?.toFixed(5) ?? '--'}</span>
                </div>
              </div>

              <div className="time-controls">
                <div className="time-selector-group">
                  {TIME_RANGES.map(r => (
                    <button
                      key={r}
                      className={`time-pill ${timeRange === r ? 'active' : ''}`}
                      onClick={() => setTimeRange(r)}
                    >{r}</button>
                  ))}
                </div>
              </div>

              <div className="chart-container">
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={timeline}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                      dataKey="label"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 10 }}
                      interval={timeline.length > 20 ? 5 : timeline.length > 10 ? 2 : 0}
                    />
                    <YAxis axisLine={false} tickLine={false} width={70} tickFormatter={v => v >= 1000 ? v.toExponential(1) : v < 0.01 ? v.toExponential(1) : v.toFixed(4)} domain={[0, globalYMax]} />
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                      formatter={(value) => [
                        value >= 1000 ? value.toExponential(2) : value < 0.01 ? value.toExponential(2) : value.toFixed(5),
                        `🔮 Predicted ${pollutant.name}`
                      ]}
                    />
                    <ReferenceLine y={WHO_SAFE_LIMIT} stroke="#10b981" strokeDasharray="6 3" strokeWidth={2} label={{ value: `WHO Safe (${WHO_SAFE_LIMIT})`, position: 'right', fill: '#10b981', fontSize: 10, fontWeight: 700 }} />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#f43f5e"
                      strokeWidth={3}
                      dot={timeline.length <= 30}
                      activeDot={{ r: 6, strokeWidth: 0 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
                <p className="prediction-note">
                  * Every data point is a real ML model prediction · Values in {pollutant.unit} · Green line = WHO safe threshold
                </p>
              </div>
            </div>

          </div>
          </>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
