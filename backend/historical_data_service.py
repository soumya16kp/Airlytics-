"""
Historical Data Service for Airlytics
======================================
Loads scraped Sentinel-5P + ERA5 weather CSV data (2020-2025) and provides:
  - Spatial lookup (nearest grid pixel to any lat/lon)
  - Weather feature extraction (with unit conversions)
  - Real observed pollutant values (ground truth from Sentinel-5P)
  - Comparison table generation (model predicted vs real observed)

CSV column layout:
  SO2: date, lat, lon, so2,  pbl, temp, u, v, elev, pop, cld
  O3:  date, lat, lon, o3,   pbl, temp, u, v, solar, elev, pop, cld

Unit conversions applied:
  temp:  Kelvin   → Celsius   (subtract 273.15)
  cld:   fraction → percent   (multiply by 100)
  u, v:  m/s components → wind_speed (m/s) + wind_dir (degrees)
  pbl:   metres (direct)
  solar: W/m² (direct, O3 only)
"""

import os
import math
import datetime
import numpy as np

# ---------------------------------------------------------------------------
# Try to import pandas – required for CSV loading
# ---------------------------------------------------------------------------
try:
    import pandas as pd
except ImportError:
    pd = None
    print("[HistoricalDataService] WARNING: pandas not installed. "
          "Historical comparison will not work. Run: pip install pandas")

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_CONFIG = {
    'so2': {
        'dir': os.path.join(BASE_DIR, 'so2_weather_data'),
        'pattern': 'SO2_Odisha_{}.csv',
        'value_col': 'so2',
        'has_solar': False,
    },
    'o3': {
        'dir': os.path.join(BASE_DIR, 'o3_weather_data'),
        'pattern': 'O3_Odisha_improv{}.csv',
        'value_col': 'o3',
        'has_solar': True,
    },
}

AVAILABLE_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LATEST_DATA_DATE = datetime.date(2025, 12, 31)

# Maximum distance (degrees) for nearest-pixel match
# ~0.5° ≈ 55 km — anything beyond this returns "no data"
MAX_PIXEL_DISTANCE = 0.5

# Comparison period definitions (label, months_back)
COMPARISON_PERIODS = [
    ('Last 1 Month',  'H1M',  1),
    ('Last 3 Months', 'H3M',  3),
    ('Last 1 Year',   'H1Y',  12),
    ('Last 3 Years',  'H3Y',  36),
    ('Last 5 Years',  'H5Y',  60),
]


