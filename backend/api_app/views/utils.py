from weather_service import get_live_weather

# Odisha annual average weather (baseline the TIF was built against)
TOWN_COORDS = {
    # Khordha
    'Bhubaneswar':   (20.2961,  85.8245, 'Khordha', 1),
    'Khordha':       (20.1817,  85.6173, 'Khordha', 2),
    'Jatni':         (20.1667,  85.7000, 'Khordha', 3),
    # Cuttack
    'Cuttack':       (20.4625,  85.8830, 'Cuttack', 4),
    'Choudwar':      (20.5000,  85.9333, 'Cuttack', 5),
    'Banki':         (20.3667,  85.5333, 'Cuttack', 6),
    # Ganjam
    'Berhampur':     (19.3150,  84.7941, 'Ganjam', 7),
    'Hinjilicut':    (19.5167,  85.0833, 'Ganjam', 8),
    'Chhatrapur':    (19.3667,  85.0167, 'Ganjam', 9),
    # Puri
    'Puri':          (19.8135,  85.8312, 'Puri', 10),
    'Konark':        (19.8978,  86.1197, 'Puri', 11),
    'Nimapada':      (20.0667,  86.0167, 'Puri', 12),
    # Sambalpur
    'Sambalpur':     (21.4669,  83.9756, 'Sambalpur', 13),
    'Burla':         (21.5000,  83.8667, 'Sambalpur', 14),
    'Hirakud':       (21.5167,  83.8833, 'Sambalpur', 15),
    # Balasore
    'Balasore':      (21.4942,  86.9331, 'Balasore', 16),
    'Jaleswar':      (21.8000,  87.2167, 'Balasore', 17),
    'Soro':          (21.2500,  86.6833, 'Balasore', 18),
    # Bhadrak
    'Bhadrak':       (21.0583,  86.4994, 'Bhadrak', 19),
    'Dhamnagar':     (21.1667,  86.5167, 'Bhadrak', 20),
    'Chandabali':    (20.7833,  86.7333, 'Bhadrak', 21),
    # Jajpur
    'Jajpur':        (20.8500,  86.3333, 'Jajpur', 22),
    'Vyasanagar':    (20.8000,  86.2333, 'Jajpur', 23),
    'Chandikhole':   (20.6833,  86.0000, 'Jajpur', 24),
    # Jagatsinghpur
    'Jagatsinghpur': (20.2667,  86.1667, 'Jagatsinghpur', 25),
    'Paradeep':      (20.3167,  86.6167, 'Jagatsinghpur', 26),
    'Tirtol':        (20.2333,  86.2833, 'Jagatsinghpur', 27),
    # Kendrapara
    'Kendrapara':    (20.5000,  86.4167, 'Kendrapara', 28),
    'Pattamundai':   (20.5833,  86.5667, 'Kendrapara', 29),
    'Aul':           (20.6167,  86.6333, 'Kendrapara', 30),
    # Jharsuguda
    'Jharsuguda':    (21.8542,  84.0064, 'Jharsuguda', 31),
    'Brajarajnagar': (21.8000,  83.9167, 'Jharsuguda', 32),
    'Belpahar':      (21.9667,  83.9333, 'Jharsuguda', 33),
}

def format_prediction_response(result, extra_info=None, coords=None):
    """Formats predictor output into a unified API response."""
    resp = {
        'base_value_2026': result.get('base_value_2026'),
        'timeline':        result.get('timeline', []),
        'range':           result.get('range', '1Y'),
        'pollutant':       result.get('pollutant', 'unknown'),
    }
    if 'comparison_table' in result:
        resp['comparison_table'] = result['comparison_table']
        
    if extra_info:
        resp.update(extra_info)
    # Attach live weather snapshot for the predicted location
    if coords:
        try:
            resp['weather_snapshot'] = get_live_weather(coords[0], coords[1])
            resp['weather_synced'] = True
        except Exception:
            resp['weather_snapshot'] = None
            resp['weather_synced'] = False
    return resp


VALID_RANGES = {'1D', '1W', '1M', '3M', '6M', '1Y', 'H1M', 'H3M', 'H1Y', 'H3Y', 'H5Y'}

def _get_range(request):
    """Extract and validate the range query parameter."""
    r = request.query_params.get('range', '1Y').upper()
    return r if r in VALID_RANGES else '1Y'


def _get_overrides(request):
    """Extract potential 'What-If' parameter overrides from query params."""
    overrides = {}
    params = [
        'temp', 'cld', 'wind_speed', 'wind_dir', 'pbl', 'pop', 'elev', 
        'urban', 'night', 'dewpoint', 'pressure', 'solar', 'aai'
    ]
    for p in params:
        val = request.query_params.get(p)
        if val:
            try:
                overrides[p] = float(val)
            except ValueError:
                pass
    return overrides if overrides else None
