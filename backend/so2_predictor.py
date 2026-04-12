"""
so2_predictor.py
================
Singleton that loads the SO2 Triple-Stack + Ridge meta model at Django startup.
Exposes real-time per-day predictions.

Model features (16):
  lat, lon, cluster, pbl, temp, elev, pop, cld,
  day_sin, day_cos, wind_speed, wind_sin, wind_cos,
  ventilation, thermal_trap, cluster_hist_avg

cluster_means DataFrame: (360 rows = 30 clusters × 12 months)
  columns: ['cluster', 'month', 'cluster_hist_avg']
"""

import os
import numpy as np
import joblib
import math

from weather_service import get_weather_for_day, get_elevation
from timeline_utils import generate_timeline_points, day_sin, day_cos

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ODISHA_MODEL(SO2_model).pkl')

DEFAULT_POP = 500000


class SO2Predictor:
    """Loads the SO2 triple-stack + Ridge meta ensemble once; predicts per day."""

    def __init__(self):
        self._models = None
        self._meta = None
        self._kmeans = None
        self._cluster_means = None
        self._features = None
        self._ready = False
        self._error = None

    def _load(self):
        if self._ready or self._error:
            return
        try:
            bundle = joblib.load(MODEL_PATH)
            self._models = {
                'lgbm': bundle['lgbm'],
                'xgb':  bundle['xgb'],
                'cat':  bundle['cat'],
            }
            self._meta          = bundle['meta']       # Ridge meta-learner
            self._kmeans        = bundle['kmeans']
            self._cluster_means = bundle['cluster_means']
            self._features      = bundle['features']
            self._ready = True
            print(f"[SO2] Model loaded. {self._kmeans.n_clusters} clusters, "
                  f"{len(self._features)} features")
        except Exception as e:
            self._error = f"Cannot load SO2 model: {e}"
            print(f"[SO2] ERROR: {self._error}")

    def _get_cluster_hist_avg(self, cluster_id, month):
        """Look up historical average SO2 for the cluster+month."""
        df = self._cluster_means
        row = df[(df['cluster'] == cluster_id) & (df['month'] == month)]
        if not row.empty:
            return float(row['cluster_hist_avg'].iloc[0])
        # Fallback: average across all months for this cluster
        fallback = df[df['cluster'] == cluster_id]['cluster_hist_avg']
        if not fallback.empty:
            return float(fallback.mean())
        return float(df['cluster_hist_avg'].mean())

    def _build_features(self, lat, lon, doy, month, weather, elev=None, pop=None):
        """Build the 16-feature vector for one prediction."""
        w = weather
        cluster = int(self._kmeans.predict(np.array([[lat, lon]]))[0])

        _elev = elev if elev is not None else 100.0
        _pop  = pop if pop is not None else DEFAULT_POP
        _pbl  = w['pbl']
        _temp = w['temp']
        _cld  = w['cld']
        _ws   = w['wind_speed']
        _wdir = w['wind_dir']

        # Derived features
        wind_sin    = math.sin(math.radians(_wdir))
        wind_cos    = math.cos(math.radians(_wdir))
        ventilation = _ws * _pbl
        # thermal_trap: high when temp inversion traps pollutants
        thermal_trap = (1.0 / (_temp + 273.15)) * (1.0 / max(_pbl, 1.0)) * 1e6

        cluster_hist_avg = self._get_cluster_hist_avg(cluster, month)

        # Feature vector in the exact order the model expects
        raw = np.array([[
            lat, lon, cluster, _pbl, _temp, _elev, _pop, _cld,
            day_sin(doy), day_cos(doy), _ws, wind_sin, wind_cos,
            ventilation, thermal_trap, cluster_hist_avg
        ]], dtype=np.float64)

        return raw

    def _predict_single(self, raw_features):
        """Run all 3 sub-models → feed into Ridge meta-learner."""
        preds = []

        # LightGBM
        try:
            p = float(self._models['lgbm'].predict(raw_features)[0])
            preds.append(p)
        except Exception as e:
            print(f"[SO2] LightGBM failed: {e}")
            preds.append(0.0)

        # XGBoost
        try:
            p = float(self._models['xgb'].predict(raw_features)[0])
            preds.append(p)
        except Exception as e:
            print(f"[SO2] XGBoost failed: {e}")
            preds.append(0.0)

        # CatBoost
        try:
            p = float(self._models['cat'].predict(raw_features)[0])
            preds.append(p)
        except Exception as e:
            print(f"[SO2] CatBoost failed: {e}")
            preds.append(0.0)

        # Ridge meta-learner combines the 3 predictions
        try:
            meta_input = np.array([preds])
            final = float(self._meta.predict(meta_input)[0])
            return max(0.001, final)
        except Exception as e:
            print(f"[SO2] Ridge meta failed: {e}")
            return max(0.001, float(np.mean(preds)))

    # ── Public API ───────────────────────────────────────────────────────────

    def predict_for_town(self, town, range_str='1Y'):
        self._load()
        if self._error:
            return {'error': self._error}
        if town.latitude is None or town.longitude is None:
            return {'error': f"Town '{town.name}' has no coordinates."}
        return self._predict_timeline(town.latitude, town.longitude, range_str)

    def predict_at_coords(self, lat, lon, range_str='1Y'):
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
            doy   = pt['day_of_year']
            month = pt['month']
            weather = get_weather_for_day(lat, lon, doy, pt['year'], pollutant='so2')
            raw = self._build_features(lat, lon, doy, month, weather, elev=elev)
            value = self._predict_single(raw)

            if value is None:
                continue

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
            return {'error': 'No valid SO2 predictions could be generated.'}

        # Automatically build the historical comparison table
        from historical_data_service import so2_history
        comparison_table = so2_history.build_comparison_data(lat, lon, self._build_features_and_predict)

        return {
            'base_value_2026': round(float(np.mean(all_values)), 6),
            'timeline':        timeline,
            'comparison_table': comparison_table,
            'range':           range_str,
            'pollutant':       'so2',
            'error':           None,
        }

    def _build_features_and_predict(self, weather, lat, lon, doy, month, elev, pop):
        """Helper for historical_data_service to run the full pipeline."""
        raw = self._build_features(lat, lon, doy, month, weather, elev=elev, pop=pop)
        return self._predict_single(raw)


def _month_name(m):
    return ['Jan','Feb','Mar','Apr','May','Jun',
            'Jul','Aug','Sep','Oct','Nov','Dec'][m - 1]


# Module-level singleton
so2_predictor = SO2Predictor()
