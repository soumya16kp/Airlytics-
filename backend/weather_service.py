"""
weather_service.py
==================
Fetches live weather data from Open-Meteo API for O3/SO2/CO predictors.
Falls back to Odisha monthly climate averages when API is unavailable.
"""

import requests
import datetime
import math

# ── Odisha monthly climate averages ──────────────────────────────────────────
# (temp_C, cloud_%, solar_W/m2, wind_speed_m/s, dewpoint_C, pressure_hPa, wind_dir_deg, pbl_m)
ODISHA_CLIMATE = {
    1:  (22.0, 15, 450, 2.5, 12.0, 1015, 330, 800),
    2:  (25.0, 12, 500, 2.8, 13.0, 1013, 340, 900),
    3:  (29.0, 15, 550, 3.2, 16.0, 1010, 200, 1100),
    4:  (33.0, 20, 580, 4.0, 21.0, 1007, 210, 1300),
    5:  (34.0, 30, 540, 4.5, 24.0, 1004, 220, 1400),
    6:  (31.0, 65, 380, 5.5, 25.0, 1000, 230, 1200),
    7:  (29.0, 80, 280, 5.0, 25.5, 998,  240, 1000),
    8:  (28.0, 82, 270, 4.8, 25.0, 999,  230, 950),
    9:  (29.0, 70, 350, 3.5, 24.0, 1003, 200, 1050),
    10: (28.0, 40, 420, 2.5, 21.0, 1008, 350, 900),
    11: (25.0, 20, 430, 2.0, 16.0, 1013, 340, 800),
    12: (21.0, 15, 400, 2.2, 11.0, 1016, 330, 750),
}

_KEYS = ('temp', 'cld', 'solar', 'wind_speed', 'dewpoint', 'pressure', 'wind_dir', 'pbl')


def get_climate_for_month(month):
    """Return Odisha climate averages for a given month (1-12)."""
    vals = ODISHA_CLIMATE[max(1, min(12, month))]
    return dict(zip(_KEYS, vals))


def get_live_weather(lat, lon, timeout=3):
    """
    Fetch current weather from Open-Meteo API.
    Returns dict with temp, cld, solar, wind_speed, dewpoint, pressure, wind_dir, pbl.
    Falls back to climate averages on failure.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,cloud_cover,shortwave_radiation,"
        f"wind_speed_10m,wind_direction_10m,dewpoint_2m,surface_pressure"
    )

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        curr = data['current']
        return {
            'temp':       curr.get('temperature_2m', 30.0),
            'cld':        curr.get('cloud_cover', 20.0),
            'solar':      curr.get('shortwave_radiation', 400.0),
            'wind_speed': curr.get('wind_speed_10m', 3.0),
            'dewpoint':   curr.get('dewpoint_2m', 18.0),
            'pressure':   curr.get('surface_pressure', 1010.0),
            'wind_dir':   curr.get('wind_direction_10m', 200.0),
            'pbl':        1000.0,   # Not available from Open-Meteo basic
        }
    except Exception as e:
        print(f"[weather_service] Open-Meteo API failed: {e}, using climate fallback")
        month = datetime.datetime.now().month
        return get_climate_for_month(month)


def get_forecast_weather(lat, lon, date_str, timeout=3):
    """Fetch daily aggregated hourly forecast including PBL boundary_layer_height."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,cloud_cover,wind_speed_10m,wind_direction_10m,shortwave_radiation,boundary_layer_height",
        "timezone": "auto"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        h = data.get('hourly', {})
        if not h or not h.get('temperature_2m'): return None
        
        # Average the hourly values to get a daily mean
        def mean_val(key):
            vals = [v for v in h.get(key, []) if v is not None]
            return sum(vals) / len(vals) if vals else 0.0
            
        return {
            'temp': mean_val('temperature_2m'),
            'cld': mean_val('cloud_cover'),
            'solar': mean_val('shortwave_radiation'),
            'wind_speed': mean_val('wind_speed_10m'),
            'wind_dir': mean_val('wind_direction_10m'),
            'pbl': max(100.0, mean_val('boundary_layer_height')), # Prevent zero PBL
            'dewpoint': 18.0,
            'pressure': 1010.0,
        }
    except Exception as e:
        print(f"[weather_service] Open-Meteo forecast failed for {date_str}: {e}")
        return None


def get_weather_for_day(lat, lon, day_of_year, year=2026, pollutant=None):
    """
    Get weather data for a specific day of the year.
    - Path 1: For dates within ±14 days of today: uses Open-Meteo Forecast API.
    - Path 2: For future dates (>14 days), if pollutant is so2/o3:
              uses pixel-specific average from 5-year CSV historical data.
    - Path 3: Fallback: uses monthly climate averages for target month.
    """
    today = datetime.datetime.now()
    try:
        target = datetime.datetime(year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
    except ValueError: # handle leap years edge cases gracefully
        target = today + datetime.timedelta(days=day_of_year - today.timetuple().tm_yday)
        
    delta_days = (target - today).days

    # 1. Forecast range (near future or recent past)
    if -2 <= delta_days <= 14:
        w = get_forecast_weather(lat, lon, target.strftime('%Y-%m-%d'))
        if w: return w
        
        # If forecast fails, fallback to get_live_weather for today
        if abs(delta_days) <= 1:
            return get_live_weather(lat, lon)

    # 2. Pixel-specific Historical Average (far future)
    if pollutant in ['so2', 'o3']:
        try:
            from historical_data_service import so2_history, o3_history
            service = so2_history if pollutant == 'so2' else o3_history
            hist_avg = service.get_pixel_historical_avg(lat, lon, day_of_year)
            if hist_avg: return hist_avg
        except Exception as e:
            print(f"[weather_service] Historical avg fallback failed: {e}")

    # 3. Fallback to climate averages
    return get_climate_for_month(target.month)


def get_elevation(lat, lon, timeout=3):
    """Fetch elevation from Open-Meteo. Returns metres, fallback 100m."""
    try:
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        elev = data.get('elevation', [100.0])
        return float(elev[0]) if isinstance(elev, list) else float(elev)
    except Exception:
        return 100.0   # Odisha average plains elevation