class HistoricalDataService:
    """
    Loads and queries historical CSV data for a single pollutant (SO₂ or O₃).

    Usage:
        from historical_data_service import so2_history, o3_history
        table = so2_history.build_comparison_data(lat, lon, predictor_fn)
    """

    def __init__(self, pollutant):
        if pollutant not in DATA_CONFIG:
            raise ValueError(f"Unknown pollutant: {pollutant}")

        cfg = DATA_CONFIG[pollutant]
        self._pollutant = pollutant
        self._data_dir = cfg['dir']
        self._file_pattern = cfg['pattern']
        self._value_col = cfg['value_col']
        self._has_solar = cfg['has_solar']

        # Caches
        self._year_dfs = {}          # year → pandas DataFrame
        self._grid_points = None     # numpy array of unique (lat, lon)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_year(self, year):
        """Load a single year's CSV into a pandas DataFrame (cached)."""
        if pd is None:
            return None
        if year in self._year_dfs:
            return self._year_dfs[year]

        filepath = os.path.join(self._data_dir, self._file_pattern.format(year))
        if not os.path.exists(filepath):
            print(f"[HistData-{self._pollutant}] File not found: {filepath}")
            return None

        print(f"[HistData-{self._pollutant}] Loading {os.path.basename(filepath)}...")
        df = pd.read_csv(filepath)
        df['date_parsed'] = pd.to_datetime(df['date'])
        df['date_only'] = df['date_parsed'].dt.date
        df['month'] = df['date_parsed'].dt.month
        df['day_of_year'] = df['date_parsed'].dt.dayofyear
        df['year'] = year

        self._year_dfs[year] = df
        print(f"[HistData-{self._pollutant}] Loaded {len(df):,} rows for {year}")
        return df

    def _ensure_grid(self):
        """Build the spatial grid index from any loaded year."""
        if self._grid_points is not None:
            return

        # Try to load 2024 (most complete) to extract grid
        for y in [2024, 2025, 2023, 2022, 2021, 2020]:
            df = self._load_year(y)
            if df is not None:
                self._grid_points = df[['lat', 'lon']].drop_duplicates().values
                print(f"[HistData-{self._pollutant}] Grid: "
                      f"{len(self._grid_points)} pixels, "
                      f"lat [{self._grid_points[:,0].min():.3f}–"
                      f"{self._grid_points[:,0].max():.3f}], "
                      f"lon [{self._grid_points[:,1].min():.3f}–"
                      f"{self._grid_points[:,1].max():.3f}]")
                return

    # ------------------------------------------------------------------
    # Spatial lookup
    # ------------------------------------------------------------------

    def _find_nearest_pixel(self, lat, lon):
        """
        Find the nearest grid pixel to (lat, lon).
        Returns (nearest_lat, nearest_lon) or (None, None) if too far.
        """
        self._ensure_grid()
        if self._grid_points is None or len(self._grid_points) == 0:
            return None, None

        dists = np.sqrt(
            (self._grid_points[:, 0] - lat) ** 2 +
            (self._grid_points[:, 1] - lon) ** 2
        )
        idx = np.argmin(dists)

        if dists[idx] > MAX_PIXEL_DISTANCE:
            print(f"[HistData-{self._pollutant}] Location ({lat},{lon}) is "
                  f"{dists[idx]:.2f}° from nearest pixel — too far.")
            return None, None

        return float(self._grid_points[idx, 0]), float(self._grid_points[idx, 1])

    # ------------------------------------------------------------------
    # Unit conversions
    # ------------------------------------------------------------------

    def _convert_weather(self, temp_k, cld_frac, u, v, pbl, solar=None):
        """Convert CSV raw values to model-expected units."""
        wind_speed = math.sqrt(u ** 2 + v ** 2)
        wind_dir = math.degrees(math.atan2(-u, -v)) % 360

        weather = {
            'temp': temp_k - 273.15,       # K → °C
            'cld': cld_frac * 100.0,        # fraction → %
            'wind_speed': wind_speed,        # m/s
            'wind_dir': wind_dir,            # degrees
            'pbl': pbl,                      # metres (direct)
            'dewpoint': 18.0,                # default (not in CSV)
            'pressure': 1010.0,              # default (not in CSV)
        }

        if solar is not None:
            weather['solar'] = solar
        else:
            weather['solar'] = 400.0  # default for SO₂ (model ignores it)

        return weather

    # ------------------------------------------------------------------
    # Core query: get data for a pixel across years
    # ------------------------------------------------------------------

    def _get_pixel_data(self, nearest_lat, nearest_lon, years):
        """
        Load and concatenate data for a specific pixel across multiple years.
        Returns a pandas DataFrame filtered to the exact pixel.
        """
        frames = []
        for year in years:
            df = self._load_year(year)
            if df is None:
                continue
            mask = (
                (df['lat'] == nearest_lat) &
                (df['lon'] == nearest_lon)
            )
            subset = df[mask]
            if not subset.empty:
                frames.append(subset)

        if not frames:
            return None

        return pd.concat(frames, ignore_index=True)

    # ------------------------------------------------------------------
    # Comparison table builder
    # ------------------------------------------------------------------

    def build_comparison_data(self, lat, lon, predictor_fn):
        """
        Build the 5-row comparison table (H1M → H5Y).

        Args:
            lat, lon: user's target coordinates
            predictor_fn: callable(weather, lat, lon, doy, month, elev, pop)
                          → predicted_value (float)

        Returns:
            list of dicts, each with:
              period, range_code, model_predicted_avg, real_observed_avg,
              variance_pct, data_points
        """
        nearest_lat, nearest_lon = self._find_nearest_pixel(lat, lon)
        if nearest_lat is None:
            print(f"[HistData-{self._pollutant}] No pixel found near ({lat},{lon})")
            return [self._empty_row(p[0], p[1]) for p in COMPARISON_PERIODS]

        # Load ALL years and filter to this pixel
        pixel_df = self._get_pixel_data(nearest_lat, nearest_lon, AVAILABLE_YEARS)
        if pixel_df is None or pixel_df.empty:
            return [self._empty_row(p[0], p[1]) for p in COMPARISON_PERIODS]

        # Group by year-month for monthly aggregation
        pixel_df['ym'] = pixel_df['date_parsed'].dt.to_period('M')

        # Columns to aggregate
        agg_cols = {
            'temp': 'mean', 'cld': 'mean', 'u': 'mean', 'v': 'mean',
            'pbl': 'mean', 'elev': 'first', 'pop': 'first',
            self._value_col: 'mean',
            'day_of_year': 'median', 'month': 'first', 'year': 'first',
        }
        if self._has_solar:
            agg_cols['solar'] = 'mean'

        monthly = pixel_df.groupby('ym').agg(agg_cols).reset_index()

        # Run model on each monthly point
        monthly_results = []
        for _, row in monthly.iterrows():
            solar_val = float(row['solar']) if self._has_solar else None
            weather = self._convert_weather(
                temp_k=float(row['temp']),
                cld_frac=float(row['cld']),
                u=float(row['u']),
                v=float(row['v']),
                pbl=float(row['pbl']),
                solar=solar_val,
            )
            doy = int(row['day_of_year'])
            month = int(row['month'])
            elev = float(row['elev'])
            pop = max(0.0, float(row['pop']))

            try:
                predicted = predictor_fn(weather, nearest_lat, nearest_lon,
                                         doy, month, elev, pop)
            except Exception as e:
                print(f"[HistData-{self._pollutant}] Prediction failed "
                      f"for {row['ym']}: {e}")
                predicted = None

            # Apply scale to raw Sentinel values so they match model's display unit (DU)
            scale = 1000000.0 if self._pollutant == 'so2' else 1000.0
            observed = float(row[self._value_col]) * scale

            monthly_results.append({
                'ym': row['ym'],
                'date': row['ym'].to_timestamp().date(),
                'predicted': predicted,
                'observed': observed,
            })

        # Build comparison for each period
        comparison = []
        for period_name, range_code, months_back in COMPARISON_PERIODS:
            cutoff_date = LATEST_DATA_DATE - datetime.timedelta(days=months_back * 30)

            in_period = [
                r for r in monthly_results
                if r['date'] >= cutoff_date and r['predicted'] is not None
            ]

            if in_period:
                pred_avg = sum(r['predicted'] for r in in_period) / len(in_period)
                obs_avg = sum(r['observed'] for r in in_period) / len(in_period)

                if obs_avg != 0:
                    variance = ((pred_avg - obs_avg) / abs(obs_avg)) * 100
                else:
                    variance = 0.0

                comparison.append({
                    'period': period_name,
                    'range_code': range_code,
                    'model_predicted_avg': round(pred_avg, 8),
                    'real_observed_avg': round(obs_avg, 8),
                    'variance_pct': round(variance, 2),
                    'data_points': len(in_period),
                })
            else:
                comparison.append(self._empty_row(period_name, range_code))

        return comparison

    def get_pixel_historical_avg(self, lat, lon, target_doy):
        """
        Compute pixel-specific historical weather average for a given day-of-year.
        Used for future predictions beyond 16 days (replacing ODISHA_CLIMATE).
        Averages the same DOY (±7 days) across all available years.

        Returns a weather dict or None.
        """
        nearest_lat, nearest_lon = self._find_nearest_pixel(lat, lon)
        if nearest_lat is None:
            return None

        pixel_df = self._get_pixel_data(nearest_lat, nearest_lon, AVAILABLE_YEARS)
        if pixel_df is None or pixel_df.empty:
            return None

        # Filter to ±7 days around target DOY
        doy_min = (target_doy - 7) % 366
        doy_max = (target_doy + 7) % 366

        if doy_min < doy_max:
            mask = (pixel_df['day_of_year'] >= doy_min) & \
                   (pixel_df['day_of_year'] <= doy_max)
        else:
            # Wraps around year boundary (e.g., DOY 360 ± 7)
            mask = (pixel_df['day_of_year'] >= doy_min) | \
                   (pixel_df['day_of_year'] <= doy_max)

        subset = pixel_df[mask]
        if subset.empty:
            return None

        solar_val = float(subset['solar'].mean()) if self._has_solar else None
        weather = self._convert_weather(
            temp_k=float(subset['temp'].mean()),
            cld_frac=float(subset['cld'].mean()),
            u=float(subset['u'].mean()),
            v=float(subset['v'].mean()),
            pbl=float(subset['pbl'].mean()),
            solar=solar_val,
        )
        return weather

    @staticmethod
    def _empty_row(period_name, range_code):
        return {
            'period': period_name,
            'range_code': range_code,
            'model_predicted_avg': None,
            'real_observed_avg': None,
            'variance_pct': None,
            'data_points': 0,
        }


# ---------------------------------------------------------------------------
# Module-level singletons (lazy – CSVs loaded on first call)
# ---------------------------------------------------------------------------
so2_history = HistoricalDataService('so2')
o3_history = HistoricalDataService('o3')
