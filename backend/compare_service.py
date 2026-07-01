"""
compare_service.py
==================
Historical comparison between GEE satellite observations and ML predictions.

Architecture:
  - GEE: uses reduceRegion (one scalar per month) — never getRegion to avoid MLE.
  - ML: calls the public predict_at_coords('1Y') API on each predictor, then
        groups the returned timeline by month. This correctly handles all
        predictors (SO2/NO2/O3 use _build_features; CO uses _perturb_for_month).

GEE failure handling:
  - Any EE error returns gee_actual=None for that month (not the safe limit).
  - The chart uses connectNulls=false so gaps appear cleanly.
"""

import math
import calendar
import datetime
from functools import lru_cache

try:
    import ee
except ImportError:
    ee = None

# ─── Config ─────────────────────────────────────────────────────────────────

GEE_COLLECTIONS = {
    'no2': {'collection': 'COPERNICUS/S5P/OFFL/L3_NO2', 'band': 'NO2_column_number_density'},
    'so2': {'collection': 'COPERNICUS/S5P/OFFL/L3_SO2', 'band': 'SO2_column_number_density'},
    'o3':  {'collection': 'COPERNICUS/S5P/OFFL/L3_O3',  'band': 'O3_column_number_density'},
    'co':  {'collection': 'COPERNICUS/S5P/OFFL/L3_CO',  'band': 'CO_column_number_density'},
}

POLLUTANT_CONFIG = {
    'no2': {'who_limit': 40.0,  'unit': 'µg/m³', 'multiplier': 1_000_000.0, 'molar_mass': 46.01},
    'so2': {'who_limit': 40.0,  'unit': 'µg/m³', 'multiplier': 1_000_000.0, 'molar_mass': 64.07},
    'o3':  {'who_limit': 100.0, 'unit': 'µg/m³', 'multiplier': 1_000.0,     'molar_mass': 48.00},
    'co':  {'who_limit': 4.0,   'unit': 'mg/m³', 'multiplier': 1_000.0,     'molar_mass': 28.01},
    'pm25': {'who_limit': 15.0, 'unit': 'µg/m³', 'multiplier': 1.0,        'molar_mass': 1000.0},
}

MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


# ─── Unit Conversion ─────────────────────────────────────────────────────────

def convert_gee_value(raw_val, pollutant):
    """Convert raw mol/m² GEE value to µg/m³ or mg/m³."""
    if raw_val is None:
        return None
    cfg = POLLUTANT_CONFIG[pollutant]
    converted = raw_val * cfg['multiplier'] * cfg['molar_mass'] / 1000.0
    return round(float(converted), 8)


# ─── Statistics ──────────────────────────────────────────────────────────────

def compute_stats(data_list):
    pairs = [
        (d['gee_actual'], d['ml_prediction'])
        for d in data_list
        if d.get('gee_actual') is not None and d.get('ml_prediction') is not None
    ]
    if len(pairs) < 2:
        return None

    n = len(pairs)
    avg_actual     = sum(a for a, p in pairs) / n
    avg_prediction = sum(p for a, p in pairs) / n
    avg_difference = avg_actual - avg_prediction
    pct_difference = abs(avg_difference / avg_actual) * 100 if avg_actual != 0 else 0
    mae  = sum(abs(a - p) for a, p in pairs) / n
    rmse = math.sqrt(sum((a - p) ** 2 for a, p in pairs) / n)

    sum_x  = sum(a for a, p in pairs)
    sum_y  = sum(p for a, p in pairs)
    sum_xy = sum(a * p for a, p in pairs)
    sum_x2 = sum(a ** 2 for a, p in pairs)
    sum_y2 = sum(p ** 2 for a, p in pairs)
    denom  = math.sqrt(
        max(0, n * sum_x2 - sum_x ** 2) * max(0, n * sum_y2 - sum_y ** 2)
    )
    correlation = (n * sum_xy - sum_x * sum_y) / denom if denom != 0 else 0

    return {
        'avg_actual':     round(avg_actual, 4),
        'avg_prediction': round(avg_prediction, 4),
        'avg_difference': round(avg_difference, 4),
        'pct_difference': round(pct_difference, 4),
        'mae':            round(mae, 4),
        'rmse':           round(rmse, 4),
        'correlation':    round(correlation, 4),
        'r_squared':      round(correlation ** 2, 4),
    }


# ─── Predictor accessor ──────────────────────────────────────────────────────

