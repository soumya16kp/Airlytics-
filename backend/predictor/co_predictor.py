"""
co_predictor.py
===============
Singleton that loads the CO triple-stack ensemble (CatBoost + LightGBM + XGBoost)
once at Django startup, then exposes real per-month predictions using weather
and spatial features from the HuggingFace dataset.

Model features (35):
    lat, lon, elev, temp, pbl, humidity, wind_speed, wind_direction,
    ventilation, ventilation_inverse, stability, turbulence, richardson,
    dispersion_capacity, stagnation, valley_trapping, boundary_effect,
    combustion_potential, traffic_density, industrial_proxy, urban_heat,
    pop_lights, hour_sin, hour_cos, doy_sin, doy_cos, morning_rush,
    evening_rush, winter_inversion, summer_oxidation, seasonal,
    wind_temp, pbl_humidity, elev_temp, anchor
"""

import os
import math
import warnings
import numpy as np
import pandas as pd

from weather_service import get_weather_for_day, get_climate_for_month
from timeline_utils import generate_timeline_points, day_sin, day_cos
from grid_data_service import grid_data_service

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'co_prediction_model.pkl')

MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']


class COPredictor:
    """Loads the CO ensemble once; predicts per-point on demand."""

    def __init__(self):
        self._bundle   = None
        self._models   = None
        self._scaler   = None
        self._features = None
        self._ready    = False
        self._error    = None

    def _load(self):
        if self._ready or self._error:
            return
        import joblib
        try:
            # Try HuggingFace first, fall back to local
            hf_token = os.environ.get("HF_TOKEN", None)
            try:
                from huggingface_hub import hf_hub_download
                model_path = hf_hub_download(
                    repo_id="ObitUchiha91/airlytics-models",
                    filename="co_prediction_model.pkl",
                    token=hf_token
                )
                print("[CO] Model downloaded from Hugging Face.")
            except Exception as hf_err:
                print(f"[CO] HF download failed ({hf_err}), using local model.")
                model_path = MODEL_PATH

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                bundle = joblib.load(model_path)

            self._bundle   = bundle
            self._models   = {
                'catboost': bundle['catboost'],
                'lightgbm': bundle['lightgbm'],
                'xgboost':  bundle['xgboost'],
            }
            self._scaler        = bundle['scaler']
            self._features      = bundle['features']
            self._anchor_lookup = bundle['anchor_lookup']    # cluster, month → anchor
            self._unique_coords = bundle['unique_coords']    # lat_r, lon_r, cluster
            self._global_mean   = float(bundle.get('global_mean', 0.039))
            self._ready = True
            print(f"[CO] Model loaded. {len(self._features)} features. "
                  f"{len(self._unique_coords)} training coords.")
        except Exception as e:
            self._error = f"Cannot load CO model: {e}"
            print(f"[CO] ERROR: {self._error}")

    def _get_cluster_anchor(self, lat, lon, month):
        """Find closest cluster via unique_coords and get anchor value for month."""
        try:
            uc = self._unique_coords.copy()
            uc['dist'] = (uc['lat_r'] - round(lat, 1))**2 + (uc['lon_r'] - round(lon, 1))**2
            best = uc.loc[uc['dist'].idxmin()]
            cluster = int(best['cluster'])

            row = self._anchor_lookup[
                (self._anchor_lookup['cluster'] == cluster) &
                (self._anchor_lookup['month'] == month)
            ]
            if len(row) > 0:
                return float(row.iloc[0]['anchor'])
        except Exception:
            pass
        return self._global_mean

    def _build_features(self, lat, lon, doy, month, hour, weather, elev, pop):
        """Build the 35-feature vector for a single prediction point."""
        temp     = float(weather.get('temp', 28.0)) + 273.15   # Kelvin
        pbl      = max(1.0, float(weather.get('pbl', 800.0)))
        humidity = float(weather.get('humidity', 60.0))
        ws       = float(weather.get('wind_speed', 3.0))
        wd       = float(weather.get('wind_dir', 180.0))

        # Core derived features
        ventilation         = ws * pbl
        ventilation_inverse = 1.0 / max(1.0, ventilation)
        stability           = temp / max(1.0, pbl)
        turbulence          = ws ** 2 / max(1.0, pbl)
        richardson          = (9.81 * pbl * (temp - 280.0)) / max(1e-6, temp * ws**2)
        dispersion_capacity = ws * (pbl ** 0.5)
        stagnation          = 1.0 / max(1.0, ws * pbl)
        valley_trapping     = max(0.0, 1.0 - (elev / 1000.0))
        boundary_effect     = elev * stability

        # Emission proxies
        combustion_potential = (1.0 / max(1.0, temp)) * humidity
        traffic_density      = pop / max(1.0, ws)
        industrial_proxy     = pop * (1.0 - min(1.0, elev / 500.0))
        urban_heat           = temp * (pop / 100000.0)
        pop_lights           = pop * 0.5   # approximate lights proxy

        # Cyclical time features
        h_sin  = math.sin(2 * math.pi * hour / 24)
        h_cos  = math.cos(2 * math.pi * hour / 24)
        d_sin  = math.sin(2 * math.pi * doy / 365)
        d_cos  = math.cos(2 * math.pi * doy / 365)

        morning_rush   = 1.0 if 7 <= hour <= 9 else 0.0
        evening_rush   = 1.0 if 17 <= hour <= 19 else 0.0
        winter_inversion = max(0.0, (1.0 - pbl / 2000.0)) if month in (12, 1, 2) else 0.0
        summer_oxidation = 1.0 if month in (4, 5, 6) else 0.0
        seasonal         = math.cos(2 * math.pi * (month - 1) / 12)

        wind_temp    = ws * temp
        pbl_humidity = pbl * humidity
        elev_temp    = elev * temp

        anchor = self._get_cluster_anchor(lat, lon, month)

        feat = {
            'lat': lat, 'lon': lon, 'elev': elev,
            'temp': temp, 'pbl': pbl, 'humidity': humidity,
            'wind_speed': ws, 'wind_direction': wd,
            'ventilation': ventilation, 'ventilation_inverse': ventilation_inverse,
            'stability': stability, 'turbulence': turbulence,
            'richardson': richardson, 'dispersion_capacity': dispersion_capacity,
            'stagnation': stagnation, 'valley_trapping': valley_trapping,
            'boundary_effect': boundary_effect,
            'combustion_potential': combustion_potential,
            'traffic_density': traffic_density, 'industrial_proxy': industrial_proxy,
            'urban_heat': urban_heat, 'pop_lights': pop_lights,
            'hour_sin': h_sin, 'hour_cos': h_cos,
            'doy_sin': d_sin, 'doy_cos': d_cos,
            'morning_rush': morning_rush, 'evening_rush': evening_rush,
            'winter_inversion': winter_inversion, 'summer_oxidation': summer_oxidation,
            'seasonal': seasonal, 'wind_temp': wind_temp,
            'pbl_humidity': pbl_humidity, 'elev_temp': elev_temp,
            'anchor': anchor,
        }
        return pd.DataFrame([feat])[self._features]

    def _predict_point(self, feat_df):
        """Run ensemble of 3 models, return averaged prediction."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            X_scaled = self._scaler.transform(feat_df)
            X_scaled_df = pd.DataFrame(X_scaled, columns=self._features)

            preds = []
            try:
                preds.append(float(self._models['catboost'].predict(feat_df)[0]))
            except Exception:
                pass
            try:
                preds.append(float(self._models['lightgbm'].predict(X_scaled_df)[0]))
            except Exception:
                pass
            try:
                preds.append(float(self._models['xgboost'].predict(X_scaled_df)[0]))
            except Exception:
                pass

        return sum(preds) / len(preds) if preds else self._global_mean

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
        """Generate timeline of CO predictions using ensemble."""
        pop, elev = grid_data_service.get_data_at(lat, lon)
        if overrides:
            if 'elev' in overrides: elev = float(overrides['elev'])
            if 'pop'  in overrides: pop  = float(overrides['pop'])

        points = generate_timeline_points(range_str)
        # Collapse to monthly (CO model doesn't vary within a month significantly)
        month_values = {}
        for pt in points:
            month = pt['month']
            if month not in month_values:
                doy  = pt['day_of_year']
                hour = pt.get('hour', 12)
                weather = get_weather_for_day(lat, lon, doy, hour=hour)
                if overrides:
                    for k in ['temp', 'pbl', 'humidity', 'wind_speed', 'wind_dir']:
                        if k in overrides: weather[k] = float(overrides[k])
                feat_df = self._build_features(lat, lon, doy, month, hour, weather, elev, pop)
                month_values[month] = self._predict_point(feat_df)

        timeline = []
        all_values = []
        for pt in points:
            month = pt['month']
            value = month_values[month]
            timeline.append({
                'year':          pt['year'],
                'month':         month,
                'monthName':     MONTH_NAMES[month - 1],
                'label':         pt['label'],
                'value':         round(value, 6),
                'is_prediction': True,
                'day_of_year':   pt['day_of_year'],
            })
            all_values.append(value)

        if not all_values:
            return {'error': 'No valid CO predictions generated.'}

        return {
            'base_value_2026': round(float(np.mean(all_values)), 6),
            'timeline':        timeline,
            'range':           range_str,
            'pollutant':       'co',
            'error':           None,
        }


# Module-level singleton — loaded lazily on first request
co_predictor = COPredictor()
