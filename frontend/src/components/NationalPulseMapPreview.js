import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import { Satellite } from 'lucide-react';
import locationService from '../services/locationService';

const INDIA_CENTER = [22.9734, 78.6569];

const pollutantConfig = {
  no2: {
    label: 'NO2',
    fullName: 'Nitrogen Dioxide',
    unit: 'mol/m²',
    gradient: ['#0f766e', '#22c55e', '#facc15', '#f97316', '#dc2626'],
    min: '0.0',
    max: '2.0e-4'
  },
  so2: {
    label: 'SO2',
    fullName: 'Sulfur Dioxide',
    unit: 'mol/m²',
    gradient: ['#0891b2', '#22c55e', '#eab308', '#f97316', '#b91c1c'],
    min: '0.0',
    max: '1.0e-3'
  },
  co: {
    label: 'CO',
    fullName: 'Carbon Monoxide',
    unit: 'mol/m²',
    gradient: ['#0284c7', '#22c55e', '#f59e0b', '#ea580c', '#dc2626'],
    min: '0.0',
    max: '5.0e-2'
  },
  o3: {
    label: 'O3',
    fullName: 'Ozone',
    unit: 'mol/m²',
    gradient: ['#2563eb', '#06b6d4', '#22c55e', '#f59e0b', '#ef4444'],
    min: '0.1',
    max: '0.15'
  },
  ch4: {
    label: 'CH4',
    fullName: 'Methane',
    unit: 'ppb',
    gradient: ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444'],
    min: '1750',
    max: '1900'
  }
};

const NationalPulseMapPreview = () => {
  const [activePollutant, setActivePollutant] = useState('no2');
  const [tileUrl, setTileUrl] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const config = pollutantConfig[activePollutant];

  useEffect(() => {
    let isMounted = true;

    const loadTileLayer = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await locationService.getGEETile(activePollutant);
        if (!isMounted) return;
        if (response && response.tile_url) {
          setTileUrl(response.tile_url);
        } else {
          setError('Failed to fetch map tile URL from server.');
        }
      } catch (err) {
        if (!isMounted) return;
        setError('Google Earth Engine API is currently unavailable.');
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    loadTileLayer();

    return () => {
      isMounted = false;
    };
  }, [activePollutant]);

  return (
    <div className="pulse-map-shell">
      <div className="pulse-map-toolbar" aria-label="Pollutant layer controls">
        {Object.entries(pollutantConfig).map(([key, item]) => (
          <button
            key={key}
            type="button"
            className={`pulse-layer-btn ${activePollutant === key ? 'active' : ''}`}
            onClick={() => setActivePollutant(key)}
            aria-pressed={activePollutant === key}
          >
            {item.label}
          </button>
        ))}
      </div>

      <MapContainer
        center={INDIA_CENTER}
        zoom={4.35}
        minZoom={3.5}
        maxZoom={9}
        scrollWheelZoom={true}
        className="pulse-map"
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        {tileUrl && !isLoading && !error && (
          <TileLayer
            key={tileUrl}
            url={tileUrl}
            opacity={0.65}
            attribution="&copy; Google Earth Engine Sentinel-5P NRT"
          />
        )}
      </MapContainer>

      {isLoading && (
        <div className="pulse-map-message" role="status">
          Generating Sentinel-5P tiles from GEE...
        </div>
      )}

      {error && (
        <div className="pulse-map-message" role="status" style={{ color: '#dc2626' }}>
          {error}
        </div>
      )}

      <div className="pulse-map-status">
        <Satellite size={16} aria-hidden="true" />
        <span>Live Sentinel-5P NRT Overlay</span>
      </div>

      <div className="pulse-legend" aria-label={`${config.label} concentration legend`}>
        <span>{config.fullName} ({config.unit})</span>
        <div className="legend-ramp" style={{ background: `linear-gradient(90deg, ${config.gradient.join(', ')})` }} />
        <div className="legend-scale">
          <span>Min: {config.min}</span>
          <span>Max: {config.max}</span>
        </div>
      </div>
    </div>
  );
};

export default NationalPulseMapPreview;