def _get_predictor(pollutant):
    if pollutant == 'no2':
        from predictor.no2_predictor import no2_predictor
        return no2_predictor
    elif pollutant == 'so2':
        from predictor.so2_predictor import so2_predictor
        return so2_predictor
    elif pollutant == 'o3':
        from predictor.o3_predictor import o3_predictor
        return o3_predictor
    elif pollutant == 'pm25':
        from predictor.pm25_predictor import pm25_predictor
        return pm25_predictor
    else:
        from predictor.co_predictor import co_predictor
        return co_predictor


# ─── ML Monthly Predictions (via public API) ─────────────────────────────────

def get_ml_monthly(lat, lon, pollutant, year):
    """
    Returns a dict {month: value} for the given year.

    Uses predict_at_coords('1Y') which is the tested public API for ALL
    predictors (including CO which has its own internal logic).
    Then groups the returned timeline by month and averages them.
    """
    pred = _get_predictor(pollutant)
    result = pred.predict_at_coords(lat, lon, range_str='1Y')

    if result.get('error'):
        print(f"[CompareService] ML predictor error for {pollutant}: {result['error']}")
        return {m: None for m in range(1, 13)}

    timeline = result.get('timeline', [])

    # Group by month → average (some pollutants emit multiple points/month)
    month_totals = {m: [] for m in range(1, 13)}
    for pt in timeline:
        m = pt.get('month')
        v = pt.get('value')
        if m and v is not None:
            month_totals[m].append(v)

    return {
        m: (round(sum(vals) / len(vals), 8) if vals else None)
        for m, vals in month_totals.items()
    }


# ─── GEE Monthly Actuals ─────────────────────────────────────────────────────

@lru_cache(maxsize=128)
def _fetch_gee_monthly_cached(lat_r, lon_r, pollutant, year):
    """
    Batched GEE query for all 12 months in a single Earth Engine map call.
    Cached locally using rounded coordinates to avoid redundant network overhead.
    """
    if ee is None:
        return {m: None for m in range(1, 13)}

    config = GEE_COLLECTIONS.get(pollutant)
    if not config:
        return {m: None for m in range(1, 13)}

    try:
        point = ee.Geometry.Point(lon_r, lat_r)
        collection = (
            ee.ImageCollection(config['collection'])
              .filterBounds(point)
              .select(config['band'])
        )

        # We pass a list of 12 dates into Earth Engine
        starts = [f"{year}-{m:02d}-01" for m in range(1, 13)]
        ee_starts = ee.List(starts)

        def compute_month(start_date):
            start = ee.Date(start_date)
            end = start.advance(1, 'month')
            monthly_col = collection.filterDate(start, end)
            
            mean_img = monthly_col.mean()
            val_dict = mean_img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=11132,
                maxPixels=1
            )
            val = val_dict.get(config['band'])
            # Return a sentinal value (-9999) if null since EE maps can't easily handle mixed types
            return ee.Algorithms.If(ee.Algorithms.IsEqual(val, None), -9999, val)

        # Single network call to execute the entire year!
        results_list = ee_starts.map(compute_month).getInfo()
        
        results = {}
        for m, val in enumerate(results_list, start=1):
            if val == -9999 or val <= 0:
                results[m] = None
            else:
                results[m] = val
        return results

    except Exception as e:
        print(f"[CompareService] GEE Batch {pollutant} {year} failed: {e}")
        return {m: None for m in range(1, 13)}

def get_gee_monthly(lat, lon, pollutant, year):
    api = None
    if pollutant == 'no2':
        from extractor_service import no2_api as api
    elif pollutant == 'pm25':
        from extractor_service import pm25_api as api
    elif pollutant == 'o3':
        from extractor_service import o3_api as api
    elif pollutant == 'co':
        from extractor_service import co_api as api
    elif pollutant == 'so2':
        from extractor_service import so2_api as api

    if api is not None:
        try:
            df = api.get_data_for_coordinate(lat, lon, year)
            if not df.empty:
                import pandas as pd
                print(f"[CompareService DEBUG] {pollutant.upper()} HF data columns: {list(df.columns)}")
                if len(df) > 0:
                    print(f"[CompareService DEBUG] {pollutant.upper()} HF data sample row: {df.iloc[0].to_dict()}")
                df['parsed_date'] = pd.to_datetime(df['date'] if 'date' in df.columns else df['parsed_date'])
                df['month'] = df['parsed_date'].dt.month
                val_col = f"{pollutant}_level" if f"{pollutant}_level" in df.columns else pollutant
                if len(df) > 0:
                    print(f"[CompareService DEBUG] Using {pollutant.upper()} column: '{val_col}', "
                          f"sample value: {df[val_col].iloc[0]}, mean: {df[val_col].mean():.10f}")
                monthly_avg = df.groupby('month')[val_col].mean().to_dict()
                print(f"[CompareService DEBUG] {pollutant.upper()} HF monthly avg (source=HuggingFace): {monthly_avg}")
                return {m: monthly_avg.get(m, None) for m in range(1, 13)}
            else:
                print(f"[CompareService DEBUG] {pollutant.upper()} HF returned empty DataFrame, falling back to GEE.")
        except Exception as e:
            print(f"[CompareService] {pollutant.upper()} Hugging Face monthly extraction failed: {e}")

    # Use rounded coordinates for stable caching
    return _fetch_gee_monthly_cached(round(lat, 4), round(lon, 4), pollutant, year)



