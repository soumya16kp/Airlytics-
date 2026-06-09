"""
no2_predictor.py
================
Singleton that loads the XGBoost NO2 model + 12-band TIF at Django startup.

The TIF contains ACTUAL monthly NO2 predictions (Band 1-12 = Jan-Dec 2026).
For monthly (1Y) granularity: reads directly from TIF bands (instant, no model needed).
For daily granularity (1D, 1W, 1M): runs XGBoost with day-specific doy/month inputs.

XGBoost features (13):
  lat, lon, elev, pop, urb, ntl, dow, doy, month, cld, aai, pop_ntl, loc_id
"""

import os
import numpy as np
import rasterio
import xgboost as xgb

from weather_service import get_weather_for_day, get_elevation
from timeline_utils import generate_timeline_points, day_sin, day_cos
from grid_data_service import grid_data_service

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'no2_xgboost_model.json')
TIF_PATH   = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'NO2_2026_FullYear_12Bands.tif')

# Defaults for features not available from weather
DEFAULT_POP = 5000
DEFAULT_URB = 50.0
DEFAULT_NTL = 30.0
DEFAULT_AAI = 1.0
DEFAULT_LOC_ID = 0


class NO2Predictor:
    """Loads the ML model and raster once; predicts per day on demand."""

    def __init__(self):
        self._model     = None
        self._src       = None
        self._data      = None
        self._transform = None
        self._ready     = False
        self._error     = None

    def _load(self):
        if self._ready or self._error:
            return
        try:
            self._model = xgb.Booster()
            self._model.load_model(MODEL_PATH)
        except Exception as e:
            self._error = f"Cannot load NO2 model: {e}"
            return
        try:
            self._src       = rasterio.open(TIF_PATH)
            self._transform = self._src.transform
            self._data      = self._src.read()   # (12, height, width)
        except Exception as e:
            self._error = f"Cannot open NO2 raster: {e}"
            return
        self._ready = True
        print(f"[NO2] Model loaded. TIF {self._src.width}x{self._src.height}, "
              f"{self._src.count} bands")

    def _get_tif_monthly(self, lat, lon):
        """Read all 12 monthly values directly from TIF. Returns (values, error)."""
        col, row = ~self._transform * (lon, lat)
        col, row = int(round(col)), int(round(row))

        if not (0 <= row < self._src.height and 0 <= col < self._src.width):
            return None, f"Coordinates ({lat},{lon}) outside NO2 raster bounds."

        pixel_vals = self._data[:, row, col].astype(np.float64)
        if np.isnan(pixel_vals).any():
            return None, f"NO2 raster has NaN at ({lat},{lon})."

        return pixel_vals.tolist(), None

    def _predict_for_day(self, lat, lon, doy, month, elev=100.0, weather=None, pop=5000.0, overrides=None):
        """Run XGBoost for a specific day-of-year."""
        _elev = elev
        _cld  = weather.get('cld', 20.0) if weather else 20.0
        _pop  = pop
        _urb  = float(overrides.get('urban', DEFAULT_URB)) if overrides else DEFAULT_URB
        _ntl  = float(overrides.get('night', DEFAULT_NTL)) if overrides else DEFAULT_NTL
        _aai  = float(overrides.get('aai', DEFAULT_AAI)) if overrides else DEFAULT_AAI
        _dow  = (doy % 7)

        features = np.array([[
            lat, lon, _elev, _pop, _urb, _ntl,
            _dow, doy, month, _cld, _aai,
            _pop * _ntl,   # pop_ntl interaction
            DEFAULT_LOC_ID
        ]], dtype=np.float64)

        dmatrix = xgb.DMatrix(features, feature_names=[
            'lat', 'lon', 'elev', 'pop', 'urb', 'ntl',
            'dow', 'doy', 'month', 'cld', 'aai', 'pop_ntl', 'loc_id'
        ])
        pred = float(self._model.predict(dmatrix)[0])
        return pred

    # ── Public API ───────────────────────────────────────────────────────────

    def predict_for_town(self, town, range_str='1Y', overrides=None):
        self._load()
        if self._error:
            return {'error': self._error}
        if town.latitude is None or town.longitude is None:
            return {'error': f"Town '{town.name}' has no coordinates."}
        return self._predict_timeline(town.latitude, town.longitude, range_str, overrides=overrides)

    def predict_at_coords(self, lat, lon, range_str='1Y', overrides=None):
        self._load()
        if self._error:
            return {'error': self._error}
        result = self._predict_timeline(lat, lon, range_str, overrides=overrides)
        result['lat'] = lat
        result['lon'] = lon
        result['is_custom'] = True
        return result

    def _predict_timeline(self, lat, lon, range_str, overrides=None):
        """
        Generate timeline of real predictions.
        - For monthly (1Y, 6M, 3M): use TIF bands directly (blazing fast)
        - For daily (1D, 1W, 1M): run XGBoost per day
        """
        points = generate_timeline_points(range_str)
        
        # Get baseline from spatial grid
        grid_pop, grid_elev = grid_data_service.get_data_at(lat, lon)
        
        elev = grid_elev
        if overrides and 'elev' in overrides: elev = float(overrides['elev'])
        
        pop = float(overrides.get('pop', grid_pop)) if overrides else grid_pop

        # Try to get TIF monthly data for fast monthly lookups
        tif_monthly, _ = self._get_tif_monthly(lat, lon)

        timeline = []
        all_values = []

        for pt in points:
            doy   = pt['day_of_year']
            month = pt['month']

            if range_str in ('1Y', '6M', '3M') and tif_monthly is not None and not overrides:
                # Use TIF band directly (index 0-11 for months 1-12)
                value = tif_monthly[month - 1]
            else:
                # Run XGBoost for this specific day
                hour = pt.get('hour')
                weather = get_weather_for_day(lat, lon, doy, hour=hour)
                
                # Apply weather overrides
                if overrides:
                    for k in ['temp', 'cld', 'wind_speed', 'wind_dir']:
                        if k in overrides: weather[k] = float(overrides[k])
                
                value = self._predict_for_day(lat, lon, doy, month, elev, weather, pop=pop, overrides=overrides)

            timeline.append({
                'year':          pt['year'],
                'month':         month,
                'monthName':     _month_name(month),
                'label':         pt['label'],
                'value':         round(value, 6),
                'is_prediction': True,
                'day_of_year':   doy,
            })
            all_values.append(value)

        if not all_values:
            return {'error': 'No valid NO2 predictions generated.'}

        return {
            'base_value_2026': round(float(np.mean(all_values)), 6),
            'timeline':        timeline,
            'range':           range_str,
            'pollutant':       'no2',
            'error':           None,
        }


def _month_name(m):
    return ['Jan','Feb','Mar','Apr','May','Jun',
            'Jul','Aug','Sep','Oct','Nov','Dec'][m - 1]


# Module-level singleton
no2_predictor = NO2Predictor()
