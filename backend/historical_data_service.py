"""
Historical Data Service for Airlytics
======================================
Provides historical weather and pollution data using Google Earth Engine dynamically.
"""

import os
import math
import datetime

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AVAILABLE_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LATEST_DATA_DATE = datetime.date(2025, 12, 31)

COMPARISON_PERIODS = [
    ('Last 1 Month',  'H1M',  1),
    ('Last 3 Months', 'H3M',  3),
    ('Last 1 Year',   'H1Y',  12),
    ('Last 3 Years',  'H3Y',  36),
    ('Last 5 Years',  'H5Y',  60),
]

from gee_extractor import EarthEngineExtractor

class HistoricalDataService:
    """
    Loads and queries historical data from Earth Engine for a single pollutant.

    Usage:
        from historical_data_service import so2_history, o3_history
        table = so2_history.build_comparison_data(lat, lon, predictor_fn)
    """

    def __init__(self, pollutant):
        self._pollutant = pollutant
        self._has_solar = (pollutant == 'o3')
        # Initialize GEE Extractor
        self.extractor = EarthEngineExtractor()

    def _convert_weather(self, temp_k, cld_frac, u, v, pbl, solar=None):
        """Convert raw GEE values to model-expected units."""
        wind_speed = math.sqrt(u ** 2 + v ** 2)
        wind_dir = math.degrees(math.atan2(-u, -v)) % 360

        weather = {
            'temp': temp_k - 273.15,         # K → °C
            'cld': cld_frac * 100.0,         # fraction → %
            'wind_speed': wind_speed,        # m/s
            'wind_dir': wind_dir,            # degrees
            'pbl': pbl,                      # metres
            'dewpoint': 18.0,                # default
            'pressure': 1010.0,              # default
        }

        if solar is not None:
            weather['solar'] = solar
        else:
            weather['solar'] = 400.0

        return weather

    def get_monthly_no2_data(self, lat, lon):
        from no2_extractor import NO2HuggingFaceAPI
        import pandas as pd
        api = NO2HuggingFaceAPI()
        try:
            df = api.get_data_for_coordinate(lat, lon, "*")
            if df.empty:
                return []
                
            lat_col = 'latitude' if 'latitude' in df.columns else 'lat'
            lon_col = 'longitude' if 'longitude' in df.columns else 'lon'
            no2_col = 'no2_level' if 'no2_level' in df.columns else 'no2'
            
            df['parsed_date'] = pd.to_datetime(df['date'] if 'date' in df.columns else df['parsed_date'])
            df['year'] = df['parsed_date'].dt.year
            df['month'] = df['parsed_date'].dt.month
            df['doy'] = df['parsed_date'].dt.dayofyear
            
            grouped = df.groupby(['year', 'month'])
            
            monthly_results = []
            for (yr, mth), group in grouped:
                ym_str = f"{yr}-{mth:02d}"
                avg_no2 = group[no2_col].mean()
                avg_temp = group['temp'].mean() if 'temp' in group.columns else 298.0
                avg_cld = group['cld'].mean() if 'cld' in group.columns else 0.2
                avg_u = group['u'].mean() if 'u' in group.columns else 0.0
                avg_v = group['v'].mean() if 'v' in group.columns else 0.0
                avg_pbl = group['pbl'].mean() if 'pbl' in group.columns else 1000.0
                elev_val = group['elev'].mean() if 'elev' in group.columns else (group['elevation'].mean() if 'elevation' in group.columns else 10.0)
                pop_val = group['pop'].mean() if 'pop' in group.columns else (group['population'].mean() if 'population' in group.columns else 0.0)
                med_doy = int(group['doy'].median()) if 'doy' in group.columns else 15
                
                row_dict = {
                    'ym': pd.Period(ym_str, freq='M'),
                    'temp': avg_temp,
                    'cld': avg_cld,
                    'u': avg_u,
                    'v': avg_v,
                    'pbl': avg_pbl,
                    'elev': elev_val or 10.0,
                    'pop': pop_val or 0.0,
                    'no2': avg_no2,
                    'day_of_year': med_doy,
                    'month': mth,
                    'year': yr,
                    'solar': 400.0
                }
                monthly_results.append(row_dict)
            return monthly_results
        except Exception as e:
            print(f"[HistoricalDataService] Failed to fetch monthly NO2 data from Hugging Face: {e}")
            return []
        finally:
            api.close()

    def build_comparison_data(self, lat, lon, predictor_fn):
        """
        Build the 5-row comparison table (H1M → H5Y) dynamically from GEE.
        """
        if self._pollutant == 'no2':
            print(f"[HistData-no2] Querying Hugging Face / DuckDB for ({lat}, {lon})...")
            try:
                monthly_data = self.get_monthly_no2_data(lat, lon)
            except Exception as e:
                print(f"[HistData-no2] Hugging Face Extractor failed: {e}")
                monthly_data = []
                
            if not monthly_data:
                print(f"[HistData-no2] Hugging Face / DuckDB returned no data. Falling back to Earth Engine.")
                try:
                    monthly_data = self.extractor.get_monthly_data(lat, lon, self._pollutant, AVAILABLE_YEARS)
                except Exception as e:
                    print(f"[HistData-no2] GEE Fallback Extractor failed: {e}")
                    return [self._empty_row(p[0], p[1]) for p in COMPARISON_PERIODS]
        else:
            print(f"[HistData-{self._pollutant}] Querying Earth Engine for ({lat}, {lon})...")
            try:
                monthly_data = self.extractor.get_monthly_data(lat, lon, self._pollutant, AVAILABLE_YEARS)
            except Exception as e:
                print(f"[HistData-{self._pollutant}] GEE Extractor failed: {e}")
                return [self._empty_row(p[0], p[1]) for p in COMPARISON_PERIODS]

        if not monthly_data:
            return [self._empty_row(p[0], p[1]) for p in COMPARISON_PERIODS]

        monthly_results = []
        for row in monthly_data:
            solar_val = float(row.get('solar', 400.0))
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
                predicted = predictor_fn(weather, lat, lon, doy, month, elev, pop)
            except Exception as e:
                print(f"[HistData-{self._pollutant}] Prediction failed: {e}")
                predicted = None

            val_col = self._pollutant
            observed = float(row.get(val_col, 0))

            if self._pollutant in ['so2', 'no2']:
                observed = observed * 1_000_000.0
                if predicted is None:
                    predicted = 0.0
            else:
                scale = 1000.0
                if predicted is None:
                    predicted = 0.0
                observed = observed * scale

            monthly_results.append({
                'ym': row['ym'],
                'date': row['ym'].to_timestamp().date(),
                'predicted': predicted,
                'observed': observed,
            })

        comparison = []
        for period_name, range_code, months_back in COMPARISON_PERIODS:
            cutoff_date = LATEST_DATA_DATE - datetime.timedelta(days=months_back * 30)
            in_period = [r for r in monthly_results if r['date'] >= cutoff_date and r['predicted'] is not None]

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
        Stub for getting specific day average. Currently unused or falls back to ODISHA_CLIMATE.
        """
        return None

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
# Module-level singletons
# ---------------------------------------------------------------------------
so2_history = HistoricalDataService('so2')
no2_history = HistoricalDataService('no2')
o3_history = HistoricalDataService('o3')
