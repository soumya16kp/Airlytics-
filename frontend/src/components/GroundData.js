import React, { useState } from 'react';
import { MapPin, RefreshCw, AlertTriangle, ShieldCheck, Compass } from 'lucide-react';
import locationService from '../services/locationService';

// Helper to compute distance in km using Haversine formula
function getHaversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

const GroundData = ({ latitude, longitude }) => {
  // Bhubaneswar default coordinates if none provided
  const lat = latitude ?? 20.2961;
  const lon = longitude ?? 85.8245;

  const [data, setData] = useState(() => {
    const cached = localStorage.getItem('ground_station_data');
    return cached ? JSON.parse(cached) : null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Disclaimer accuracy configurations
  const getAccuracyTier = (dist) => {
    if (dist <= 10) {
      return {
        label: 'Excellent Accuracy',
        color: '#10b981',
        desc: 'Ground data is highly representative of your immediate surroundings within 10 km.',
      };
    } else if (dist <= 30) {
      return {
        label: 'Good Approximation',
        color: '#3b82f6',
        desc: 'Solid regional representation. Slight variance may exist due to local microclimates (10 - 30 km).',
      };
    } else if (dist <= 50) {
      return {
        label: 'Moderate Variance',
        color: '#f59e0b',
        desc: 'Reading represents the broader district context. Local urban activity may vary (30 - 50 km).',
      };
    } else {
      return {
        label: 'Regional Baseline Only',
        color: '#ef4444',
        desc: 'High spatial variance. Data serves as a regional baseline rather than precise local exposure (50 - 100 km).',
      };
    }
  };

  const fetchGroundData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Bounding box for ~100km radius (approx 0.9 degrees latitude/longitude)
      const min_lon = lon - 0.9;
      const min_lat = lat - 0.9;
      const max_lon = lon + 0.9;
      const max_lat = lat + 0.9;

      const locationsData = await locationService.getOpenAQLocations(
        `${min_lon},${min_lat},${max_lon},${max_lat}`,
        30
      );

      const locations = locationsData?.results || [];

      // Calculate distances and filter <= 100 km
      const locationsWithDistance = locations
        .map((loc) => {
          const locLat = loc.coordinates?.latitude;
          const locLon = loc.coordinates?.longitude;
          if (locLat == null || locLon == null) return null;
          const dist = getHaversineDistance(lat, lon, locLat, locLon);
          return { ...loc, distance: dist };
        })
        .filter((loc) => loc !== null && loc.distance <= 100);

      // Sort by closest distance
      locationsWithDistance.sort((a, b) => a.distance - b.distance);

      if (locationsWithDistance.length === 0) {
        // Trigger Model Prediction Fallback
        await triggerFallback('No active ground stations found within 100 km.');
        return;
      }

      const closestStation = locationsWithDistance[0];

      // Fetch the latest measurements for the closest station
      const latestData = await locationService.getOpenAQLatest(closestStation.id);

      const measurements = latestData?.results || [];

      if (measurements.length === 0) {
        await triggerFallback(`Station ${closestStation.name} has no recent measurements.`);
        return;
      }

      // Create a map of sensor ID to parameter details from the location query
      const sensorMap = {};
      if (closestStation.sensors) {
        closestStation.sensors.forEach((s) => {
          if (s.id && s.parameter) {
            sensorMap[s.id] = s.parameter;
          }
        });
      }

      // Map metrics nicely using the sensor map
      const pollutants = {};
      measurements.forEach((m) => {
        const parameter = sensorMap[m.sensorsId];
        if (parameter && parameter.name) {
          pollutants[parameter.name.toLowerCase()] = {
            value: m.value,
            unit: parameter.units || 'µg/m³',
            updatedAt: m.datetime?.local || m.datetime?.utc,
          };
        }
      });

      const resultPayload = {
        isFallback: false,
        stationName: closestStation.name,
        distance: closestStation.distance,
        pollutants,
        lastUpdated: new Date().toLocaleTimeString(),
      };

      setData(resultPayload);
      localStorage.setItem('ground_station_data', JSON.stringify(resultPayload));
    } catch (err) {
      console.error('Error fetching ground station data:', err);
      // Fail gracefully to fallback rather than rendering blank
      await triggerFallback('OpenAQ API service unavailable. Using satellite models.');
    } finally {
      setLoading(false);
    }
  };

  const triggerFallback = async (reason) => {
    try {
      const [coRes, no2Res, so2Res, o3Res] = await Promise.all([
        locationService.predictCOAt(lat, lon, '1D').catch(() => null),
        locationService.predictNO2At(lat, lon, '1D').catch(() => null),
        locationService.predictSO2At(lat, lon, '1D').catch(() => null),
        locationService.predictO3At(lat, lon, '1D').catch(() => null),
      ]);

      const pollutants = {};
      // Helper function to scale raw predictive model results similar to scientific conversion layer in Dashboard.js
      const formatModelVal = (res, type, molarMass) => {
        if (!res) return null;
        const rawValue = res.base_value_2026 || 0.0;
        const pbl = res.weather_snapshot?.pbl || 1000;
        let multiplier = (molarMass * 1000000) / pbl;
        if (type === 'co') multiplier = (molarMass * 1000) / pbl;
        if (type === 'so2') multiplier = molarMass / pbl;
        if (type === 'o3') multiplier = (molarMass * 0.1) / pbl;

        return {
          value: parseFloat((rawValue * multiplier).toFixed(3)),
          unit: type === 'co' ? 'mg/m³' : 'µg/m³',
          updatedAt: new Date().toISOString(),
        };
      };

      if (coRes) pollutants['co'] = formatModelVal(coRes, 'co', 28.01);
      if (no2Res) pollutants['no2'] = formatModelVal(no2Res, 'no2', 46.01);
      if (so2Res) pollutants['so2'] = formatModelVal(so2Res, 'so2', 64.07);
      if (o3Res) pollutants['o3'] = formatModelVal(o3Res, 'o3', 48.0);

      const resultPayload = {
        isFallback: true,
        fallbackReason: reason,
        stationName: 'Triple-Stack Satellite Model Ensemble',
        distance: null,
        pollutants,
        lastUpdated: new Date().toLocaleTimeString(),
      };

      setData(resultPayload);
      localStorage.setItem('ground_station_data', JSON.stringify(resultPayload));
    } catch (e) {
      setError('Failed to fetch fallback prediction data.');
    }
  };

  const accuracy = data && data.distance != null ? getAccuracyTier(data.distance) : null;

  return (
    <div className="chart-card full card-enter" style={{ background: '#fdfdfe', minHeight: '400px' }}>
      <div className="card-header" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '20px', marginBottom: '30px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <div className="title-with-badge">
            <h3 style={{ fontSize: '24px', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Compass className="text-primary" size={24} /> Ground Monitoring Station Analysis
            </h3>
            {data && (
              <span className={`badge-ai ${data.isFallback ? 'warning' : 'primary'}`} style={{ marginLeft: '12px' }}>
                {data.isFallback ? 'Fallback Model' : 'Verified Ground'}
              </span>
            )}
          </div>
          <button
            onClick={fetchGroundData}
            disabled={loading}
            className="auth-btn"
            style={{
              width: 'auto',
              margin: 0,
              padding: '10px 24px',
              borderRadius: '14px',
              fontSize: '14px',
              boxShadow: '0 4px 12px rgba(99, 102, 241, 0.2)',
            }}
          >
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            {loading ? 'Connecting to Ground Center...' : 'Fetch Ground Station Data'}
          </button>
        </div>
        <p style={{ marginTop: '8px', fontSize: '14px', color: 'var(--text-muted)' }}>
          Retrieves real-time ground-level measurements directly from regulatory ambient air quality stations.
        </p>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '16px', padding: '16px', color: '#dc2626', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle size={20} />
          <span>{error}</span>
        </div>
      )}

      {!data && !loading && (
        <div style={{ textAlign: 'center', padding: '60px 20px', background: '#f8fafc', borderRadius: '24px', border: '1px dashed #cbd5e1' }}>
          <MapPin size={48} className="text-muted" style={{ margin: '0 auto 16px', opacity: 0.5 }} />
          <h4 style={{ fontSize: '18px', fontWeight: 600, color: '#334155' }}>No Data Loaded</h4>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px', maxWidth: '400px', margin: '4px auto 16px' }}>
            Click the fetch button to connect with the closest ground monitoring center within 100 km of your coordinates.
          </p>
        </div>
      )}

      {data && (
        <div>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: data.isFallback ? 'linear-gradient(135deg, #fffbeb, #ffffff)' : 'linear-gradient(135deg, #f0fdf4, #ffffff)',
            padding: '24px',
            borderRadius: '24px',
            border: data.isFallback ? '1px solid #fef3c7' : '1px solid #dcfce7',
            marginBottom: '32px',
            gap: '16px'
          }}>
            <div>
              <span style={{ fontSize: '12px', fontWeight: 800, textTransform: 'uppercase', color: data.isFallback ? '#b45309' : '#15803d', display: 'block', marginBottom: '4px' }}>
                {data.isFallback ? '⚠️ Fallback Active' : '📡 Connected Station'}
              </span>
              <h4 style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                {data.stationName}
                {data.distance != null && (
                  <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--primary)', background: 'var(--primary-glow)', padding: '2px 8px', borderRadius: '8px' }}>
                    {data.distance.toFixed(1)} km away
                  </span>
                )}
              </h4>
              {data.isFallback && (
                <p style={{ fontSize: '13px', color: '#b45309', marginTop: '4px' }}>
                  Reason: {data.fallbackReason}
                </p>
              )}
            </div>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block' }}>Last Sync</span>
              <strong style={{ fontSize: '15px', color: '#0f172a' }}>{data.lastUpdated}</strong>
            </div>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '24px',
            marginBottom: '32px'
          }}>
            {Object.entries(data.pollutants).length === 0 ? (
              <div style={{ gridColumn: 'span 4', textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>
                No standard pollutants were reported by this station.
              </div>
            ) : (
              Object.entries(data.pollutants).map(([key, item]) => {
                const limit = key === 'co' ? 4 : key === 'no2' ? 40 : key === 'so2' ? 40 : key === 'o3' ? 100 : 25;
                const ratio = item.value / limit;
                let status = { label: 'Good', color: '#10b981' };
                if (ratio > 1.5) status = { label: 'Hazardous', color: '#ef4444' };
                else if (ratio > 1.0) status = { label: 'Poor', color: '#f97316' };
                else if (ratio > 0.5) status = { label: 'Moderate', color: '#f59e0b' };

                return (
                  <div key={key} style={{
                    background: '#f8fafc',
                    padding: '24px',
                    borderRadius: '20px',
                    borderLeft: `5px solid ${status.color}`,
                    boxShadow: 'var(--shadow-sm)',
                    transition: 'all 0.3s ease',
                    position: 'relative'
                  }}>
                    <span style={{ fontSize: '12px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                      {key.toUpperCase()} Reading
                    </span>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '12px 0 6px' }}>
                      <span style={{ fontSize: '28px', fontWeight: 800, color: '#0f172a' }}>{item.value}</span>
                      <span style={{ fontSize: '14px', color: 'var(--text-muted)', fontWeight: 600 }}>{item.unit}</span>
                    </div>
                    <span style={{
                      fontSize: '11px',
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      color: 'white',
                      background: status.color,
                      padding: '2px 8px',
                      borderRadius: '6px',
                      display: 'inline-block'
                    }}>
                      {status.label}
                    </span>
                  </div>
                );
              })
            )}
          </div>

          {/* Accuracy Tier / Disclaimer Details */}
          {accuracy && (
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '16px',
              padding: '24px',
              borderRadius: '24px',
              background: '#f8fafc',
              border: '1px solid var(--border-subtle)',
              marginTop: '40px'
            }}>
              <div style={{
                background: accuracy.color,
                color: 'white',
                padding: '8px',
                borderRadius: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <ShieldCheck size={20} />
              </div>
              <div>
                <h5 style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                  {accuracy.label} Disclaimer
                </h5>
                <p style={{ fontSize: '14px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
                  {accuracy.desc}
                </p>
                <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
                  {['0-10km: Excellent', '10-30km: Good', '30-50km: Moderate', '50-100km: Regional'].map((tier, idx) => {
                    const isActive = (data.distance <= 10 && idx === 0) ||
                                     (data.distance > 10 && data.distance <= 30 && idx === 1) ||
                                     (data.distance > 30 && data.distance <= 50 && idx === 2) ||
                                     (data.distance > 50 && idx === 3);
                    return (
                      <span key={tier} style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '4px 10px',
                        borderRadius: '6px',
                        background: isActive ? accuracy.color : '#e2e8f0',
                        color: isActive ? 'white' : '#64748b',
                        transition: 'all 0.3s'
                      }}>
                        {tier}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default GroundData;
