"""
so2_predictor.py
================
Singleton that loads the SO2 Triple-Stack + Ridge meta model at Django startup.

Model bundle keys: lgbm, cat, xgb, meta, kmeans, cluster_means, features

EXACT feature order (verified from model bundle inspection):
  ['lat','lon','cluster','pbl','temp','elev','pop','cld',
   'day_sin','day_cos','wind_speed','wind_sin','wind_cos',
   'ventilation','thermal_trap','cluster_hist_avg']

cluster_means DataFrame columns: ['cluster', 'month', 'cluster_hist_avg']
KMeans fitted on: ['lat', 'lon'] (raw coordinates, 2 features)
Meta-learner input order: [lgbm_pred, cat_pred, xgb_pred]
"""

import os
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import joblib
import math
import warnings

from weather_service import get_weather_for_day, get_elevation
from timeline_utils import generate_timeline_points, day_sin, day_cos
from grid_data_service import get_grid_data_service

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'so2_prediction_model.pkl')
CLUSTER_MEANS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'so2_cluster_means.csv')

DEFAULT_POP = 5000


class SO2Predictor:
    """Loads the SO2 triple-stack + Ridge meta ensemble once; predicts per day."""

    def __init__(self):
        self._lgbm = None
        self._cat  = None
        self._xgb  = None
        self._meta = None
        self._kmeans = None
        self._cluster_means = None
        self._features = None
        self._ready = False
        self._error = None

    def _load(self):
        if self._ready or self._error:
            return
        import joblib
        import warnings
        try:
            hf_token = os.environ.get("HF_TOKEN", None)
            try:
                from huggingface_hub import hf_hub_download
                so2_model_path = hf_hub_download(
                    repo_id="ObitUchiha91/airlytics-models",
                    filename="so2_prediction_model.pkl",
                    token=hf_token
                )
                cluster_means_path = hf_hub_download(
                    repo_id="ObitUchiha91/airlytics-models",
                    filename="so2_cluster_means.csv",
                    token=hf_token
                )
                print("[SO2] Model and CSV files downloaded from Hugging Face.")
            except Exception as hf_err:
                print(f"[SO2] HF download failed ({hf_err}), using local model.")
                so2_model_path = MODEL_PATH
                cluster_means_path = CLUSTER_MEANS_PATH

            # Fail fast if cluster means CSV is missing
            if not cluster_means_path or not os.path.exists(cluster_means_path):
                raise RuntimeError("Missing SO2 lookup CSV file (so2_cluster_means.csv)")

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                bundle = joblib.load(so2_model_path)

            # Exact keys from the model bundle
            self._lgbm          = bundle['lgbm']
            self._cat           = bundle['cat']
            self._xgb           = bundle['xgb']
            self._meta          = bundle['meta']
            self._kmeans        = bundle['kmeans']
            self._features      = bundle['features']
            
            # Load DataFrame
            self._cluster_means = pd.read_csv(cluster_means_path)

            self._ready = True
            print(f"[SO2] Model loaded. {self._kmeans.n_clusters} clusters, "
                  f"{len(self._features)} features: {self._features}")
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

    def _build_features(self, lat, lon, doy, month, weather, elev=None, pop=None, overrides=None):
        """
        Build the exact 16-feature DataFrame the model expects.
        
        Feature order (from bundle['features']):
        lat, lon, cluster, pbl, temp, elev, pop, cld,
        day_sin, day_cos, wind_speed, wind_sin, wind_cos,
        ventilation, thermal_trap, cluster_hist_avg
        """
        # KMeans was fitted on ['lat', 'lon'] as a DataFrame
        coords_df = pd.DataFrame([[lat, lon]], columns=['lat', 'lon'])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cluster = int(self._kmeans.predict(coords_df)[0])

        _elev = elev if elev is not None else 100.0
        _pop  = float(pop) if pop is not None else DEFAULT_POP

        # Apply overrides on top of weather
        w = dict(weather)
        if overrides:
            for k in ['temp', 'cld', 'wind_speed', 'wind_dir', 'pbl']:
                if k in overrides:
                    w[k] = float(overrides[k])

        _pbl  = max(1.0, float(w.get('pbl', 800.0)))
        _temp = float(w.get('temp', 28.0))
        _cld  = float(w.get('cld', 20.0))
        _ws   = float(w.get('wind_speed', 3.0))
        _wdir = float(w.get('wind_dir', 210.0))

        # Derived features — EXACT formulas from research training code
        _temp_k = _temp + 273.15  # Model was trained on Kelvin
        _wind_sin    = math.sin(math.radians(_wdir))
        _wind_cos    = math.cos(math.radians(_wdir))
        _ventilation = _ws * _pbl
        _thermal_trap = _temp_k / (_pbl + 1.0) # Matches research 'thermal_ratio'
        _day_sin     = day_sin(doy)
        _day_cos     = day_cos(doy)

        cluster_hist_avg = self._get_cluster_hist_avg(cluster, month)

        # Build as DataFrame with exact feature names the model was trained on
        # Use rounded coordinates as model was trained on 0.1 degree grid
        X = pd.DataFrame([[
            round(lat, 1), round(lon, 1), cluster, _pbl, _temp_k, _elev, _pop, _cld,
            _day_sin, _day_cos, _ws, _wind_sin, _wind_cos,
            _ventilation, _thermal_trap, cluster_hist_avg
        ]], columns=self._features)

        return X

    def _predict_single(self, X):
        """Run all 3 sub-models → Ridge meta-learner. Order: lgbm, cat, xgb."""
        preds = []

        # LightGBM
        try:
            p = float(self._lgbm.predict(X)[0])
            preds.append(p)
        except Exception as e:
            print(f"[SO2] LightGBM failed: {e}")
            preds.append(0.0)

        # CatBoost (second — matching training meta-learner order)
        try:
            p = float(self._cat.predict(X)[0])
            preds.append(p)
        except Exception as e:
            print(f"[SO2] CatBoost failed: {e}")
            preds.append(0.0)

        # XGBoost
        try:
            p = float(self._xgb.predict(X)[0])
            preds.append(p)
        except Exception as e:
            print(f"[SO2] XGBoost failed: {e}")
            preds.append(0.0)

        # Ridge meta-learner combines the 3 predictions [lgbm, cat, xgb]
        try:
            meta_input = np.array([preds])
            final = float(self._meta.predict(meta_input)[0])
            return max(0.001, final)
        except Exception as e:
            print(f"[SO2] Ridge meta failed: {e}")
            return max(0.001, float(np.mean([p for p in preds if p > 0])))

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
        """Generate timeline of real model predictions."""
        points = generate_timeline_points(range_str)

        # Get baseline pop/elev from spatial grid service
        grid_data_service = get_grid_data_service()
        grid_pop, grid_elev = grid_data_service.get_data_at(lat, lon)

        elev = grid_elev
        if overrides and 'elev' in overrides:
            elev = float(overrides['elev'])

        pop = float(overrides.get('pop', grid_pop)) if overrides else grid_pop

        timeline = []
        all_values = []

        for pt in points:
            doy   = pt['day_of_year']
            month = pt['month']
            hour  = pt.get('hour')
            weather = get_weather_for_day(lat, lon, doy, pt['year'], pollutant='so2', hour=hour)

            X = self._build_features(lat, lon, doy, month, weather, elev=elev, pop=pop, overrides=overrides)
            value = self._predict_single(X)

            if value is None:
                continue

            timeline.append({
                'year':          pt['year'],
                'month':         month,
                'hour':          hour,
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
            'weather_snapshot': get_weather_for_day(lat, lon, points[0]['day_of_year'], points[0]['year'], pollutant='so2'),
            'error':           None,
        }

    def _build_features_and_predict(self, weather, lat, lon, doy, month, elev, pop):
        """Helper for historical_data_service to run the full pipeline."""
        X = self._build_features(lat, lon, doy, month, weather, elev=elev, pop=pop)
        return self._predict_single(X)


def _month_name(m):
    return ['Jan','Feb','Mar','Apr','May','Jun',
            'Jul','Aug','Sep','Oct','Nov','Dec'][m - 1]


# Module-level singleton
so2_predictor = SO2Predictor()