# ─── GEE for arbitrary date windows (weekly / daily) ─────────────────────────

def get_gee_for_dates(lat, lon, pollutant, dates, window_days=1):
    """
    Returns list of {date_str, gee_actual_raw} — one entry per date.
    Performs server-side batching using ee.List.map to avoid looping getInfo().
    """
    api = None
    if pollutant == 'no2':
        from extractor_service import no2_api as api
    elif pollutant == 'pm25':
        from extractor_service import pm25_api as api
    elif pollutant == 'o3':
        from extractor_service import o3_api as api
    elif pollutant == 'co':
        from extractor_service import co_api as api
    elif pollutant == 'so2':
        from extractor_service import so2_api as api

    if api is not None and dates:
        years = list(set(d.year for d in dates))
        try:
            results = []
            year_query = years[0] if len(years) == 1 else "*"
            df = api.get_data_for_coordinate(lat, lon, year_query)
            if not df.empty:
                import pandas as pd
                df['parsed_date'] = pd.to_datetime(df['date'] if 'date' in df.columns else df['parsed_date']).dt.date
                val_col = f"{pollutant}_level" if f"{pollutant}_level" in df.columns else pollutant
                daily_avg = df.groupby('parsed_date')[val_col].mean().to_dict()
                
                for d in dates:
                    val = daily_avg.get(d, None)
                    if val is None and window_days > 1:
                        window_vals = [
                            daily_avg[date_key] for date_key in daily_avg
                            if d <= date_key < (d + datetime.timedelta(days=window_days))
                        ]
                        if window_vals:
                            val = sum(window_vals) / len(window_vals)
                    results.append({'date_str': d.isoformat(), 'gee_actual_raw': val})
                return results
        except Exception as e:
            print(f"[CompareService] {pollutant.upper()} Hugging Face date extraction failed: {e}")

    if ee is None:
        return [{'date_str': d.isoformat(), 'gee_actual_raw': None} for d in dates]

    config = GEE_COLLECTIONS.get(pollutant)
    if not config:
        return [{'date_str': d.isoformat(), 'gee_actual_raw': None} for d in dates]

    try:
        point = ee.Geometry.Point(lon, lat)
        collection = (
            ee.ImageCollection(config['collection'])
              .filterBounds(point)
              .select(config['band'])
        )

        date_strs = [d.isoformat() for d in dates]
        ee_starts = ee.List(date_strs)
        ee_window = ee.Number(window_days)

        def compute_window(start_date):
            start = ee.Date(start_date)
            end = start.advance(ee_window, 'day')
            window_col = collection.filterDate(start, end)
            
            mean_img = window_col.mean()
            val_dict = mean_img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=11132,
                maxPixels=1
            )
            val = val_dict.get(config['band'])
            return ee.Algorithms.If(ee.Algorithms.IsEqual(val, None), -9999, val)

        results_list = ee_starts.map(compute_window).getInfo()

        results = []
        for i, val in enumerate(results_list):
            if val == -9999 or val <= 0:
                results.append({'date_str': date_strs[i], 'gee_actual_raw': None})
            else:
                results.append({'date_str': date_strs[i], 'gee_actual_raw': val})
        return results

    except Exception as e:
        print(f"[CompareService] GEE Window Batch {pollutant} failed: {e}")
        return [{'date_str': d.isoformat(), 'gee_actual_raw': None} for d in dates]


# ─── ML for arbitrary dates (weekly / daily) ─────────────────────────────────

