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
import pandas as pd

from weather_service import get_weather_for_day, get_elevation
from timeline_utils import generate_timeline_points, day_sin, day_cos
from grid_data_service import get_grid_data_service

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'OdishaO3Model.pkl')

# Default O3 lag value (mean tropospheric O3 in DU for Odisha region)
DEFAULT_O3_LAG = 35.0
DEFAULT_POP = 5000


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
            # Try HuggingFace first, then fall back to local
            hf_token = os.environ.get("HF_TOKEN", None)
            try:
                from huggingface_hub import hf_hub_download
                o3_model_path = hf_hub_download(
                    repo_id="ObitUchiha91/airlytics-models",
                    filename="o3_model_new.pkl",
                    token=hf_token
                )
                print("[O3] Model downloaded from Hugging Face.")
            except Exception as hf_err:
                print(f"[O3] HF download failed ({hf_err}), using local model.")
                o3_model_path = MODEL_PATH
            bundle = joblib.load(o3_model_path)
            self._models = {
                'xgb':  bundle.get('xgboost'),
                'cat':  bundle.get('catboost'),
            }
            self._kmeans  = bundle.get('kmeans')
            self._features = bundle.get('features')
            self._ready = True
            print(f"[O3] Model loaded: {bundle.get('version', 'unknown')}")
        except Exception as e:
            self._error = f"Cannot load O3 model: {e}"
            print(f"[O3] ERROR: {self._error}")

    def _build_features(self, lat, lon, doy, weather, elev=None, pop=None):
        """Build the 15-feature vector for one prediction."""
        import warnings
        w = weather


        _elev  = elev if elev is not None else 100.0
        _pop   = pop if pop is not None else DEFAULT_POP
        _pbl   = max(1.0, float(w.get('pbl', 800.0)))
        _temp  = float(w.get('temp', 28.0))
        _temp_k = _temp + 273.15  # Model was trained on Kelvin (ERA5)
        # Solar must always be present — fallback to April average if missing
        _solar = float(w.get('solar', 580.0))
        _cld   = float(w.get('cld', 20.0))
        _ws    = float(w.get('wind_speed', 3.0))

        # Derived features
        import math
        photo_index = _solar * (1.0 - _cld / 100.0)
        _humidity = float(w.get('humidity', _cld))
        uv_energy_sq = photo_index ** 2
        inversion_idx = _temp_k / (_pbl + 1.0)
        emission_sun_interaction = _pop * _solar
        ventilation = _pbl * _ws
        hist_norm = DEFAULT_O3_LAG
        
        # We need hour if provided, else use midday (12)
        hour_val = w.get('hour', 12)
        if hour_val is None: hour_val = 12
        hour_sin = math.sin(2 * math.pi * hour_val / 24.0)
        hour_cos = math.cos(2 * math.pi * hour_val / 24.0)

        df = pd.DataFrame([[
            round(lat, 1), round(lon, 1), _pbl, _temp_k, _solar, _elev, _pop, _humidity, _ws,
            uv_energy_sq, inversion_idx, emission_sun_interaction, 
            day_sin(doy), day_cos(doy), hour_sin, hour_cos, ventilation, hist_norm
        ]], columns=self._features)

        return df

    def _predict_single(self, raw_features):
        """Run sub-models and average."""
        preds = []

        # XGBoost
        if self._models.get('xgb'):
            try:
                p = float(self._models['xgb'].predict(raw_features)[0])
                preds.append(p)
            except Exception as e:
                print(f"[O3] XGBoost failed: {e}")

        # CatBoost
        if self._models.get('cat'):
            try:
                p = float(self._models['cat'].predict(raw_features)[0])
                preds.append(p)
            except Exception as e:
                print(f"[O3] CatBoost failed: {e}")

        if not preds:
            return None
        return float(np.mean(preds))

    # ── Public API ───────────────────────────────────────────────────────────

    def predict_for_town(self, town, range_str='1Y', overrides=None):
        """
        Given a Town model instance, returns predictions for the requested range.
        """
        self._load()
        if self._error:
            return {'error': self._error}

        if town.latitude is None or town.longitude is None:
            return {'error': f"Town '{town.name}' has no coordinates."}

        return self._predict_timeline(town.latitude, town.longitude, range_str, overrides=overrides)

    def predict_at_coords(self, lat, lon, range_str='1Y', overrides=None):
        """Predict O3 at arbitrary (lat, lon)."""
        self._load()
        if self._error:
            return {'error': self._error}

        result = self._predict_timeline(lat, lon, range_str, overrides=overrides)
        if result.get('error'):
            return result  # Don't try to add keys to an error dict
        result['lat'] = lat
        result['lon'] = lon
        result['is_custom'] = True
        return result

    def _predict_timeline(self, lat, lon, range_str, overrides=None):
        """Generate timeline of real model predictions."""
        points = generate_timeline_points(range_str)
        
        # Get baseline from spatial grid
        grid_data_service = get_grid_data_service()
        grid_pop, grid_elev = grid_data_service.get_data_at(lat, lon)
        
        elev = grid_elev
        if overrides and 'elev' in overrides: elev = float(overrides['elev'])
        
        pop = float(overrides.get('pop', grid_pop)) if overrides else grid_pop

        timeline = []
        all_values = []

        for pt in points:
            doy = pt['day_of_year']
            hour = pt.get('hour')
            weather = get_weather_for_day(lat, lon, doy, pt['year'], pollutant='o3', hour=hour)
            
            # Apply overrides
            if overrides:
                for k in ['temp', 'cld', 'wind_speed', 'solar', 'pbl']:
                    if k in overrides: weather[k] = float(overrides[k])
            
            # pass hour to _build_features
            weather['hour'] = hour

            raw = self._build_features(lat, lon, doy, weather, elev=elev, pop=pop)
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
            'weather_snapshot': get_weather_for_day(lat, lon, points[0]['day_of_year'], points[0]['year'], pollutant='o3'),
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
