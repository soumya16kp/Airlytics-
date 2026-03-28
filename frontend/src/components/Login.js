import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { Mail, Lock, Leaf } from 'lucide-react';
import { login, reset } from '../store/authSlice';
import carbonHero from '../assests/carbon-hero.jpg';
import './Login.css';

const Login = () => {
  const [formData, setFormData] = useState({ username: '', password: '' });
  const navigate = useNavigate();
  const dispatch = useDispatch();

  const { user, isLoading, isError, isSuccess, message } = useSelector(
    (state) => state.auth
  );

  useEffect(() => {
    if (isSuccess || user) {
      navigate('/dashboard');
    }
  }, [user, isSuccess, navigate]);

  useEffect(() => {
    return () => {
        dispatch(reset());
    };
  }, [dispatch]);

  const onChange = (e) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const onSubmit = (e) => {
    e.preventDefault();
    dispatch(login(formData));
  };

  return (
    <div className="auth-container">
      <div className="auth-hero">
        <img src={carbonHero} alt="Carbon monitoring visualization" />
        <div className="auth-hero-overlay" />
        <div className="auth-hero-content">
          <div className="auth-hero-badge">
            <span className="auth-live-dot" />
            Live Tracking
          </div>
          <h1>
            AI-Powered <span>Carbon</span> Monitoring & Prediction
          </h1>
          <p>
            Real-time emissions tracking from town to state level.
            Predict, analyze, and reduce carbon footprints with actionable insights.
          </p>
        </div>
      </div>

      <div className="auth-form-panel">
        <div className="auth-grid-overlay" />
        
        <div className="auth-card">
          <div className="auth-brand">
            <div className="auth-brand-icon">
              <Leaf />
            </div>
            <span className="auth-brand-text">Odisha CarbonInsight</span>
          </div>

          <div className="auth-header">
            <h2>Welcome Back</h2>
            <p>
              Monitoring active across 30 Odisha districts
            </p>
          </div>

          <div className="auth-stats">
            <div className="auth-stat">
              <span className="auth-stat-value">4.2M</span>
              <span className="auth-stat-label">Tons Tracked</span>
            </div>
            <div className="auth-stat">
              <span className="auth-stat-value">98.2%</span>
              <span className="auth-stat-label">Accuracy</span>
            </div>
            <div className="auth-stat">
              <span className="auth-stat-value">24/7</span>
              <span className="auth-stat-label">Uptime</span>
            </div>
          </div>

          {isError && <div className="error-message">{message}</div>}

          <form onSubmit={onSubmit}>
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <div className="input-with-icon">
                <Mail className="input-icon" />
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={onChange}
                  placeholder="Enter your username"
                  required
                />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <div className="input-with-icon">
                <Lock className="input-icon" />
                <input
                  type="password"
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={onChange}
                  placeholder="Enter your password"
                  required
                />
              </div>
            </div>
            <button type="submit" className="auth-btn" disabled={isLoading}>
              {isLoading ? 'Authenticating...' : 'Access Dashboard'}
            </button>
          </form>

          <p className="auth-footer">
            Don't have an account?{' '}
            <span onClick={() => navigate('/register')} style={{cursor: 'pointer', color: 'var(--primary-color)'}}>Register</span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