def get_ml_for_dates(lat, lon, pollutant, year, dates):
    """
    Returns list of {date_str, ml_prediction}.
    Uses predict_at_coords('1Y') and matches by month (or closest date).
    """
    pred    = _get_predictor(pollutant)
    result  = pred.predict_at_coords(lat, lon, range_str='1Y')

    if result.get('error'):
        return [{'date_str': d.isoformat(), 'ml_prediction': None} for d in dates]

    timeline = result.get('timeline', [])

    # Build month→avg lookup
    month_totals = {m: [] for m in range(1, 13)}
    for pt in timeline:
        m = pt.get('month')
        v = pt.get('value')
        if m and v is not None:
            month_totals[m].append(v)

    month_avg = {
        m: (round(sum(vals) / len(vals), 8) if vals else None)
        for m, vals in month_totals.items()
    }

    return [
        {'date_str': d.isoformat(), 'ml_prediction': month_avg.get(d.month)}
        for d in dates
    ]


# ─── Pagination helpers ───────────────────────────────────────────────────────

def get_weeks_for_page(year, page):
    start_month = (page - 1) * 3 + 1
    end_month   = min(start_month + 2, 12)
    dates = []
    for m in range(start_month, end_month + 1):
        for w in range(4):
            d = datetime.date(year, m, 1) + datetime.timedelta(weeks=w)
            if d.month == m:
                dates.append(d)
    return dates


def get_days_for_page(year, month, page):
    start_day = (page - 1) * 15 + 1
    end_day   = min(start_day + 14, calendar.monthrange(year, month)[1])
    return [datetime.date(year, month, d) for d in range(start_day, end_day + 1)]


