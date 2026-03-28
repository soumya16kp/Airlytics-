"""
co_predictor.py
===============
Singleton that loads the RF model + raster once at Django startup,
then exposes `predict_for_town(town)` for real-time API calls.

Usage (from views.py):
    from co_predictor import co_predictor
    result = co_predictor.predict_for_town(town_obj)
"""

import os
import numpy as np
import rasterio
import joblib
from rasterio.transform import rowcol

SEASONAL_FACTORS = [1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.7, 0.8, 0.9, 1.1, 1.2]

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'core', 'rf_regularized.pkl')
TIF_PATH   = os.path.join(os.path.dirname(__file__), 'core', 'predictors_2026.tif')


class COPredictor:
    """Loads the model and raster once; predicts per town on demand."""

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
            self._error = f"Cannot load model: {e}"
            return

        try:
            self._src       = rasterio.open(TIF_PATH)
            self._transform = self._src.transform
            self._data      = self._src.read()          # (bands, height, width)
        except Exception as e:
            self._error = f"Cannot open raster: {e}"
            return

        self._ready = True

    # ── public ────────────────────────────────────────────────────────────────

    def predict_for_town(self, town):
        """
        Given a Town model instance (must have .latitude and .longitude set),
        returns a dict:
          {
            'base_co_2026': float,          # raw model output for the pixel
            'monthly_2026': [float x 12],   # Jan-Dec 2026 predicted values
            'monthly_history': {            # 2020-2025 back-trended values
                year: [float x 12], ...
            },
            'error': str | None
          }
        """
        self._load()

        if self._error:
            return {'error': self._error}

        if town.latitude is None or town.longitude is None:
            return {'error': f"Town '{town.name}' has no coordinates. Update lat/lon in DB."}

        lat, lon = town.latitude, town.longitude

        # Convert lon/lat → raster pixel
        col, row = ~self._transform * (lon, lat)
        col, row = int(round(col)), int(round(row))

        if not (0 <= row < self._src.height and 0 <= col < self._src.width):
            return {'error': f"Town '{town.name}' ({lat},{lon}) is outside raster bounds."}

        pixel_vals = self._data[:, row, col].astype(np.float64)

        if np.isnan(pixel_vals).any():
            return {'error': f"Raster has NaN values at '{town.name}' ({lat},{lon})."}

        n_features = self._model.n_features_in_
        if len(pixel_vals) != n_features:
            return {
                'error': (
                    f"Feature mismatch: raster has {len(pixel_vals)} bands "
                    f"but model expects {n_features}."
                )
            }

        base_co = float(self._model.predict(pixel_vals.reshape(1, -1))[0])

        # Monthly 2026
        # Generate a more realistic timeline (COVID dips, post-lockdown growth)
        monthly_2026 = [round(base_co * sf, 6) for sf in SEASONAL_FACTORS]
        monthly_history = {}
        for year in range(2025, 2019, -1):
            if year == 2020:
                covid_dip = 0.82
                base_at_year = (base_co / (1.03 ** (2026 - year))) * covid_dip
            else:
                base_at_year = base_co / (1.031 ** (2026 - year))
            monthly_history[year] = [round(base_at_year * sf, 6) for sf in SEASONAL_FACTORS]

        return {
            'base_co_2026':    round(base_co, 5),
            'monthly_2026':    monthly_2026,
            'monthly_history': monthly_history,
            'error':           None,
        }

    def predict_at_coords(self, lat, lon):
        """
        Predict CO at any arbitrary (lat, lon) — used by the draggable map marker.
        Returns {'base_co_2026': float, 'error': str|None}
        """
        self._load()
        if self._error:
            return {'error': self._error}

        col, row = ~self._transform * (lon, lat)
        col, row = int(round(col)), int(round(row))

        if not (0 <= row < self._src.height and 0 <= col < self._src.width):
            return {'error': f'Coordinates ({lat}, {lon}) are outside the raster coverage area.'}

        pixel_vals = self._data[:, row, col].astype(np.float64)
        if np.isnan(pixel_vals).any():
            return {'error': f'No valid data at ({lat}, {lon}) — may be ocean or cloud-masked.'}

        n_features = self._model.n_features_in_
        if len(pixel_vals) != n_features:
            return {'error': f'Feature mismatch: {len(pixel_vals)} bands vs {n_features} expected.'}

        co = float(self._model.predict(pixel_vals.reshape(1, -1))[0])
        # Apply March seasonal factor (index 2)
        march_co = round(co * SEASONAL_FACTORS[2], 6)

        # Generate a more realistic timeline (COVID dips, post-lockdown growth)
        monthly_2026 = [round(co * sf, 6) for sf in SEASONAL_FACTORS]
        monthly_history = {}
        for year in range(2025, 2019, -1):
            # Base logic: 2026 value back-trended
            # COVID Lockdown (2020 approx 18% lower than trend)
            if year == 2020:
                covid_dip = 0.82
                base_at_year = (co / (1.03 ** (2026 - year))) * covid_dip
            else:
                base_at_year = co / (1.031 ** (2026 - year))
            
            monthly_history[year] = [round(base_at_year * sf, 6) for sf in SEASONAL_FACTORS]

        return {
            'base_co_2026': round(co, 6),
            'march_co_2026': march_co,
            'monthly_2026': monthly_2026,
            'monthly_history': monthly_history,
            'lat': lat,
            'lon': lon,
            'error': None,
        }


# Module-level singleton — loaded once when Django starts
co_predictor = COPredictor()
