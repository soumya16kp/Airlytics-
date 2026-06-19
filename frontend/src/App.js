import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { loadUser } from './store/authSlice';
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './components/Dashboard';
import ErrorBoundary from './components/ErrorBoundary';
import HomePage from './components/HomePage';

function App() {
  const dispatch = useDispatch();

  useEffect(() => {
    dispatch(loadUser());
  }, [dispatch]);

  return (
    <Router>
      <div className="App">
        <ErrorBoundary>
          <Routes>
            {/* Home page shown after login before users enter analytics */}
            <Route path="/" element={<HomePage />} />
            
            {/* Pollutant-specific dashboard routes */}
            <Route path="/dashboard/co" element={<Dashboard pollutantType="co" />} />
            <Route path="/dashboard/no2" element={<Dashboard pollutantType="no2" />} />
            <Route path="/dashboard/so2" element={<Dashboard pollutantType="so2" />} />
            <Route path="/dashboard/o3" element={<Dashboard pollutantType="o3" />} />
            <Route path="/dashboard/ground" element={<Dashboard pollutantType="ground" />} />
            
            {/* Legacy route redirects to CO */}
            <Route path="/dashboard" element={<Navigate to="/dashboard/co" replace />} />
            
            {/* Auth routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
          </Routes>
        </ErrorBoundary>
      </div>
    </Router>
  );
}

export default App;
