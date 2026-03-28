import React, { useEffect, useState, useMemo } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { logout, reset } from '../store/authSlice';
import locationService from '../services/locationService';
import LocationSelector from './LocationSelector';
import { 
  LogOut, User, MapPin, 
  TrendingUp, BarChart3, Activity, Wind
} from 'lucide-react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import RegionalMap from './RegionalMap';

const COLORS = ['#f43f5e', '#64748b'];

const Dashboard = () => {
  const navigate  = useNavigate();
  const dispatch  = useDispatch();
  const { user, isLoggedIn, profile } = useSelector((state) => state.auth);

  const [showLocationSelector, setShowLocationSelector] = useState(false);
  const [coData, setCoData]   = useState(null);   // live RF model response
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [hasAutoLocated, setHasAutoLocated] = useState(false);

  useEffect(() => {
    if (!isLoggedIn) {
      navigate('/login');
      return;
    }

    // Run auto-location ONLY once on initial mount
    if (!hasAutoLocated) {
      if (navigator.geolocation) {
        setLoading(true);
        navigator.geolocation.getCurrentPosition(
          async ({ coords }) => {
            try {
              const data = await locationService.predictCOAt(coords.latitude, coords.longitude);
              setCoData(data);
              setHasAutoLocated(true);
              setShowLocationSelector(false);
            } catch (e) {
              console.error('Geo-predict error:', e);
              fallbackToPreferred();
            } finally {
              setLoading(false);
            }
          },
          () => {
            console.warn('Geo access denied or timed out.');
            fallbackToPreferred();
          },
          { timeout: 5000 }
        );
      } else {
        fallbackToPreferred();
      }
    } else {
      // If we already located once, standard town changes should just fetch town data
      if (profile?.preferred_town) {
        fetchData();
      }
    }
  }, [isLoggedIn, navigate, profile?.preferred_town]);

  const fallbackToPreferred = () => {
    setHasAutoLocated(true); // Don't try again
    if (!profile?.preferred_town) {
      setShowLocationSelector(true);
      setLoading(false);
    } else {
      setShowLocationSelector(false);
      fetchData();
    }
  };

  const fetchData = async () => {
    if (!profile?.preferred_town) return;
    setLoading(true);
    setError(null);
    try {
      const data = await locationService.predictCO(profile.preferred_town);
      setCoData(data);
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to load town data.');
    } finally {
      setLoading(false);
    }
  };

  const onLogout = () => {
    dispatch(logout());
    dispatch(reset());
    navigate('/login');
  };

  // ── Derived data (memoized) ───────────────────────────────────────────────

  // Full 2020-2026 monthly CO timeline for the main chart
  const coTimeline = useMemo(() => {
    if (!coData?.timeline) return [];
    return coData.timeline.map(item => ({
      date:         `${item.year}-${String(item.month).padStart(2,'0')}-15`,
      monthYear:    `${item.monthName} '${String(item.year).slice(-2)}`,
      month:        item.month,
      year:         item.year,
      value:        Math.round(item.value * 1e5) / 1e5,
      isPrediction: item.is_prediction,
    }));
  }, [coData]);

  // YoY jump: March 2026 vs March 2025 from the timeline
  const jump = useMemo(() => {
    if (!coData?.timeline) return null;
    const m26 = coData.timeline.find(d => d.year === 2026 && d.month === 3);
    const m25 = coData.timeline.find(d => d.year === 2025 && d.month === 3);
    if (!m26 || !m25) return null;
    const pct = ((m26.value - m25.value) / m25.value) * 100;
    return {
      value:     parseFloat(m26.value.toFixed(5)),
      prevValue: parseFloat(m25.value.toFixed(5)),
      percent:   Math.abs(pct).toFixed(1),
      isUp:      pct > 0,
      monthName: 'March',
    };
  }, [coData]);

  // Pie chart: Predicted CO (March 2026) vs WHO Proxy
  const sectorData = useMemo(() => {
    if (!jump) return [];
    return [
      { name: 'Predicted (Mar 26)', value: parseFloat(jump.value) },
      { name: 'WHO Safe Proxy (0.035)', value: 0.035 }, 
    ];
  }, [jump]);

  // Next Month Prediction (April 2026)
  const nextMonth = useMemo(() => {
    if (!coData?.timeline) return null;
    const mApril = coData.timeline.find(d => d.year === 2026 && d.month === 4);
    const mMarch = coData.timeline.find(d => d.year === 2026 && d.month === 3);
    if (!mApril || !mMarch) return null;
    const diff = mApril.value - mMarch.value;
    return {
      value:    mApril.value.toFixed(5),
      delta:    Math.abs(diff).toFixed(5),
      isHigher: diff > 0,
    };
  }, [coData]);

  // Peak month in 2026
  const peak2026 = useMemo(() => {
    if (!coData?.timeline) return null;
    const months2026 = coData.timeline.filter(d => d.year === 2026);
    if (months2026.length === 0) return null;
    const peak = months2026.reduce((prev, curr) => (prev.value > curr.value) ? prev : curr);
    return peak;
  }, [coData]);

  // COVID impact (2020 vs 2021)
  const covidImpact = useMemo(() => {
    if (!coData?.timeline) return null;
    const m20 = coData.timeline.find(d => d.year === 2020 && d.month === 3);
    const m21 = coData.timeline.find(d => d.year === 2021 && d.month === 3);
    if (!m20 || !m21) return '—';
    const reduction = ((m21.value - m20.value) / m21.value) * 100;
    return reduction.toFixed(1) + '%';
  }, [coData]);

  // Baseline (January 2020)
  const baseline = useMemo(() => {
    if (!coData?.timeline) return '--';
    const jan2020 = coData.timeline.find(d => d.year === 2020 && d.month === 1);
    return jan2020 ? jan2020.value.toFixed(5) : '--';
  }, [coData]);
  // Annual Averages (Bar Chart)
  const yearlyAverages = useMemo(() => {
    if (!coData?.timeline) return [];
    const years = [...new Set(coData.timeline.map(d => d.year))];
    return years.sort().map(y => {
        const yearMonths = coData.timeline.filter(d => d.year === y);
        const avg = yearMonths.reduce((sum, curr) => sum + curr.value, 0) / yearMonths.length;
        return { 
            year: y, 
            avg: parseFloat(avg.toFixed(6)),
            isFuture: y === 2026
        };
    });
  }, [coData]);

  // Annual Growth Rate (%)
  const annualGrowth = useMemo(() => {
    if (yearlyAverages.length < 2) return '—';
    const vStart = yearlyAverages[0].avg;
    const vEnd   = yearlyAverages[yearlyAverages.length - 1].avg;
    const years  = yearlyAverages.length - 1;
    const cagr   = (Math.pow(vEnd / vStart, 1 / years) - 1) * 100;
    return cagr.toFixed(1) + '%';
  }, [yearlyAverages]);

  // Regional AQI Index (Synthetic based on 0.035 WHO proxy)
  const aqiScore = useMemo(() => {
    if (!jump) return null;
    const score = Math.round((jump.value / 0.035) * 100);
    const types = [
        { limit: 50,  label: 'Excellent', color: '#059669' },
        { limit: 100, label: 'Good',      color: '#10b981' },
        { limit: 150, label: 'Moderate',  color: '#f59e0b' },
        { limit: 200, label: 'Poor',      color: '#f97316' },
        { limit: 999, label: 'Hazardous', color: '#ef4444' }
    ];
    return {
      val:   score,
      label: types.find(t => score <= t.limit)?.label || 'Extreme',
      color: types.find(t => score <= t.limit)?.color || '#991b1b'
    };
  }, [jump]);


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
                <h1>{coData?.is_custom ? 'Live Location' : (coData?.town_name || profile?.preferred_town_name)} Dashboard</h1>
                <p>Location-specific CO prediction using RF Model ({coData?.is_custom ? 'GPS/Probe' : 'Selected Town'}).</p>
                {coData?.latitude && (
                  <div className="coord-badge">
                    {coData.latitude.toFixed(4)}°N, {coData.longitude.toFixed(4)}°E
                  </div>
                )}
            </div>
            <div className="quick-stats">
                 <div className="mini-stat">
                    <Activity size={20} className="text-secondary" />
                    <div>
                        <span className="label">Next Month (Apr 26)</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span className="value">{nextMonth?.value ?? '--'}</span>
                            <span style={{ fontSize: '10px', color: nextMonth?.isHigher ? '#ef4444' : '#10b981' }}>
                               {nextMonth?.isHigher ? '▲' : '▼'}
                            </span>
                        </div>
                    </div>
                 </div>
                 <div className="mini-stat">
                    <TrendingUp size={20} className="text-indigo" />
                    <div>
                        <span className="label">2026 Peak Forecast</span>
                        <span className="value">{peak2026?.value.toFixed(5) ?? '--'} <small style={{ fontSize: '9px', fontWeight: 600 }}>({peak2026?.monthName})</small></span>
                    </div>
                 </div>
                 <div className="mini-stat">
                    <BarChart3 size={20} className="text-secondary" />
                    <div>
                        <span className="label">Avg Annual Growth</span>
                        <span className="value text-error">+{annualGrowth}</span>
                    </div>
                 </div>
                 <div className="mini-stat">
                    <Wind size={20} className="text-primary" />
                    <div>
                        <span className="label">COVID Era Dip (2020)</span>
                        <span className="value text-success">-{covidImpact}</span>
                    </div>
                 </div>
            </div>
        </div>

        {loading && (
          <div style={{ textAlign:'center', padding:'60px', color:'#64748b' }}>
            <Activity size={32} style={{ margin:'0 auto 12px', display:'block', animation:'spin 1s linear infinite' }} />
            Running RF model for {profile?.preferred_town_name}…
          </div>
        )}

        {error && (
          <div style={{ background:'#fef2f2', border:'1px solid #fecaca', borderRadius:'12px', padding:'16px', color:'#dc2626', margin:'16px 0' }}>
            ⚠ {error}
          </div>
        )}

        {!loading && !error && coData && (
        <div className="dashboard-grid">

            {/* Regional Map — still reads /api/map-data/ but that now returns real model values */}
            <div className="chart-card wide map-card">
                <div className="card-header">
                     <h3>Location Analysis &amp; Regional Heatmap</h3>
                     <span className="badge-location">{profile?.preferred_town_name}, Odisha</span>
                </div>
                <RegionalMap 
                    townName={profile?.preferred_town_name} 
                    currentCOValue={jump?.value ?? 0}
                    townCoords={coData?.latitude && coData?.longitude
                        ? [coData.latitude, coData.longitude]
                        : null
                    }
                    onDataUpdate={setCoData} // Allow map drag to update dashboard charts
                />
            </div>

            {/* CO Comparison card */}
            <div className="chart-card comparison-analysis">
                <div className="card-header">
                    <h3>CO Comparison Analysis</h3>
                    <Wind size={20} className="text-primary" />
                </div>
                <div className="comparison-stack">
                    <div className="comparison-item previous">
                        <div className="label-area">
                            <span className="label">March 2025 (Historical)</span>
                            <span className="source">Model Back-trend</span>
                        </div>
                        <span className="value">{jump?.prevValue ?? '--'} mol/m²</span>
                    </div>
                    <div className="comparison-item current highlight">
                        <div className="label-area">
                            <span className="label">March 2026 (Predicted)</span>
                            <span className="source-prediction">RF Model Output</span>
                        </div>
                        <span className="value">{jump?.value ?? '--'} mol/m²</span>
                    </div>
                    <div className="comparison-item standard">
                        <div className="label-area">
                            <span className="label">WHO Standard (Proxy)</span>
                            <span className="source">TROPOMI mol/m² safe threshold</span>
                        </div>
                        <span className="value">0.035 mol/m²</span>
                    </div>
                </div>
                <div className="standard-status-indicator">
                    <div className="status-label">Regional AQI Index:</div>
                    <div className="status-flex">
                        <span className="value" style={{ fontWeight:800, color: aqiScore?.val < 100 ? '#10b981' : '#f59e0b' }}>
                           {aqiScore?.val ?? '--'}
                        </span>
                        <div className={`status-pill ${jump?.value > 0.035 ? 'red' : 'green'}`}>
                            {aqiScore?.label ?? 'Calculating...'}
                        </div>
                    </div>
                </div>

            </div>

            {/* Predicted CO vs WHO Pie */}
            <div className="chart-card">
                <div className="card-header">
                    <h3>CO vs Standard</h3>
                    <div className="subtitle">mol/m² · RF Model</div>
                </div>
                <div className="chart-container flex-center">
                    <ResponsiveContainer width="100%" height={260}>
                       <PieChart>
                            <Pie
                                data={sectorData}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={80}
                                paddingAngle={5}
                                dataKey="value"
                            >
                                {sectorData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip formatter={(v) => `${v} mol/m²`} />
                            <Legend verticalAlign="bottom" height={36}/>
                        </PieChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Main CO 2020-2026 chart */}
            <div className="chart-card wide co-prediction-card">
                <div className="card-header">
                    <div className="title-with-badge">
                        <h3>CO Concentration (2020–2026)</h3>
                        <span className="badge-ai">Live RF Model</span>
                    </div>
                    <Activity size={20} className="text-secondary" />
                </div>
                <div className="co-stats-grid">
                    <div className="co-main-stat">
                        <span className="label">Predicted (March 2026)</span>
                        <div className="val-flex">
                            <span className="value">{jump?.value ?? '--'} mol/m²</span>
                            {jump && (
                                <span className={`jump-tag ${jump.isUp ? 'text-error' : 'text-success'}`}>
                                    {jump.isUp ? '▲' : '▼'} {jump.percent}%
                                </span>
                            )}
                        </div>
                        <span className="label">vs March 2025</span>
                    </div>
                    <div className="co-mini-stat">
                        <span className="label">March 2025 (Historical)</span>
                        <span className="value-mini">{jump?.prevValue ?? '--'} mol/m²</span>
                    </div>
                    <div className="co-mini-stat">
                        <span className="label">Baseline (Jan 2020)</span>
                        <span className="value-mini">{baseline} mol/m²</span>
                    </div>
                </div>
                <div className="chart-container">
                    <ResponsiveContainer width="100%" height={260}>
                        <LineChart data={coTimeline}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis 
                                dataKey="monthYear" 
                                axisLine={false} 
                                tickLine={false} 
                                tick={{fontSize: 10}}
                                interval={5}
                             />
                            <YAxis axisLine={false} tickLine={false} width={70} tickFormatter={v => v.toFixed(4)} />
                            <Tooltip 
                                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                formatter={(value, name, props) => [
                                  value.toFixed(5),
                                  props.payload.isPrediction ? '🔮 Predicted CO' : '📊 Historical CO'
                                ]}
                            />
                            <Line 
                                type="monotone" 
                                dataKey="value" 
                                stroke="#f43f5e" 
                                strokeWidth={3}
                                dot={false}
                                activeDot={{ r: 6, strokeWidth: 0 }}
                                strokeDasharray={(entry) => entry?.isPrediction ? '6 3' : '0'}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                    <p className="prediction-note">
                      * 2026 = live RF prediction · Values in mol/m² · 2020 COVID Dip modeled
                    </p>
                </div>
            </div>

            {/* NEW: Annual Breakdown Bar Chart */}
            <div className="chart-card yearly-breakdown-card wide">
                 <div className="card-header">
                    <div>
                        <h3>Annual Mean CO (2020–2026)</h3>
                        <div className="subtitle">Historical Trends vs Model Projection</div>
                    </div>
                    <BarChart3 size={20} className="text-indigo" />
                </div>
                <div className="chart-container">
                    <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={yearlyAverages}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="year" axisLine={false} tickLine={false} />
                            <YAxis axisLine={false} tickLine={false} width={60} hide />
                            <Tooltip 
                                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                cursor={{ fill: '#f1f5f9' }}
                                formatter={(v) => [v.toFixed(6), 'Mean CO']}
                            />
                            <Line 
                                type="monotone" 
                                dataKey="avg" 
                                stroke="#6366f1" 
                                strokeWidth={3}
                                dot={{ fill: '#6366f1', strokeWidth: 2, r: 4 }}
                                activeDot={{ r: 6 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                    <div className="annual-legend" style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
                         {yearlyAverages.map(y => (
                             <div key={y.year} style={{ textAlign: 'center' }}>
                                 <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b' }}>{y.year}</div>
                                 <div style={{ fontSize: 11, fontWeight: 800, color: y.isFuture ? '#f43f5e' : '#1e293b' }}>
                                    {y.avg.toFixed(4)}
                                 </div>
                             </div>
                         ))}
                    </div>
                </div>
            </div>


        </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
