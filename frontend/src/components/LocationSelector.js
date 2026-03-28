import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { updateProfile } from '../store/authSlice';
import locationService from '../services/locationService';
import { MapPin, ArrowRight, Check } from 'lucide-react';

const LocationSelector = ({ onSelect }) => {
  const [districts, setDistricts] = useState([]);
  const [towns, setTowns] = useState([]);
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [selectedTown, setSelectedTown] = useState('');
  
  const dispatch = useDispatch();
  const { profile } = useSelector((state) => state.auth);

  useEffect(() => {
    locationService.getDistricts().then(setDistricts);
  }, []);

  useEffect(() => {
    if (selectedDistrict) {
      locationService.getTowns(selectedDistrict).then(setTowns);
    } else {
      setTowns([]);
    }
    setSelectedTown('');
  }, [selectedDistrict]);

  const handleSave = async () => {
    if (selectedDistrict && selectedTown) {
      const updatedProfile = await dispatch(updateProfile({
        preferred_district: selectedDistrict,
        preferred_town: selectedTown,
      })).unwrap();
      onSelect(updatedProfile);
    }
  };

  return (
    <div className="location-overlay">
      <div className="location-card">
        <div className="location-header">
          <MapPin className="loc-icon" />
          <h2>Welcome to CarbonMonitor Odisha</h2>
          <p>Please select your town to view localized insights.</p>
        </div>
        
        <div className="form-group">
          <label>Select District</label>
          <select 
            value={selectedDistrict} 
            onChange={(e) => setSelectedDistrict(e.target.value)}
            className="modern-select"
          >
            <option value="">Select a District</option>
            {districts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>

        {selectedDistrict && (
          <div className="form-group animate-in">
            <label>Select Town</label>
            <select 
              value={selectedTown} 
              onChange={(e) => setSelectedTown(e.target.value)}
              className="modern-select"
            >
              <option value="">Select a Town</option>
              {towns.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
        )}

        <button 
          className="auth-btn" 
          disabled={!selectedTown}
          onClick={handleSave}
        >
          {selectedTown ? 'Explore Dashboard' : 'Select Location'} <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
};

export default LocationSelector;
