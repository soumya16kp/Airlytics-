import rasterio
import os

tif_path = os.path.join('core', 'predictors_2026.tif')
try:
    with rasterio.open(tif_path) as src:
        print(f"CRS: {src.crs}")
        print(f"Bounds: {src.bounds}")
        print(f"Width: {src.width}, Height: {src.height}")
        print(f"Count (Bands): {src.count}")
except Exception as e:
    print(f"Error: {e}")
