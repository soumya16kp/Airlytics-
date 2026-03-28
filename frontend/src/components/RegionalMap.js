import React, { useState, useEffect, useRef, useCallback } from 'react';
import locationService from '../services/locationService';
import { MapContainer, TileLayer, Marker, Popup, useMap, Circle, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom draggable pin icon
const dragIcon = new L.Icon({
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize:   [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
});

// Pan map to a center when it changes
function ChangeView({ center }) {
    const map = useMap();
    useEffect(() => {
        if (center) map.setView(center, 10, { animate: true });
    }, [center, map]);
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

// CO intensity colour (Sentinel-5P mol/m² scale, typically 0.01–0.10)
const getColor = (v) => {
    if (!v) return '#64748b';
    if (v < 0.025) return '#059669'; // Emerald-600 (Very Safe)
    if (v < 0.030) return '#10b981'; // Emerald-500 (Safe)
    if (v < 0.035) return '#84cc16'; // Lime-500 (Fair)
    if (v < 0.040) return '#f59e0b'; // Amber-500 (Moderate)
    if (v < 0.045) return '#f97316'; // Orange-500 (High)
    if (v < 0.050) return '#ea580c'; // Orange-600 (Very High)
    if (v < 0.060) return '#ef4444'; // Red-500 (Hazardous)
    return '#991b1b';               // Red-800 (Extreme)
};

const coLabel = (v) => v != null ? v.toFixed(6) + ' mol/m²' : '—';

const RegionalMap = ({ townName, currentCOValue, townCoords, onDataUpdate }) => {
    // Centre of Odisha as default
    const defaultCenter = [20.5, 85.0];

    const [center,        setCenter]       = useState(defaultCenter);
    const [selectedTown,  setSelectedTown] = useState(null); // { coords, name, district, value }

    // Dragger state
    const [dragPos,       setDragPos]      = useState(null);  // { lat, lon }
    const [dragResult,    setDragResult]   = useState(null);  // API response
    const [dragLoading,   setDragLoading]  = useState(false);
    const [dragError,     setDragError]    = useState(null);

    const markerRef = useRef(null);

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


    // Live predict on drag / map click
    const predictAt = useCallback(async ({ lat, lng }) => {
        setDragPos({ lat, lon: lng });
        setDragLoading(true);
        setDragError(null);
        setDragResult(null);
        try {
            const res = await locationService.predictCOAt(lat, lng);
            setDragResult(res);
        } catch (e) {
            setDragError(e.response?.data?.error || 'Prediction failed for this location.');
        } finally {
            setDragLoading(false);
        }
    }, []);

    // Auto-open popup whenever the probe result updates
    // (setTimeout gives React one tick to mount/update the Marker before calling openPopup)
    useEffect(() => {
        if (!dragPos) return;
        const t = setTimeout(() => {
            markerRef.current?.openPopup();
        }, 80);
        return () => clearTimeout(t);
    }, [dragPos, dragResult, dragError, dragLoading]);


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

    const selectedColor = selectedTown?.value ? getColor(selectedTown.value) : '#4f46e5';

    return (
        <div style={{ position: 'relative', height: '520px', borderRadius: '20px', overflow: 'hidden', border: '2px solid #e2e8f0' }}>

            {/* Legend */}
            <div style={{
                position: 'absolute', bottom: 16, left: 16, zIndex: 1000,
                background: 'rgba(255,255,255,0.94)', padding: '14px',
                borderRadius: '16px', backdropFilter: 'blur(8px)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.12)', fontSize: '11px', color: '#1e293b',
                border: '1px solid rgba(255,255,255,0.4)', minWidth: '180px'
            }}>
                <div style={{ fontWeight: 800, marginBottom: 10, fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
                    CO Gradient (mol/m²)
                </div>
                <div style={{ display: 'flex', gap: 2, height: 10, borderRadius: 5, overflow: 'hidden', marginBottom: 8 }}>
                    {['#059669','#10b981','#84cc16','#f59e0b','#f97316','#ea580c','#ef4444','#991b1b'].map(c => (
                        <div key={c} style={{ flex: 1, background: c }} />
                    ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', fontWeight: 700 }}>
                    <span style={{ color: '#059669' }}>SAFE (0.02)</span>
                    <span style={{ color: '#991b1b' }}>EXTREME (0.06+)</span>
                </div>
                <div style={{ marginTop: 10, borderTop: '1px solid #e2e8f0', paddingTop: 8, fontSize: '10px', color: '#64748b', fontStyle: 'italic' }}>
                    💡 Probing pixel-accurate RF predictions
                </div>
            </div>


            {/* Geo status badge (top-left) */}
            {geoStatus === 'loading' && (
                <div style={{
                    position:'absolute', top:12, left:12, zIndex:1001,
                    background:'rgba(99,102,241,0.92)', color:'white',
                    padding:'6px 14px', borderRadius:'8px',
                    fontSize:'12px', fontWeight:600,
                    boxShadow:'0 2px 8px rgba(0,0,0,0.2)',
                    display:'flex', alignItems:'center', gap:6
                }}>
                    <span style={{animation:'spin 1s linear infinite', display:'inline-block'}}>⏳</span>
                    Fetching your GPS location…
                </div>
            )}
            {geoStatus === 'done' && (
                <div style={{
                    position:'absolute', top:12, left:12, zIndex:1001,
                    background:'rgba(16,185,129,0.92)', color:'white',
                    padding:'6px 14px', borderRadius:'8px',
                    fontSize:'12px', fontWeight:600,
                    boxShadow:'0 2px 8px rgba(0,0,0,0.2)'
                }}>
                    📍 Your location detected — CO data loaded
                </div>
            )}
            {geoStatus === 'denied' && (
                <div style={{
                    position:'absolute', top:12, left:12, zIndex:1001,
                    background:'rgba(239,68,68,0.85)', color:'white',
                    padding:'6px 14px', borderRadius:'8px',
                    fontSize:'12px', fontWeight:600,
                    boxShadow:'0 2px 8px rgba(0,0,0,0.2)'
                }}>
                    ⚠ Location access denied — click map to probe CO
                </div>
            )}

            {/* Instruction overlay (top-right) */}
            <div style={{
                position: 'absolute', top: 12, right: 12, zIndex: 1000,
                background: 'rgba(79,70,229,0.9)', color: 'white',
                padding: '6px 12px', borderRadius: '8px', fontSize: '11px', fontWeight: 600,
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
            }}>
                🔍 Drag marker or click map to probe CO
            </div>

            {/* Use My Location button */}
            <button
                onClick={() => {
                    if (!navigator.geolocation) return;
                    setGeoStatus('loading');
                    navigator.geolocation.getCurrentPosition(
                        ({ coords }) => {
                            const { latitude: lat, longitude: lng } = coords;
                            setCenter([lat, lng]);
                            setGeoStatus('done');
                            predictAt({ lat, lng });
                        },
                        () => setGeoStatus('denied'),
                        { enableHighAccuracy: true, timeout: 8000 }
                    );
                }}
                style={{
                    position: 'absolute', bottom: 20, right: 16, zIndex: 1000,
                    background: 'linear-gradient(135deg,#4f46e5,#6366f1)',
                    color: 'white', border: 'none', borderRadius: '10px',
                    padding: '8px 18px', fontSize: '12px', fontWeight: 700,
                    cursor: 'pointer', boxShadow: '0 4px 14px rgba(79,70,229,0.45)',
                    display: 'flex', alignItems: 'center', gap: 6
                }}
            >
                📍 Use My Location
            </button>

            <MapContainer
                center={center}
                zoom={8}
                style={{ height: '100%', width: '100%' }}
                zoomControl={true}
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                />
                <ChangeView center={center} />
                <MapClickHandler onMapClick={onMapClick} />

                {/* Active Synced Location Circle (intensity overlay) */}
                {townCoords && (
                    <Circle
                        center={townCoords}
                        radius={6500}
                        pathOptions={{
                            fillColor: getColor(currentCOValue),
                            fillOpacity: 0.5,
                            color: getColor(currentCOValue),
                            weight: 2,
                        }}
                    >
                        <Popup closeButton={false}>
                            <div style={{ minWidth: 160 }}>
                                <div style={{ fontWeight: 700, fontSize: 13 }}>Synced Location</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: getColor(currentCOValue) }} />
                                    <span style={{ fontWeight: 800, fontSize: 15 }}>
                                        {coLabel(currentCOValue)}
                                    </span>
                                </div>
                                <div style={{ marginTop: 6, fontSize: 10, color: '#4f46e5', fontWeight: 700 }}>
                                    ● CURRENT DASHBOARD SOURCE
                                </div>
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
                            <div style={{ minWidth: 180 }}>
                                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
                                    📍 Probe Location
                                </div>
                                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>
                                    {dragPos.lat.toFixed(4)}°N, {dragPos.lon.toFixed(4)}°E
                                </div>
                                {dragLoading && (
                                    <div style={{ color: '#6366f1', fontSize: 12 }}>⏳ Running RF model…</div>
                                )}
                                {dragError && (
                                    <div style={{ color: '#ef4444', fontSize: 11 }}>⚠ {dragError}</div>
                                )}
                                {dragResult && !dragLoading && (
                                    <>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                                            <div style={{ width:10, height:10, borderRadius:'50%', background: getColor(dragResult.march_co_2026) }} />
                                            <span style={{ fontWeight: 800, fontSize: 15 }}>
                                                {coLabel(dragResult.march_co_2026)}
                                            </span>
                                        </div>
                                        <div style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>
                                            Base (annual avg): {coLabel(dragResult.base_co_2026)}
                                        </div>
                                        <div style={{ fontSize: 10, color: '#4f46e5', marginTop: 2, fontWeight: 600 }}>
                                            🔮 RF Model · March 2026
                                        </div>
                                        {onDataUpdate && (
                                            <button 
                                                onClick={() => onDataUpdate(dragResult)}
                                                style={{
                                                    marginTop: 10, width: '100%', padding: '6px',
                                                    background: '#4f46e5', color: 'white', border: 'none',
                                                    borderRadius: '6px', fontSize: '10px', fontWeight: 700,
                                                    cursor: 'pointer'
                                                }}
                                            >
                                                Sync to Dashboard
                                            </button>
                                        )}
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
