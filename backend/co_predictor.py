"""
co_predictor.py
===============
Singleton that loads the RF model + raster once at Django startup,
then exposes real per-month predictions by varying weather features.

The CO TIF contains 12 FEATURE bands (not CO values):
  0: urban, 1: night, 2: temp, 3: dewpoint, 4: wind_speed,
  5: pressure, 6: temp_diff, 7: wind_u, 8: wind_v,
  9: urban_night, 10: temp_wind, 11: urban_temp

For each month, we perturb the weather bands using Odisha climate
averages, then run the RF model — giving genuinely different CO
predictions per month.
"""

import os
import numpy as np
import rasterio
import joblib

from weather_service import get_climate_for_month, get_live_weather
from timeline_utils import generate_timeline_points

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'core', 'rf_regularized.pkl')
TIF_PATH   = os.path.join(os.path.dirname(__file__), 'core', 'predictors_2026.tif')

# Band indices in the TIF
B_URBAN = 0; B_NIGHT = 1; B_TEMP = 2; B_DEWPOINT = 3
B_WIND  = 4; B_PRESSURE = 5; B_TEMP_DIFF = 6
B_WIND_U = 7; B_WIND_V = 8
B_URBAN_NIGHT = 9; B_TEMP_WIND = 10; B_URBAN_TEMP = 11

# Odisha annual average weather (baseline the TIF was built against)
ANNUAL_AVG = {
    'temp': 27.5, 'dewpoint': 18.5, 'wind_speed': 3.5, 'pressure': 1008.0,
}


class COPredictor:
    """Loads the model and raster once; predicts per month on demand."""

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
            self._model = joblib.load(MODEL_PATH)
        except Exception as e:
            self._error = f"Cannot load CO model: {e}"
            return
        try:
            self._src       = rasterio.open(TIF_PATH)
            self._transform = self._src.transform
            self._data      = self._src.read()          # (bands, height, width)
        except Exception as e:
            self._error = f"Cannot open CO raster: {e}"
            return
        self._ready = True
        print(f"[CO] Model loaded. {self._model.n_features_in_} features, "
              f"TIF {self._src.width}x{self._src.height}")

    def _get_pixel(self, lat, lon):
        """Get base pixel values from TIF. Returns (pixel_vals, error_str)."""
        col, row = ~self._transform * (lon, lat)
        col, row = int(round(col)), int(round(row))

        if not (0 <= row < self._src.height and 0 <= col < self._src.width):
            return None, f"Coordinates ({lat},{lon}) outside raster bounds."

        pixel_vals = self._data[:, row, col].astype(np.float64)
        if np.isnan(pixel_vals).any():
            return None, f"Raster has NaN at ({lat},{lon})."

        n_features = self._model.n_features_in_
        if len(pixel_vals) != n_features:
            return None, (f"Feature mismatch: raster {len(pixel_vals)} bands "
                          f"vs model expects {n_features}.")

        return pixel_vals, None

    def _perturb_for_month(self, base_pixel, month):
        """
        Create a month-specific feature vector by adjusting weather bands.
        Spatial features (urban, night, etc.) stay the same.
        Weather features are scaled by monthly/annual ratio.
        Interaction features are recomputed.
        """
        features = base_pixel.copy()
        climate = get_climate_for_month(month)

        # Scale weather bands relative to annual average
        temp_ratio     = climate['temp'] / ANNUAL_AVG['temp']
        dewpoint_ratio = climate['dewpoint'] / ANNUAL_AVG['dewpoint']
        wind_ratio     = climate['wind_speed'] / ANNUAL_AVG['wind_speed']
        pressure_ratio = climate['pressure'] / ANNUAL_AVG['pressure']

        features[B_TEMP]     *= temp_ratio
        features[B_DEWPOINT] *= dewpoint_ratio
        features[B_WIND]     *= wind_ratio
        features[B_PRESSURE] *= pressure_ratio
        features[B_WIND_U]   *= wind_ratio
        features[B_WIND_V]   *= wind_ratio

        # Recompute derived/interaction features
        features[B_TEMP_DIFF]   = features[B_TEMP] - features[B_DEWPOINT]
        features[B_TEMP_WIND]   = features[B_TEMP] * features[B_WIND]
        features[B_URBAN_TEMP]  = features[B_URBAN] * features[B_TEMP]
        # urban_night stays the same (no weather dependency)

        return features

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
        """
        Generate timeline of real RF model predictions.
        For CO, daily granularity within a month gives the same value
        (model has no day-of-year input), so we collapse to monthly.
        """
        base_pixel, err = self._get_pixel(lat, lon)
        if err:
            return {'error': err}

        points = generate_timeline_points(range_str)

        # For CO, group by month since model has no daily time input
        seen_months = set()
        month_values = {}

        for pt in points:
            month = pt['month']
            if month not in month_values:
                perturbed = self._perturb_for_month(base_pixel, month)
                co_val = float(self._model.predict(perturbed.reshape(1, -1))[0])
                month_values[month] = co_val

        timeline = []
        all_values = []

        for pt in points:
            month = pt['month']
            value = month_values[month]
            timeline.append({
                'year':          pt['year'],
                'month':         month,
                'monthName':     _month_name(month),
                'label':         pt['label'],
                'value':         round(value, 6),
                'is_prediction': True,
                'day_of_year':   pt['day_of_year'],
            })
            all_values.append(value)

        if not all_values:
            return {'error': 'No valid predictions generated.'}

        return {
            'base_value_2026': round(float(np.mean(all_values)), 6),
            'timeline':        timeline,
            'range':           range_str,
            'pollutant':       'co',
            'error':           None,
        }


def _month_name(m):
    return ['Jan','Feb','Mar','Apr','May','Jun',
            'Jul','Aug','Sep','Oct','Nov','Dec'][m - 1]


# Module-level singleton — loaded once when Django starts
co_predictor = COPredictor()
