import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          {/* Redirect root to CO dashboard */}
          <Route path="/" element={<Navigate to="/dashboard/co" replace />} />
          
          {/* Pollutant-specific dashboard routes */}
          <Route path="/dashboard/co" element={<Dashboard pollutantType="co" />} />
          <Route path="/dashboard/no2" element={<Dashboard pollutantType="no2" />} />
          <Route path="/dashboard/so2" element={<Dashboard pollutantType="so2" />} />
          <Route path="/dashboard/o3" element={<Dashboard pollutantType="o3" />} />
          
          {/* Legacy route redirects to CO */}
          <Route path="/dashboard" element={<Navigate to="/dashboard/co" replace />} />
          
          {/* Auth routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