HF_AVAILABLE_YEARS = {
    "no2": [2020, 2021, 2022, 2023],
    "o3": [2023, 2024, 2025],
    "so2": [2024, 2025],
    "co": [2022, 2023, 2024, 2025],
    "pm25": [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
}

POLLUTANT_DISPLAY_NAMES = {
    "no2": "NO₂",
    "o3": "O₃",
    "so2": "SO₂",
    "co": "CO",
    "pm25": "PM₂.₅"
}


# ─── Main orchestrator ───────────────────────────────────────────────────────

def get_comparison_data(lat, lon, pollutant, year_str, mode='monthly', page=1, month=1):
    if pollutant not in POLLUTANT_CONFIG:
        return {'error': f'Unsupported pollutant: {pollutant}'}

    cfg = POLLUTANT_CONFIG[pollutant]

    # "All" mode — ML only, no GEE
    if year_str == 'all':
        return _get_all_years_data(lat, lon, pollutant, cfg)

    year           = int(year_str)
    if pollutant in HF_AVAILABLE_YEARS and year not in HF_AVAILABLE_YEARS[pollutant]:
        years = HF_AVAILABLE_YEARS[pollutant]
        display_name = POLLUTANT_DISPLAY_NAMES.get(pollutant, pollutant.upper())
        return {
            'available': False,
            'message': f'Historical {display_name} observations are available from {min(years)} to {max(years)} only.'
        }

    is_current_year = (year == datetime.date.today().year)
    fetch_gee      = not is_current_year
    message        = ("Historical GEE observations are not yet available for the current year. "
                      "Showing ML prediction only.") if is_current_year else None

    total_pages = 1
    response_data = []

    if mode == 'monthly':
        gee_raw = get_gee_monthly(lat, lon, pollutant, year) if fetch_gee else {m: None for m in range(1, 13)}
        ml_map  = get_ml_monthly(lat, lon, pollutant, year)

        # Debug: log raw values for first available month
        for dbg_m in range(1, 13):
            if gee_raw.get(dbg_m) is not None and ml_map.get(dbg_m) is not None:
                print(f"[CompareService DEBUG] {pollutant} month={dbg_m}: "
                      f"GEE_raw={gee_raw[dbg_m]:.10f}, ML_raw={ml_map[dbg_m]:.10f}, "
                      f"ratio={gee_raw[dbg_m]/ml_map[dbg_m]:.4f}")
                break

        for m in range(1, 13):
            raw      = gee_raw.get(m)
            gee_val  = convert_gee_value(raw, pollutant) if raw is not None else None
            ml_raw   = ml_map.get(m)
            # ML predictions are in the same raw unit as GEE satellite data
            # (both use mol/m² for Sentinel-5P bands), so apply same conversion
            ml_val   = convert_gee_value(ml_raw, pollutant) if ml_raw is not None else None
            response_data.append({
                'label':         f"{MONTH_NAMES[m-1]} {year}",
                'date':          f"{year}-{m:02d}-15",
                'gee_actual':    gee_val,   # None means gap in chart
                'ml_prediction': ml_val,
                'has_gee':       gee_val is not None,
            })

    elif mode == 'weekly':
        total_pages = 4
        dates       = get_weeks_for_page(year, page)
        gee_list    = get_gee_for_dates(lat, lon, pollutant, dates, window_days=7) if fetch_gee else [{'date_str': d.isoformat(), 'gee_actual_raw': None} for d in dates]
        ml_list     = get_ml_for_dates(lat, lon, pollutant, year, dates)

        for i, d in enumerate(dates):
            raw     = gee_list[i]['gee_actual_raw']
            gee_val = convert_gee_value(raw, pollutant) if raw is not None else None
            ml_raw  = ml_list[i]['ml_prediction']
            ml_val  = convert_gee_value(ml_raw, pollutant) if ml_raw is not None else None
            response_data.append({
                'label':         f"Week of {d.strftime('%b %d')}",
                'date':          d.isoformat(),
                'gee_actual':    gee_val,
                'ml_prediction': ml_val,
                'has_gee':       gee_val is not None,
            })

    elif mode == 'daily':
        days_in_month = calendar.monthrange(year, month)[1]
        total_pages   = math.ceil(days_in_month / 15)
        dates         = get_days_for_page(year, month, page)
        gee_list      = get_gee_for_dates(lat, lon, pollutant, dates, window_days=1) if fetch_gee else [{'date_str': d.isoformat(), 'gee_actual_raw': None} for d in dates]
        ml_list       = get_ml_for_dates(lat, lon, pollutant, year, dates)

        for i, d in enumerate(dates):
            raw     = gee_list[i]['gee_actual_raw']
            gee_val = convert_gee_value(raw, pollutant) if raw is not None else None
            ml_raw  = ml_list[i]['ml_prediction']
            ml_val  = convert_gee_value(ml_raw, pollutant) if ml_raw is not None else None
            response_data.append({
                'label':         d.strftime('%b %d'),
                'date':          d.isoformat(),
                'gee_actual':    gee_val,
                'ml_prediction': ml_val,
                'has_gee':       gee_val is not None,
            })
    else:
        return {'error': f'Unknown mode: {mode}'}

    stats = compute_stats(response_data) if fetch_gee else None

    return {
        'pollutant':        pollutant,
        'year':             year,
        'mode':             mode,
        'page':             page,
        'is_current_year':  is_current_year,
        'data':             response_data,
        'safe_limit':       cfg['who_limit'],
        'unit':             cfg['unit'],
        'stats':            stats,
        'pagination': {
            'current_page': page,
            'total_pages':  total_pages,
            'has_next':     page < total_pages,
            'has_prev':     page > 1,
        },
        'message': message,
    }


def _get_all_years_data(lat, lon, pollutant, cfg):
    """All-time view: ML-only yearly averages from 2020 to current year."""
    pred           = _get_predictor(pollutant)
    result         = pred.predict_at_coords(lat, lon, range_str='1Y')
    timeline       = result.get('timeline', []) if not result.get('error') else []

    # Build a single month-avg from the 1Y prediction (reused across years)
    month_totals = {m: [] for m in range(1, 13)}
    for pt in timeline:
        m = pt.get('month')
        v = pt.get('value')
        if m and v is not None:
            month_totals[m].append(v)
    annual_avg = sum(
        sum(vals) / len(vals) for vals in month_totals.values() if vals
    ) / max(1, sum(1 for vals in month_totals.values() if vals))

    current_year = datetime.date.today().year
    response_data = []
    for year in range(2020, current_year + 1):
        response_data.append({
            'label':         str(year),
            'date':          f"{year}-06-15",
            'gee_actual':    None,
            'ml_prediction': convert_gee_value(annual_avg, pollutant) if annual_avg else None,
            'has_gee':       False,
        })

    return {
        'pollutant':        pollutant,
        'year':             'all',
        'mode':             'yearly',
        'page':             1,
        'is_current_year':  False,
        'data':             response_data,
        'safe_limit':       cfg['who_limit'],
        'unit':             cfg['unit'],
        'stats':            None,
        'pagination': {
            'current_page': 1,
            'total_pages':  1,
            'has_next':     False,
            'has_prev':     False,
        },
        'message': 'All-time mode shows ML predictions only.',
    }
