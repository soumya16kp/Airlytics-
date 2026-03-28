import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { register, reset } from '../store/authSlice';
import { User, Mail, Lock, UserPlus, Leaf } from 'lucide-react';
import carbonHero from '../assests/carbon-hero.jpg';
import './Login.css';

const Register = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const { username, email, password, confirmPassword } = formData;

  const navigate = useNavigate();
  const dispatch = useDispatch();

  const { isLoading, isError, isSuccess, message } = useSelector(
    (state) => state.auth
  );

  useEffect(() => {
    if (isError) {
      alert(message);
    }

    if (isSuccess) {
      navigate('/login');
    }
  }, [isError, isSuccess, message, navigate]);

  useEffect(() => {
    return () => {
        dispatch(reset());
    };
  }, [dispatch]);

  const onChange = (e) => {
    setFormData((prevState) => ({
      ...prevState,
      [e.target.name]: e.target.value,
    }));
  };

  const onSubmit = (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      alert('Passwords do not match');
      return;
    }
    dispatch(register({ username, email, password }));
  };

  return (
    <div className="auth-container">
      <div className="auth-hero">
        <img src={carbonHero} alt="Carbon monitoring visualization" />
        <div className="auth-hero-overlay" />
        <div className="auth-hero-content">
          <div className="auth-hero-badge">
            <span className="auth-live-dot" />
            Join the Mission
          </div>
          <h1>
            Start Tracking <span>Carbon</span> Today
          </h1>
          <p>
            Become part of Odisha's community dedicated to sustainability and data-driven climate action.
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
            <h2>Create Account</h2>
            <p>Join the community today</p>
          </div>

          <form onSubmit={onSubmit}>
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <div className="input-with-icon">
                <User className="input-icon" />
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={username}
                  onChange={onChange}
                  placeholder="Choose a username"
                  required
                />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <div className="input-with-icon">
                <Mail className="input-icon" />
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={email}
                  onChange={onChange}
                  placeholder="Enter your email"
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
                  value={password}
                  onChange={onChange}
                  placeholder="Secure your account"
                  required
                />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <div className="input-with-icon">
                <Lock className="input-icon" />
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  value={confirmPassword}
                  onChange={onChange}
                  placeholder="Retype password"
                  required
                />
              </div>
            </div>
            <button type="submit" className="auth-btn" disabled={isLoading}>
              {isLoading ? 'Creating Account...' : 'Register Now'}
            </button>
          </form>

          <p className="auth-footer">
            Already have an account? <span onClick={() => navigate('/login')}>Login</span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;
