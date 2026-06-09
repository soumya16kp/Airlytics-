import requests
import datetime
import math
from functools import lru_cache

# Caching to prevent hitting API limits
@lru_cache(maxsize=128)
def _cached_forecast_api(lat, lon, date_str):
    """Internal helper to cache API responses for 128 unique (location, day) pairs."""
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
        resp = requests.get(url, params=params, timeout=5) # Increased to 5s for stability
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[weather_service] API call failed for {lat},{lon} on {date_str}: {e}")
        return None

# ── Odisha monthly climate averages ──────────────────────────────────────────
# ... (keeping ODISHA_CLIMATE as is) ...
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
    vals = ODISHA_CLIMATE[max(1, min(12, month))]
    return dict(zip(_KEYS, vals))

def get_live_weather(lat, lon, timeout=3):
    """Quick snapshot for today's weather."""
    # Round coords to 2 decimals to increase cache hits
    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    data = _cached_forecast_api(round(lat, 2), round(lon, 2), date_str)
    
    if data:
        # Map the current hour from forecast to "live"
        hour = datetime.datetime.now().hour
        h = data.get('hourly', {})
        if h and 'temperature_2m' in h:
            return {
                'temp':       h['temperature_2m'][hour],
                'cld':        h['cloud_cover'][hour],
                'solar':      h['shortwave_radiation'][hour],
                'wind_speed': h['wind_speed_10m'][hour],
                'dewpoint':   18.0,
                'pressure':   1010.0,
                'wind_dir':   h['wind_direction_10m'][hour],
                'pbl':        h['boundary_layer_height'][hour],
            }
    
    # Fallback if no cache/api
    return get_climate_for_month(datetime.datetime.now().month)

def get_forecast_weather(lat, lon, date_str, timeout=5, hour=None):
    """Fetch daily aggregated hourly forecast or a specific hour."""
    data = _cached_forecast_api(round(lat, 2), round(lon, 2), date_str)
    if not data: return None
    
    h = data.get('hourly', {})
    if not h or not h.get('temperature_2m'): return None
    
    if hour is not None and 0 <= hour < len(h.get('temperature_2m', [])):
        return {
            'temp': h['temperature_2m'][hour],
            'cld': h['cloud_cover'][hour],
            'solar': h['shortwave_radiation'][hour],
            'wind_speed': h['wind_speed_10m'][hour],
            'wind_dir': h['wind_direction_10m'][hour],
            'pbl': max(100.0, h['boundary_layer_height'][hour]),
            'dewpoint': 18.0,
            'pressure': 1010.0,
        }

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
        'pbl': max(100.0, mean_val('boundary_layer_height')),
        'dewpoint': 18.0,
        'pressure': 1010.0,
    }

def get_weather_for_day(lat, lon, day_of_year, year=2026, pollutant=None, hour=None):
    today = datetime.datetime.now()
    try:
        target = datetime.datetime(year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
    except ValueError:
        target = today + datetime.timedelta(days=day_of_year - today.timetuple().tm_yday)
        
    delta_days = (target - today).days
    date_str = target.strftime('%Y-%m-%d')

    # 1. Forecast range (near future or recent past)
    if -2 <= delta_days <= 14:
        w = get_forecast_weather(lat, lon, date_str, hour=hour)
        if w: return w

    # 2. Pixel-specific Historical Average (far future or API failure)
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
    try:
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        elev = data.get('elevation', [100.0])
        return float(elev[0]) if isinstance(elev, list) else float(elev)
    except Exception:
        return 100.0
