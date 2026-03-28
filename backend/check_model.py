import joblib
import rasterio
import os
import numpy as np

model_path = os.path.join('core', 'rf_regularized.pkl')
tif_path = os.path.join('core', 'predictors_2026.tif')

print(f"Loading model...")
model = joblib.load(model_path)
print(f"Model loaded. Features: {model.n_features_in_ if hasattr(model, 'n_features_in_') else 'unknown'}")

with rasterio.open(tif_path) as src:
    print(f"TIF Bands: {src.count}")
    print(f"TIF Metadata: {src.meta}")
