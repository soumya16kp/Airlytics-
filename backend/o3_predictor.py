"""
o3_predictor.py
===============
Singleton that loads the O3 Triple-Stack model (LightGBM + XGBoost + CatBoost)
at Django startup, then exposes real-time per-day predictions.

Model features (15):
  lat, lon, cluster, pbl, temp, solar, elev, pop, cld,
  day_sin, day_cos, wind_speed, photo_index, ozone_trap, o3_lag
"""

import os
import numpy as np
import joblib
import math

from weather_service import get_weather_for_day, get_elevation
from timeline_utils import generate_timeline_points, day_sin, day_cos

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ODISHA_ (O3_model).pkl')

# Default O3 lag value (mean tropospheric O3 in DU for Odisha region)
DEFAULT_O3_LAG = 35.0
DEFAULT_POP = 500000


class O3Predictor:
    """Loads the O3 triple-stack ensemble once; predicts per day on demand."""

    def __init__(self):
        self._models = None
        self._scaler = None
        self._kmeans = None
        self._features = None
        self._ready = False
        self._error = None

    def _load(self):
        if self._ready or self._error:
            return
        try:
            bundle = joblib.load(MODEL_PATH)
            self._models = {
                'lgbm': bundle['m1_lgbm'],
                'xgb':  bundle['m2_xgb'],
                'cat':  bundle['m3_cat'],
            }
            self._scaler  = bundle['scaler']
            self._kmeans  = bundle['kmeans']
            self._features = bundle['features']
            self._ready = True
            print(f"[O3] Model loaded: {bundle.get('version', 'unknown')}")
        except Exception as e:
            self._error = f"Cannot load O3 model: {e}"
            print(f"[O3] ERROR: {self._error}")

    def _build_features(self, lat, lon, doy, weather, elev=None, pop=None):
        """Build the 15-feature vector for one prediction."""
        w = weather
        cluster = int(self._kmeans.predict(np.array([[lat, lon]]))[0])

        _elev = elev if elev is not None else 100.0
        _pop  = pop if pop is not None else DEFAULT_POP
        _pbl  = w['pbl']
        _temp = w['temp']
        _solar = w['solar']
        _cld  = w['cld']
        _ws   = w['wind_speed']

        # Derived features
        photo_index = _solar * (1.0 - _cld / 100.0)
        ozone_trap  = _temp / (_ws + 0.1)
        o3_lag      = DEFAULT_O3_LAG

        # Feature vector in the exact order the model expects
        raw = np.array([[
            lat, lon, cluster, _pbl, _temp, _solar, _elev, _pop, _cld,
            day_sin(doy), day_cos(doy), _ws, photo_index, ozone_trap, o3_lag
        ]], dtype=np.float64)

        return raw

    def _predict_single(self, raw_features):
        """Run all 3 sub-models and average."""
        scaled = self._scaler.transform(raw_features)

        preds = []
        # LightGBM
        try:
            p = float(self._models['lgbm'].predict(scaled)[0])
            preds.append(p)
        except Exception as e:
            print(f"[O3] LightGBM failed: {e}")

        # XGBoost
        try:
            p = float(self._models['xgb'].predict(scaled)[0])
            preds.append(p)
        except Exception as e:
            print(f"[O3] XGBoost failed: {e}")

        # CatBoost
        try:
            p = float(self._models['cat'].predict(scaled)[0])
            preds.append(p)
        except Exception as e:
            print(f"[O3] CatBoost failed: {e}")

        if not preds:
            return None
        return float(np.mean(preds))

    # ── Public API ───────────────────────────────────────────────────────────

    def predict_for_town(self, town, range_str='1Y'):
        """
        Given a Town model instance, returns predictions for the requested range.
        """
        self._load()
        if self._error:
            return {'error': self._error}

        if town.latitude is None or town.longitude is None:
            return {'error': f"Town '{town.name}' has no coordinates."}

        return self._predict_timeline(town.latitude, town.longitude, range_str)

    def predict_at_coords(self, lat, lon, range_str='1Y'):
        """Predict O3 at arbitrary (lat, lon)."""
        self._load()
        if self._error:
            return {'error': self._error}

        result = self._predict_timeline(lat, lon, range_str)
        result['lat'] = lat
        result['lon'] = lon
        result['is_custom'] = True
        return result

    def _predict_timeline(self, lat, lon, range_str):
        """Generate timeline of real model predictions."""
        points = generate_timeline_points(range_str)
        elev = get_elevation(lat, lon)

        timeline = []
        all_values = []

        for pt in points:
            doy = pt['day_of_year']
            weather = get_weather_for_day(lat, lon, doy, pt['year'], pollutant='o3')
            raw = self._build_features(lat, lon, doy, weather, elev=elev)
            value = self._predict_single(raw)

            if value is None:
                continue

            timeline.append({
                'year':          pt['year'],
                'month':         pt['month'],
                'monthName':     _month_name(pt['month']),
                'label':         pt['label'],
                'value':         round(value, 6),
                'is_prediction': True,
                'day_of_year':   doy,
            })
            all_values.append(value)

        if not all_values:
            return {'error': 'No valid predictions could be generated.'}

        # Automatically build the historical comparison table
        from historical_data_service import o3_history
        comparison_table = o3_history.build_comparison_data(lat, lon, self._build_features_and_predict)

        return {
            'base_value_2026': round(float(np.mean(all_values)), 6),
            'timeline':        timeline,
            'comparison_table': comparison_table,
            'range':           range_str,
            'pollutant':       'o3',
            'error':           None,
        }

    def _build_features_and_predict(self, weather, lat, lon, doy, month, elev, pop):
        """Helper for historical_data_service to run the full pipeline."""
        # Note: o3_predictor build_features doesn't take month, but historical service passes it 
        # so we ignore the month parameter here
        raw = self._build_features(lat, lon, doy, weather, elev=elev, pop=pop)
        return self._predict_single(raw)


def _month_name(m):
    return ['Jan','Feb','Mar','Apr','May','Jun',
            'Jul','Aug','Sep','Oct','Nov','Dec'][m - 1]


# Module-level singleton — loaded once when Django starts
o3_predictor = O3Predictor()
