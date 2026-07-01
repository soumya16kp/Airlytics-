import React, { useState } from 'react';
import { useDispatch } from 'react-redux';
import { updateProfile } from '../store/authSlice';
import { MapPin, ArrowRight } from 'lucide-react';

const LocationSelector = ({ onSelect }) => {
  const [loading, setLoading] = useState(false);
  const [coords, setCoords] = useState(null);
  const [error, setError] = useState('');

  const dispatch = useDispatch();

  const getLocation = () => {
    setError('');
    setLoading(true);

    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser');
      setLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setCoords({ latitude, longitude });
        setLoading(false);
      },
      (err) => {
        setError('Permission denied or location unavailable');
        setLoading(false);
      }
    );
  };

  const handleSave = async () => {
    if (!coords) return;

    const updatedProfile = await dispatch(
      updateProfile({
        latitude: coords.latitude,
        longitude: coords.longitude,
      })
    ).unwrap();

    onSelect(updatedProfile);
  };

  return (
    <div className="location-overlay">
      <div className="location-card">

        <div className="location-header">
          <MapPin className="loc-icon" />
          <h2>Enable Location Access</h2>
          <p>We use GPS to show you localized carbon insights.</p>
        </div>

        {!coords && (
          <button className="btn-primary" onClick={getLocation} disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Fetching Location...' : 'Use My Current Location'}{' '}
            <ArrowRight size={18} />
          </button>
        )}

        {coords && (
          <div className="location-success">
            <p>Location detected ✔</p>
            <p>
              Lat: {coords.latitude.toFixed(4)} <br />
              Lng: {coords.longitude.toFixed(4)}
            </p>
          </div>
        )}

        {error && <p className="error-text">{error}</p>}

        <button
          className={`btn-primary ${coords ? 'explore-btn-active' : ''}`}
          disabled={!coords}
          onClick={handleSave}
          style={{ width: '100%', marginTop: '16px' }}
        >
          {coords ? 'Explore Dashboard' : 'Allow Location First'}{' '}
          <ArrowRight size={18} />
        </button>

      </div>
    </div>
  );
};

export default LocationSelector;