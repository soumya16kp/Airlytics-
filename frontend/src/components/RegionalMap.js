import React, { useState, useEffect, useRef, useCallback } from 'react';
import locationService from '../services/locationService';
import { MapContainer, TileLayer, Marker, Popup, useMap, Circle, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom draggable pin icon
const dragIcon = new L.Icon({
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
});

// Set initial map view ONCE (on mount or first geolocation result)
function InitialView({ center, hasInitialized }) {
    const map = useMap();
    useEffect(() => {
        if (center && !hasInitialized.current) {
            map.setView(center, 12, { animate: true });
            hasInitialized.current = true;
        }
    }, [center, map, hasInitialized]);
    return null;
}

function MapViewportSync({ center, zoom }) {
    const map = useMap();

    useEffect(() => {
        if (center) {
            map.setView(center, zoom, { animate: true });
        }
    }, [center, zoom, map]);

    return null;
}

// Listens for map click to move the dragger
function MapClickHandler({ onMapClick }) {
    useMapEvents({
        click(e) {
            onMapClick(e.latlng);
        },
    });
    return null;
}

// ── Pollutant metadata & spatial resolution ─────────────────────────────────
const POLLUTANT_INFO = {
    co:  { name: 'CO',  unit: 'mol/m²',  safeLabel: '0.02', extremeLabel: '0.06+', modelTag: 'Random Forest' },
    no2: { name: 'NO₂', unit: 'µmol/m²', safeLabel: '20',   extremeLabel: '80+',   modelTag: 'XGBoost' },
    so2: { name: 'SO₂', unit: 'DU',      safeLabel: '10',   extremeLabel: '80+',   modelTag: 'Triple-Stack + Ridge' },
    o3:  { name: 'O₃',  unit: 'DU',      safeLabel: '50',   extremeLabel: '160+',  modelTag: 'Triple-Stack' },
};

// Sentinel-5P pixel resolution ≈ 5.5 km → radius in metres
const SENTINEL_RADIUS = 5500;   // 5.5 km
const MODEL_RESOLUTION = {
    co:  { radius: SENTINEL_RADIUS,  label: '~5.5 x 5.5 km Sentinel pixel',  zoom: 12 },
    no2: { radius: SENTINEL_RADIUS,  label: '~5.5 x 5.5 km Sentinel pixel',  zoom: 12 },
    so2: { radius: SENTINEL_RADIUS,  label: '~5.5 x 5.5 km Sentinel pixel',  zoom: 12 },
    o3:  { radius: SENTINEL_RADIUS,  label: '~5.5 x 5.5 km Sentinel pixel',  zoom: 12 },
};

// Colour scale per pollutant
const getPollutantColor = (v, type) => {
    if (!v && v !== 0) return '#64748b';
    switch (type) {
        case 'no2':
            if (v < 20) return '#059669';
            if (v < 30) return '#10b981';
            if (v < 40) return '#84cc16';
            if (v < 50) return '#f59e0b';
            if (v < 60) return '#f97316';
            if (v < 70) return '#ea580c';
            if (v < 80) return '#ef4444';
            return '#991b1b';
        case 'so2':
            if (v < 10) return '#059669';
            if (v < 20) return '#10b981';
            if (v < 30) return '#84cc16';
            if (v < 40) return '#f59e0b';
            if (v < 50) return '#f97316';
            if (v < 60) return '#ea580c';
            if (v < 80) return '#ef4444';
            return '#991b1b';
        case 'o3':
            if (v < 50) return '#059669';
            if (v < 70) return '#10b981';
            if (v < 90) return '#84cc16';
            if (v < 100) return '#f59e0b';
            if (v < 120) return '#f97316';
            if (v < 140) return '#ea580c';
            if (v < 160) return '#ef4444';
            return '#991b1b';
        default: // co
            if (v < 0.025) return '#059669';
            if (v < 0.030) return '#10b981';
            if (v < 0.035) return '#84cc16';
            if (v < 0.040) return '#f59e0b';
            if (v < 0.045) return '#f97316';
            if (v < 0.050) return '#ea580c';
            if (v < 0.060) return '#ef4444';
            return '#991b1b';
    }
};

const formatLabel = (v, type) => {
    if (v == null) return '—';
    const info = POLLUTANT_INFO[type] || POLLUTANT_INFO.co;
    if (type === 'no2') return v.toExponential(2) + ' ' + info.unit;
    if (type === 'so2' || type === 'o3') return v.toFixed(2) + ' ' + info.unit;
    return v.toFixed(6) + ' ' + info.unit;
};

const RegionalMap = ({ townName, currentCOValue, townCoords, onDataUpdate, pollutantType = 'co' }) => {
    // Centre of Odisha as default
    const defaultCenter = [20.5, 85.0];

    const [center, setCenter] = useState(defaultCenter);
    const mapInitialized = useRef(false);
    const [selectedTown, setSelectedTown] = useState(null); // { coords, name, district, value }

    // Dragger state
    const [dragPos, setDragPos] = useState(null);  // { lat, lon }
    const [dragResult, setDragResult] = useState(null);  // API response
    const [dragLoading, setDragLoading] = useState(false);
    const [dragError, setDragError] = useState(null);

    const markerRef = useRef(null);
    const mapZoom = (MODEL_RESOLUTION[pollutantType] || MODEL_RESOLUTION.co).zoom;

    // ── On mount: get real GPS and run model immediately ─────────────────────
    const [geoStatus, setGeoStatus] = useState('idle'); // idle | loading | done | denied

    useEffect(() => {
        if (!navigator.geolocation) {
            setGeoStatus('denied');
            return;
        }
        setGeoStatus('loading');
        navigator.geolocation.getCurrentPosition(
            ({ coords }) => {
                const { latitude: lat, longitude: lng } = coords;
                setCenter([lat, lng]);
                setGeoStatus('done');
                // Drop probe pin and run model at real location
                predictAt({ lat, lng });
            },
            (err) => {
                console.warn('Geolocation denied:', err.message);
                setGeoStatus('denied');
                // Fall back to selected town centre if available
                if (townCoords) setCenter(townCoords);
            },
            { enableHighAccuracy: true, timeout: 8000 }
        );
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // run once on mount

    // Centre map when townCoords (synced location) changes
    useEffect(() => {
        if (townCoords) {
            setCenter(townCoords);
        }
    }, [townCoords]);


    // Live predict on drag / map click — handles all 4 pollutant types
    const predictAt = useCallback(async ({ lat, lng }) => {
        setDragPos({ lat, lon: lng });
        setDragLoading(true);
        setDragError(null);
        setDragResult(null);

        // Notify dashboard immediately that we are loading a new location
        if (onDataUpdate) {
            onDataUpdate({ lat, lon: lng, latitude: lat, longitude: lng, loading: true });
        }

        // No auto-zoom/pan — let the user control the map freely

        try {
            const predictFns = {
                co:  locationService.predictCOAt,
                no2: locationService.predictNO2At,
                so2: locationService.predictSO2At,
                o3:  locationService.predictO3At,
            };
            const fn = predictFns[pollutantType] || predictFns.co;
            let res = await fn(lat, lng);

            // Scale NO2 mol/m² → µmol/m² for readable visualization
            if (pollutantType === 'no2' && res.timeline) {
                const MULTIPLIER = 1000000;
                res = {
                    ...res,
                    base_value_2026: (res.base_value_2026 ?? 0) * MULTIPLIER,
                    timeline: res.timeline.map(t => ({ ...t, value: t.value * MULTIPLIER })),
                };
            }

            setDragResult(res);
            return res;
        } catch (e) {
            setDragError(e.response?.data?.error || 'Prediction failed for this location.');
            return null;
        } finally {
            setDragLoading(false);
        }
    }, [pollutantType]);

    // Auto-open popup whenever the probe result updates
    // (setTimeout gives React one tick to mount/update the Marker before calling openPopup)
    useEffect(() => {
        if (!dragPos) return;
        const t = setTimeout(() => {
            markerRef.current?.openPopup();
        }, 80);
        return () => clearTimeout(t);
    }, [dragPos, dragResult, dragError, dragLoading]);

    useEffect(() => {
        if (!onDataUpdate || dragLoading) return;

        if (dragResult && dragPos) {
            onDataUpdate({
                ...dragResult,
                latitude: dragResult.latitude ?? dragPos.lat,
                longitude: dragResult.longitude ?? dragPos.lon,
                lat: dragPos.lat,
                lon: dragPos.lon,
                is_custom: true,
            });
        } else if (dragError) {
            // Ensure dashboard stops loading if there was an error
            onDataUpdate({ error: dragError, loading: false });
        }
    }, [dragLoading, dragPos, dragResult, dragError, onDataUpdate]);


    const onMarkerDragEnd = useCallback(() => {
        const m = markerRef.current;
        if (m) {
            const { lat, lng } = m.getLatLng();
            predictAt({ lat, lng });
        }
    }, [predictAt]);

    const onMapClick = useCallback((latlng) => {
        predictAt(latlng);
    }, [predictAt]);

    const selectedColor = selectedTown?.value ? getPollutantColor(selectedTown.value, pollutantType) : '#4f46e5';

    return (
        <div style={{ position: 'relative', height: '700px', borderRadius: '32px', overflow: 'hidden', boxShadow: 'var(--shadow-lg)', background: '#f8fafc' }}>

            {/* Legend */}
            <div style={{
                position: 'absolute', bottom: 24, left: 24, zIndex: 1000,
                background: 'rgba(255,255,255,0.9)', padding: '20px',
                borderRadius: '24px', backdropFilter: 'blur(16px)',
                boxShadow: 'var(--shadow-lg)', fontSize: '12px', color: '#1e293b',
                border: '1px solid rgba(255,255,255,0.4)', minWidth: '220px'
            }}>
                <div style={{ fontWeight: 800, marginBottom: 12, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#64748b' }}>
                    {(POLLUTANT_INFO[pollutantType] || POLLUTANT_INFO.co).name} Intensity ({(POLLUTANT_INFO[pollutantType] || POLLUTANT_INFO.co).unit})
                </div>
                <div style={{ display: 'flex', gap: 3, height: 12, borderRadius: 6, overflow: 'hidden', marginBottom: 12 }}>
                    {['#059669', '#10b981', '#84cc16', '#f59e0b', '#f97316', '#ea580c', '#ef4444', '#991b1b'].map(c => (
                        <div key={c} style={{ flex: 1, background: c }} />
                    ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', fontWeight: 800 }}>
                    <span style={{ color: '#059669' }}>SAFE ({(POLLUTANT_INFO[pollutantType] || POLLUTANT_INFO.co).safeLabel})</span>
                    <span style={{ color: '#991b1b' }}>EXTREME ({(POLLUTANT_INFO[pollutantType] || POLLUTANT_INFO.co).extremeLabel})</span>
                </div>
                <div style={{ marginTop: 12, borderTop: '1px solid rgba(0,0,0,0.05)', paddingTop: 12, fontSize: '11px', color: '#64748b', fontWeight: 500 }}>
                    💡 {(MODEL_RESOLUTION[pollutantType] || MODEL_RESOLUTION.co).label}
                </div>
            </div>


            {/* Geo status badge (top-left) */}
            {geoStatus === 'loading' && (
                <div style={{
                    position: 'absolute', top: 24, left: 24, zIndex: 1001,
                    background: 'var(--primary)', color: 'white',
                    padding: '10px 20px', borderRadius: '16px',
                    fontSize: '13px', fontWeight: 700,
                    boxShadow: 'var(--shadow-lg)',
                    display: 'flex', alignItems: 'center', gap: 8,
                    animation: 'fadeInUp 0.4s ease-out'
                }}>
                    <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⏳</span>
                    Detecting GPS Location…
                </div>
            )}
            {geoStatus === 'done' && (
                <div style={{
                    position: 'absolute', top: 24, left: 24, zIndex: 1001,
                    background: 'var(--secondary)', color: 'white',
                    padding: '10px 20px', borderRadius: '16px',
                    fontSize: '13px', fontWeight: 700,
                    boxShadow: 'var(--shadow-lg)',
                    animation: 'fadeInUp 0.4s ease-out'
                }}>
                    📍 Location detected
                </div>
            )}
            {geoStatus === 'denied' && (
                <div style={{
                    position: 'absolute', top: 24, left: 24, zIndex: 1001,
                    background: 'var(--error)', color: 'white',
                    padding: '10px 20px', borderRadius: '16px',
                    fontSize: '13px', fontWeight: 700,
                    boxShadow: 'var(--shadow-lg)',
                    animation: 'fadeInUp 0.4s ease-out'
                }}>
                    ⚠ GPS access denied
                </div>
            )}

            {/* Instruction overlay (top-right) */}
            <div style={{
                position: 'absolute', top: 24, right: 24, zIndex: 1000,
                background: 'var(--glass-bg)', backdropFilter: 'blur(12px)',
                color: 'var(--text-main)', border: '1px solid var(--glass-border)',
                padding: '10px 20px', borderRadius: '16px', fontSize: '12px', fontWeight: 700,
                boxShadow: 'var(--shadow-md)',
                animation: 'fadeInUp 0.4s ease-out'
            }}>
                🔍 Drag marker or click map to probe
            </div>

            {/* Use My Location button */}
            <button
                onClick={() => {
                    if (!navigator.geolocation) return;
                    setGeoStatus('loading');
                    navigator.geolocation.getCurrentPosition(
                        async ({ coords }) => {
                            const { latitude: lat, longitude: lng } = coords;
                            setCenter([lat, lng]);
                            setGeoStatus('done');
                            const res = await predictAt({ lat, lng });
                            if (res && onDataUpdate) {
                                onDataUpdate({
                                    ...res,
                                    latitude: lat,
                                    longitude: lng,
                                    is_custom: true
                                });
                            }
                        },
                        () => setGeoStatus('denied'),
                        { enableHighAccuracy: true, timeout: 8000 }
                    );
                }}
                style={{
                    position: 'absolute', bottom: 24, right: 24, zIndex: 1000,
                    background: 'var(--primary)',
                    color: 'white', border: 'none', borderRadius: '16px',
                    padding: '12px 24px', fontSize: '13px', fontWeight: 700,
                    cursor: 'pointer', boxShadow: 'var(--shadow-lg)',
                    display: 'flex', alignItems: 'center', gap: 8,
                    transition: '0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                }}
                className="hover-lift"
            >
                📍 Use My Location
            </button>

            <MapContainer
                center={center}
                zoom={mapZoom}
                style={{ height: '100%', width: '100%' }}
                zoomControl={true}
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                />
                <InitialView center={center} hasInitialized={mapInitialized} />
                <MapViewportSync center={center} zoom={mapZoom} />
                <MapClickHandler onMapClick={onMapClick} />

                {/* Active Synced Location Circle (intensity overlay) */}
                {townCoords && (
                    <Circle
                        center={townCoords}
                        radius={SENTINEL_RADIUS}
                        pathOptions={{
                            fillColor: getPollutantColor(currentCOValue, pollutantType),
                            fillOpacity: 0.5,
                            color: getPollutantColor(currentCOValue, pollutantType),
                            weight: 2,
                        }}
                    >
                        <Popup closeButton={false}>
                            <div style={{ minWidth: 160 }}>
                                <div style={{ fontWeight: 700, fontSize: 13 }}>Synced Location</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: getPollutantColor(currentCOValue, pollutantType) }} />
                                    <span style={{ fontWeight: 800, fontSize: 15 }}>
                                        {formatLabel(currentCOValue, pollutantType)}
                                    </span>
                                </div>
                                <div style={{ marginTop: 6, fontSize: 10, color: '#4f46e5', fontWeight: 700 }}>
                                    ● CURRENT DASHBOARD SOURCE
                                </div>
                            </div>
                        </Popup>
                    </Circle>
                )}


                {/* Prediction coverage area circle (shows model spatial resolution) */}
                {dragPos && dragResult && !dragLoading && (
                    <Circle
                        center={[dragPos.lat, dragPos.lon]}
                        radius={(MODEL_RESOLUTION[pollutantType] || MODEL_RESOLUTION.co).radius}
                        pathOptions={{
                            fillColor: getPollutantColor(dragResult.base_value_2026, pollutantType),
                            fillOpacity: 0.2,
                            color: getPollutantColor(dragResult.base_value_2026, pollutantType),
                            weight: 2,
                            dashArray: '8 4',
                        }}
                    >
                        <Popup closeButton={false}>
                            <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, textAlign: 'center' }}>
                                Approx. prediction coverage<br/>
                                {(MODEL_RESOLUTION[pollutantType] || MODEL_RESOLUTION.co).label}
                            </div>
                        </Popup>
                    </Circle>
                )}

                {/* Draggable probe marker */}
                {dragPos && (
                    <Marker
                        ref={markerRef}
                        position={[dragPos.lat, dragPos.lon]}
                        icon={dragIcon}
                        draggable={true}
                        eventHandlers={{ dragend: onMarkerDragEnd }}
                    >
                        <Popup autoOpen={true} closeButton={false}>
                            <div style={{ minWidth: 200 }}>
                                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
                                    📍 Probe Location
                                </div>
                                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>
                                    {dragPos.lat.toFixed(4)}°N, {dragPos.lon.toFixed(4)}°E
                                </div>
                                {dragLoading && (
                                    <div style={{ color: '#6366f1', fontSize: 12 }}>⏳ Running {(POLLUTANT_INFO[pollutantType] || POLLUTANT_INFO.co).name} model…</div>
                                )}
                                {dragError && (
                                    <div style={{ color: '#ef4444', fontSize: 11 }}>⚠ {dragError}</div>
                                )}
                                {dragResult && !dragLoading && (
                                    <>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                                            <div style={{ width: 10, height: 10, borderRadius: '50%', background: getPollutantColor(dragResult.base_value_2026, pollutantType) }} />
                                            <span style={{ fontWeight: 800, fontSize: 15 }}>
                                                {formatLabel(dragResult.base_value_2026, pollutantType)}
                                            </span>
                                        </div>
                                        <div style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>
                                            Annual average prediction (2026)
                                        </div>
                                        <div style={{
                                            marginTop: 6, padding: '4px 8px',
                                            background: 'rgba(79,70,229,0.08)', borderRadius: '6px',
                                            fontSize: '10px', color: '#4f46e5', fontWeight: 600,
                                            display: 'flex', alignItems: 'center', gap: 4
                                        }}>
                                            🔮 {(POLLUTANT_INFO[pollutantType] || POLLUTANT_INFO.co).modelTag} · {(MODEL_RESOLUTION[pollutantType] || MODEL_RESOLUTION.co).label}
                                        </div>
                                        <div style={{ marginTop: 8, fontSize: '10px', color: '#10b981', fontWeight: 700 }}>
                                            ✓ Auto-synced to Dashboard
                                        </div>
                                    </>
                                )}
                            </div>
                        </Popup>
                    </Marker>
                )}
            </MapContainer>
        </div>
    );
};

export default RegionalMap;
