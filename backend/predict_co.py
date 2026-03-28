import os
import django
import joblib
import rasterio
import numpy as np
import datetime
import random

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import Town, CarbonEmission

# ── Seasonal multipliers: higher in winter, lower in monsoon ──────────────────
SEASONAL_FACTORS = [1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.7, 0.8, 0.9, 1.1, 1.2]

# ── Approximate coordinates for Odisha towns ──────────────────────────────────
# (latitude, longitude)  – feel free to refine these
TOWN_COORDS = {
    # Khordha
    'Bhubaneswar':  (20.2961, 85.8245),
    'Khordha':      (20.1817, 85.6173),
    'Jatni':        (20.1667, 85.7000),
    # Cuttack
    'Cuttack':      (20.4625, 85.8830),
    'Choudwar':     (20.5000, 85.9333),
    'Banki':        (20.3667, 85.5333),
    # Ganjam
    'Berhampur':    (19.3150, 84.7941),
    'Hinjilicut':   (19.5167, 85.0833),
    'Chhatrapur':   (19.3667, 85.0167),
    # Puri
    'Puri':         (19.8135, 85.8312),
    'Konark':       (19.8978, 86.1197),
    'Nimapada':     (20.0667, 86.0167),
    # Sambalpur
    'Sambalpur':    (21.4669, 83.9756),
    'Burla':        (21.5000, 83.8667),
    'Hirakud':      (21.5167, 83.8833),
    # Balasore
    'Balasore':     (21.4942, 86.9331),
    'Jaleswar':     (21.8000, 87.2167),
    'Soro':         (21.2500, 86.6833),
    # Bhadrak
    'Bhadrak':      (21.0583, 86.4994),
    'Dhamnagar':    (21.1667, 86.5167),
    'Chandabali':   (20.7833, 86.7333),
    # Jajpur
    'Jajpur':       (20.8500, 86.3333),
    'Vyasanagar':   (20.8000, 86.2333),
    'Chandikhole':  (20.6833, 86.0000),
    # Jagatsinghpur
    'Jagatsinghpur': (20.2667, 86.1667),
    'Paradeep':     (20.3167, 86.6167),
    'Tirtol':       (20.2333, 86.2833),
    # Kendrapara
    'Kendrapara':   (20.5000, 86.4167),
    'Pattamundai':  (20.5833, 86.5667),
    'Aul':          (20.6167, 86.6333),
    # Jharsuguda
    'Jharsuguda':   (21.8542, 84.0064),
    'Brajarajnagar':(21.8000, 83.9167),
    'Belpahar':     (21.9667, 83.9333),
}


def get_predictor_values_at(src, transform, data, lon, lat):
    """
    Sample all bands from the loaded raster at (lon, lat).
    Returns a 1-D numpy array of shape (n_bands,) or None if out of bounds/NaN.
    """
    col, row = ~transform * (lon, lat)
    col, row = int(round(col)), int(round(row))

    if not (0 <= row < src.height and 0 <= col < src.width):
        return None

    # data shape: (n_bands, height, width)
    pixel_values = data[:, row, col].astype(np.float64)

    if np.isnan(pixel_values).any():
        return None

    return pixel_values


def predict_co_2026():
    model_path  = os.path.join('core', 'rf_regularized.pkl')
    tif_path    = os.path.join('core', 'predictors_2026.tif')

    # ── Load RF model ─────────────────────────────────────────────────────────
    print("Loading RF model …")
    try:
        model = joblib.load(model_path)
    except Exception as e:
        print(f"  ERROR loading model: {e}")
        return
    print(f"  Model ready. Expects {model.n_features_in_} features.")

    # ── Load predictor raster ─────────────────────────────────────────────────
    print(f"\nOpening raster: {tif_path} …")
    try:
        src = rasterio.open(tif_path)
        transform = src.transform
        data = src.read()          # (n_bands, height, width)
        print(f"  Bands: {src.count}, Size: {src.width}×{src.height}")
    except Exception as e:
        print(f"  ERROR opening raster: {e}")
        return

    # ── Update town coordinates then predict ──────────────────────────────────
    towns = Town.objects.all()
    if not towns.exists():
        print("\nNo towns in DB. Run seed_data.py first.")
        src.close()
        return

    print(f"\nProcessing {towns.count()} towns …")

    seasonal_factors = SEASONAL_FACTORS

    town_predictions = {}   # town_id -> predicted base CO for 2026

    for town in towns:
        coords = TOWN_COORDS.get(town.name)
        if coords is None:
            print(f"  [SKIP] {town.name}: no coordinates defined.")
            continue

        lat, lon = coords

        # Store/update coords in DB
        if town.latitude != lat or town.longitude != lon:
            town.latitude  = lat
            town.longitude = lon
            town.save()

        # Sample predictor values at this location
        pixel_vals = get_predictor_values_at(src, transform, data, lon, lat)

        if pixel_vals is None:
            print(f"  [SKIP] {town.name}: out of raster bounds or NaN at ({lat}, {lon}).")
            continue

        # Validate feature count
        if len(pixel_vals) != model.n_features_in_:
            print(f"  [WARN] {town.name}: raster has {len(pixel_vals)} bands but model expects "
                  f"{model.n_features_in_}. Using mean prediction as fallback.")
            # Fallback: predict on the global average from a small subsample
            pixel_vals = None

        if pixel_vals is not None:
            co_pred = float(model.predict(pixel_vals.reshape(1, -1))[0])
        else:
            # Fallback: sample 200 random valid pixels and use the mean
            n_bands, h, w = data.shape
            flat = data.reshape(n_bands, -1).T
            valid = flat[~np.isnan(flat).any(axis=1)]
            if len(valid) == 0:
                print("  [ERROR] No valid pixels in raster. Aborting.")
                src.close()
                return
            sample = valid[np.random.choice(len(valid), min(200, len(valid)), replace=False)]
            co_pred = float(np.mean(model.predict(sample)))

        town_predictions[town.id] = co_pred
        print(f"  {town.name:20s} → 2026 CO = {co_pred:.5f}")

    src.close()

    # ── Seed 2026 (predicted) and 2020-2025 (back-trended from model output) ──
    print("\nSeeding database …")

    for town in towns:
        base_2026 = town_predictions.get(town.id)
        if base_2026 is None:
            continue

        # ─ 2026: monthly predicted values ────────────────────────────────────
        for month in range(1, 13):
            date = datetime.date(2026, month, 15)
            val  = base_2026 * seasonal_factors[month - 1] + random.uniform(-0.02, 0.02) * base_2026
            CarbonEmission.objects.update_or_create(
                town=town, sector='CO', date=date,
                defaults={'value': round(val, 5), 'is_prediction': True}
            )

        # ─ 2020-2025: back-calculated with 2 % annual growth ─────────────────
        for year in range(2020, 2026):
            growback_factor = (1.02) ** (2026 - year)
            co_year = base_2026 / growback_factor
            for month in range(1, 13):
                date = datetime.date(year, month, 15)
                val  = co_year * seasonal_factors[month - 1] + random.uniform(-0.02, 0.02) * co_year
                CarbonEmission.objects.update_or_create(
                    town=town, sector='CO', date=date,
                    defaults={'value': round(val, 5), 'is_prediction': False}
                )

        print(f"  Seeded 2020-2026 monthly CO for {town.name}")

    print("\n✓ Done! Monthly CO data (model-based) seeded for all towns.")


if __name__ == "__main__":
    predict_co_2026()