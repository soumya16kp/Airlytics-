import os
import numpy as np
import pandas as pd
import rasterio
import math
import datetime
from catboost import CatBoostRegressor

from weather_service import get_weather_for_day, get_elevation
from timeline_utils import generate_timeline_points, day_sin, day_cos
from grid_data_service import get_grid_data_service

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'no2_optimized.cbm')
TIF_PATH   = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'NO2_2026_FullYear_12Bands.tif')

class NO2Predictor:
    """Loads the CatBoost model and raster once; predicts per day on demand."""

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
        
        hf_token = os.environ.get("HF_TOKEN", None)
        
        try:
            self._model = CatBoostRegressor()
            # Try HuggingFace first, then fall back to local
            try:
                from huggingface_hub import hf_hub_download
                actual_model_path = hf_hub_download(
                    repo_id="ObitUchiha91/airlytics-models",
                    filename="no2_optimized.cbm",
                    token=hf_token
                )
                print("[NO2] Model downloaded from Hugging Face.")
            except Exception as hf_err:
                print(f"[NO2] HF download failed ({hf_err}), using local model.")
                actual_model_path = MODEL_PATH
                
            self._model.load_model(actual_model_path)
        except Exception as e:
            self._error = f"Cannot load NO2 model: {e}"
            return
            
        try:
            # TIF is optional — NO2 can predict without it using CatBoost directly
            if os.path.exists(TIF_PATH):
                self._src       = rasterio.open(TIF_PATH)
                self._transform = self._src.transform
                self._data      = self._src.read()   # (12, height, width)
                print(f"[NO2] TIF loaded: {self._src.width}x{self._src.height}, "
                      f"{self._src.count} bands")
            else:
                print("[NO2] TIF not found — will use CatBoost predictions for all ranges.")
                self._src = None
                self._data = None
                self._transform = None
        except Exception as e:
            print(f"[NO2] TIF load failed ({e}) — will use CatBoost for all ranges.")
            self._src = None
            self._data = None
            self._transform = None
            
        self._ready = True
        print(f"[NO2] Model loaded successfully.")

    def _get_tif_monthly(self, lat, lon):
        """Read all 12 monthly values directly from TIF. Returns (values, error)."""
        if self._src is None or self._data is None:
            return None, "TIF not loaded — using CatBoost instead."
        col, row = ~self._transform * (lon, lat)
        col, row = int(round(col)), int(round(row))

        if not (0 <= row < self._src.height and 0 <= col < self._src.width):
            return None, f"Coordinates ({lat},{lon}) outside NO2 raster bounds."

        pixel_vals = self._data[:, row, col].astype(np.float64)
        if np.isnan(pixel_vals).any():
            return None, f"NO2 raster has NaN at ({lat},{lon})."

        return pixel_vals.tolist(), None

    def _predict_for_day(self, lat, lon, doy, month, elev=100.0, weather=None, pop=5000.0, overrides=None, baseline_spatial=None, pt=None):
        """Run CatBoost for a specific day-of-year."""
        _elev = elev
        _cld  = weather.get('cld', 20.0) if weather else 20.0
        _pop  = pop
        _temp = weather.get('temp', 28.0) if weather else 28.0
        _temp_k = _temp + 273.15
        
        # Spatial baseline fallback values
        base_ndvi = baseline_spatial.get('ndvi', 0.5) if baseline_spatial else 0.5
        base_lights = baseline_spatial.get('lights', 0.5) if baseline_spatial else 0.5
        base_urban = baseline_spatial.get('urban', 0) if baseline_spatial else 0
        base_humidity = baseline_spatial.get('humidity', 50.0) if baseline_spatial else 50.0
        
        _ndvi = float(overrides.get('ndvi', base_ndvi)) if overrides else base_ndvi
        _lights = float(overrides.get('lights', base_lights)) if overrides else base_lights
        _urban = int(overrides.get('urban', base_urban)) if overrides else base_urban
        _humidity = float(weather.get('humidity', base_humidity)) if weather else base_humidity

        # Derived features
        _ws = float(weather.get('wind_speed', 3.0)) if weather else 3.0
        _pbl = float(weather.get('pbl', 800.0)) if weather else 800.0
        _ventilation = _ws * _pbl
        _solar = float(weather.get('solar', 400.0)) if weather else 400.0
        _thermal_ratio = _temp_k / max(1.0, _pbl)
        
        # Date features
        _hour = pt.get('hour', 12) if pt else 12
        
        _weekend = 0
        if pt and pt.get('date'):
            try:
                _dt = datetime.date.fromisoformat(pt['date'])
                _weekend = 1 if _dt.weekday() >= 5 else 0
            except Exception:
                pass
        
        # Formulate all 26 features in order expected by model
        features = {
            'lat_r': round(lat, 4),
            'lon_r': round(lon, 4),
            'pbl': _pbl,
            'temp': _temp_k,
            'elev': _elev,
            'pop': _pop,
            'cld': _cld,
            'humidity': _humidity,
            'ndvi': _ndvi,
            'lights': _lights,
            'urban': _urban,
            'ventilation': _ventilation,
            'solar': _solar,
            'thermal_ratio': _thermal_ratio,
            'month': month,
            'hour': _hour,
            'weekend': _weekend,
            'lights_pop': _lights * _pop,
            'pop_pbl': _pop * _pbl,
            'temp_pbl': _temp_k * _pbl,
            'lights_sq': _lights ** 2,
            'pop_sq': _pop ** 2,
            'lights_per_pop': _lights / (_pop + 0.001),
            'hour_sin': math.sin(2 * math.pi * _hour / 24),
            'hour_cos': math.cos(2 * math.pi * _hour / 24),
            'anchor': 0.0
        }
        
        # Predict using CatBoost
        df_feats = pd.DataFrame([features])[self._model.feature_names_]
        pred = float(self._model.predict(df_feats)[0])
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
        - For daily (1D, 1W, 1M): run CatBoost per day
        """
        points = generate_timeline_points(range_str)
        
        # Get baseline from Hugging Face dataset
        baseline_spatial = {}
        from extractor_service import no2_api as api
        try:
            df_baseline = api.get_data_for_coordinate(lat, lon)
            if not df_baseline.empty:
                row = df_baseline.iloc[0]
                baseline_spatial['pop'] = float(row.get('pop', 0.8))
                baseline_spatial['elev'] = float(row.get('elev', 50.0))
                baseline_spatial['ndvi'] = float(row.get('ndvi', 0.5))
                baseline_spatial['lights'] = float(row.get('lights', 0.5))
                baseline_spatial['urban'] = int(row.get('urban', 0))
                baseline_spatial['humidity'] = float(row.get('humidity', 50.0))
        except Exception as e:
            print(f"[NO2] Hugging Face baseline retrieval failed: {e}")

        # Fallback to local grid service if Hugging Face was empty or failed
        grid_data_service = get_grid_data_service()
        grid_pop, grid_elev = grid_data_service.get_data_at(lat, lon)
        
        elev = baseline_spatial.get('elev', grid_elev)
        if overrides and 'elev' in overrides: elev = float(overrides['elev'])
        
        pop = baseline_spatial.get('pop', (grid_pop / 5000.0 if grid_pop > 10 else grid_pop))
        if overrides and 'pop' in overrides: pop = float(overrides['pop'])

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
                # Run CatBoost for this specific day
                hour = pt.get('hour')
                weather = get_weather_for_day(lat, lon, doy, hour=hour)
                
                # Apply weather overrides
                if overrides:
                    for k in ['temp', 'cld', 'wind_speed', 'wind_dir']:
                        if k in overrides: weather[k] = float(overrides[k])
                
                value = self._predict_for_day(lat, lon, doy, month, elev, weather, pop=pop, overrides=overrides, baseline_spatial=baseline_spatial, pt=pt)

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
