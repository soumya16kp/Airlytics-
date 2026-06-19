import React, { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import {
  Activity,
  BarChart3,
  Bot,
  Clock3,
  Database,
  Globe2,
  Layers3,
  Leaf,
  LogOut,
  Map,
  Radar,
  Satellite,
  Sparkles,
  TrendingUp,
  Wind,
} from 'lucide-react';
import { logout, reset } from '../store/authSlice';
import './HomePage.css';

const NationalPulseMapPreview = lazy(() => import('./NationalPulseMapPreview'));

const stats = [
  { label: 'Near Real-Time Monitoring', value: 24, suffix: '/7', Icon: Clock3 },
  { label: 'Nationwide Coverage', value: 36, suffix: '+ regions', Icon: Globe2 },
  { label: 'Sentinel-5P Satellite Data', value: 5, suffix: 'P', Icon: Satellite },
  { label: 'AI-Powered Environmental Analysis', value: 98, suffix: '% ready', Icon: Sparkles },
];

const features = [
  { title: 'National Pulse', body: 'Macro environmental intelligence across India.', Icon: Map, path: '/dashboard/no2' },
  { title: 'Regional Analysis', body: 'State and district level environmental monitoring.', Icon: Layers3, path: '/dashboard/co' },
  { title: 'Air Quality Insights', body: 'NO2, SO2, O3 trend exploration.', Icon: Wind, path: '/dashboard/no2' },
  { title: 'AI Assistant', body: 'Natural language environmental analysis and insights.', Icon: Bot, path: '/dashboard/co' },
  { title: 'Historical Trends', body: 'Time-series analysis and environmental forecasting.', Icon: TrendingUp, path: '/dashboard/o3' },
  { title: 'Data Explorer', body: 'Advanced environmental dataset exploration.', Icon: Database, path: '/dashboard/ground' },
];

const useCountUp = (target) => {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const duration = 1400;
    const start = performance.now();
    let frameId;

    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) frameId = requestAnimationFrame(tick);
    };

    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [target]);

  return value;
};

const StatCard = ({ stat, index }) => {
  const current = useCountUp(stat.value);
  const Icon = stat.Icon;

  return (
    <article className="home-stat-card" style={{ animationDelay: `${index * 80}ms` }}>
      <div className="home-stat-icon">
        <Icon size={22} aria-hidden="true" />
      </div>
      <strong>
        {current}
        {stat.suffix}
      </strong>
      <span>{stat.label}</span>
    </article>
  );
};

const HomePage = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { isLoggedIn, isLoading, user } = useSelector((state) => state.auth);

  const particles = useMemo(
    () => Array.from({ length: 20 }, (_, index) => ({ id: index, left: (index * 37) % 100, delay: (index % 8) * 0.7 })),
    []
  );

  if (!isLoggedIn && !isLoading) {
    return <Navigate to="/login" replace />;
  }

  const onLogout = () => {
    dispatch(logout());
    dispatch(reset());
    navigate('/login');
  };

  return (
    <div className="home-page">
      <div className="home-gradient-field" aria-hidden="true" />
      <div className="particle-field" aria-hidden="true">
        {particles.map((particle) => (
          <span
            key={particle.id}
            style={{
              left: `${particle.left}%`,
              animationDelay: `${particle.delay}s`,
            }}
          />
        ))}
      </div>

      <header className="home-nav">
        <Link className="home-brand" to="/" aria-label="CO2 Insight home">
          <span className="home-brand-icon">
            <Leaf size={21} aria-hidden="true" />
          </span>
          <span>CO2 Insight</span>
        </Link>
        <nav className="home-nav-actions" aria-label="Home navigation">
          <Link to="/dashboard/co">Dashboard</Link>
          <span className="home-user">{user?.username || 'Analyst'}</span>
          <button type="button" onClick={onLogout} aria-label="Log out">
            <LogOut size={18} aria-hidden="true" />
          </button>
        </nav>
      </header>

      <main>
        <section className="home-hero" aria-labelledby="home-title">
          <div className="hero-copy">
            <div className="home-kicker">
              <span className="live-dot" />
              Sentinel-5P NRT intelligence
            </div>
            <h1 id="home-title">India's Environmental Intelligence Platform</h1>
            <p>
              Monitor national air quality indicators using Near Real-Time satellite intelligence,
              AI-powered insights, and interactive geospatial analytics.
            </p>
            <div className="hero-actions">
              <Link className="explore-insights-btn" to="/dashboard/co">
                Explore Insights
                <Activity size={18} aria-hidden="true" />
              </Link>
              <span className="hero-microcopy">NO2, SO2, O3 and ground validation workflows</span>
            </div>
          </div>

          <div className="hero-visual" aria-hidden="true">
            <div className="premium-datacard">
              <div className="datacard-glow" />
              <div className="datacard-header">
                <div className="header-left">
                  <Satellite size={16} />
                  <span>REAL-TIME SATELLITE FEED</span>
                </div>
                <div className="live-badge">
                  <span className="pulse-dot" />
                  LIVE
                </div>
              </div>
              <div className="datacard-metrics">
                <div className="metric-item">
                  <span>NO₂ Column Density</span>
                  <strong>0.124</strong>
                  <span>mol/m²</span>
                </div>
                <div className="metric-item">
                  <span>SO₂ Column Density</span>
                  <strong>0.042</strong>
                  <span>mol/m²</span>
                </div>
                <div className="metric-item">
                  <span>O₃ Column Density</span>
                  <strong>0.268</strong>
                  <span>mol/m²</span>
                </div>
              </div>
              <div className="datacard-footer">
                <Radar size={14} />
                <span>India coverage: 98.7%</span>
                <div className="trend-indicator">
                  <TrendingUp size={12} />
                  <span>+2.1% vs last pass</span>
                </div>
              </div>
              <div className="waveform" />
            </div>
          </div>
        </section>

        <section className="home-stats" aria-label="Platform statistics">
          {stats.map((stat, index) => (
            <StatCard key={stat.label} stat={stat} index={index} />
          ))}
        </section>

        <section className="national-pulse-preview" aria-labelledby="pulse-title">
          <div className="section-heading">
            <div>
              <span className="section-eyebrow">National Pulse Preview</span>
              <h2 id="pulse-title">National Pulse (Macro View)</h2>
            </div>
            <p>
              Folium-style India heatmap visualization for Sentinel-5P Near Real-Time NO2,
              SO2, and O3 column observations.
            </p>
          </div>

          <div className="pulse-preview-card">
            <Suspense
              fallback={
                <div className="map-loading" role="status">
                  Loading national geospatial layer...
                </div>
              }
            >
              <NationalPulseMapPreview />
            </Suspense>
          </div>
          <p className="pulse-disclaimer">
            Satellite observations represent Total Column Density and should not be interpreted as
            direct surface-level PM2.5 measurements.
          </p>
        </section>

        <section className="platform-features" aria-labelledby="features-title">
          <div className="section-heading compact">
            <div>
              <span className="section-eyebrow">Platform Features</span>
              <h2 id="features-title">Explore the analytics workbench</h2>
            </div>
          </div>
          <div className="feature-grid">
            {features.map(({ title, body, Icon, path }) => (
              <Link className="feature-card" to={path} key={title}>
                <span className="feature-icon">
                  <Icon size={22} aria-hidden="true" />
                </span>
                <strong>{title}</strong>
                <p>{body}</p>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
};

export default HomePage;