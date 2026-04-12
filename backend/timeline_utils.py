"""
timeline_utils.py
=================
Shared timeline/range logic for all pollutant predictors.
Generates data points for 1D, 1W, 1M, 3M, 6M, 1Y time ranges.
"""

import datetime
import math

YEAR = 2026


def generate_timeline_points(range_str):
    """
    Generate a list of dicts for the given range.
    Each dict: { 'day_of_year', 'month', 'date', 'label' }

    Ranges:
      1D  → 1 point  (today)
      1W  → 7 points (daily, next 7 days from today)
      1M  → ~30 points (daily, next 30 days)
      3M  → ~13 points (weekly, next 3 months)
      6M  → ~26 points (weekly, next 6 months)
      1Y  → 12 points (monthly, Jan-Dec)
    """
    today = datetime.date.today()
    if today.year != YEAR:
        today = datetime.date(YEAR, 4, 12)

    points = []

    if range_str == '1D':
        _add_point(points, today)

    elif range_str == '1W':
        for i in range(7):
            d = today + datetime.timedelta(days=i)
            if d.year == YEAR:
                _add_point(points, d)

    elif range_str == '1M':
        for i in range(30):
            d = today + datetime.timedelta(days=i)
            if d.year == YEAR:
                _add_point(points, d)

    elif range_str == '3M':
        for i in range(0, 91, 7):
            d = today + datetime.timedelta(days=i)
            if d.year == YEAR:
                _add_point(points, d)

    elif range_str == '6M':
        for i in range(0, 181, 7):
            d = today + datetime.timedelta(days=i)
            if d.year == YEAR:
                _add_point(points, d)

    elif range_str == '1Y':
        for month in range(1, 13):
            d = datetime.date(YEAR, month, 15)
            _add_point(points, d)

    else:
        return generate_timeline_points('1Y')

    return points


def _add_point(points, d):
    doy = d.timetuple().tm_yday
    points.append({
        'day_of_year': doy,
        'month':       d.month,
        'date':        d.isoformat(),
        'label':       d.strftime('%b %d') if d.day != 15 else d.strftime('%b %Y'),
        'year':        d.year,
    })


def day_sin(doy):
    return math.sin(2 * math.pi * doy / 365)


def day_cos(doy):
    return math.cos(2 * math.pi * doy / 365)
