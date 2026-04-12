"""
test_all_predictors.py
======================
Tests all 4 pollutant predictors + weather API directly (no Django needed).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test coordinates: Bhubaneswar
LAT, LON = 20.2961, 85.8245

print("=" * 60)
print("1. TESTING WEATHER SERVICE")
print("=" * 60)
from weather_service import get_live_weather, get_climate_for_month, get_elevation

print("\n[Live weather from Open-Meteo]")
w = get_live_weather(LAT, LON)
for k, v in w.items():
    print(f"  {k}: {v}")

print("\n[Climate for January]")
c = get_climate_for_month(1)
for k, v in c.items():
    print(f"  {k}: {v}")

print("\n[Elevation]")
elev = get_elevation(LAT, LON)
print(f"  Elevation: {elev}m")

print("\n" + "=" * 60)
print("2. TESTING CO PREDICTOR")
print("=" * 60)
from co_predictor import co_predictor
result = co_predictor.predict_at_coords(LAT, LON, '1Y')
if result.get('error'):
    print(f"  ERROR: {result['error']}")
else:
    print(f"  Base value: {result['base_value_2026']}")
    print(f"  Timeline points: {len(result['timeline'])}")
    for pt in result['timeline'][:3]:
        print(f"    {pt['label']}: {pt['value']}")
    print(f"    ...")

print("\n" + "=" * 60)
print("3. TESTING NO2 PREDICTOR")
print("=" * 60)
from no2_predictor import no2_predictor
result = no2_predictor.predict_at_coords(LAT, LON, '1Y')
if result.get('error'):
    print(f"  ERROR: {result['error']}")
else:
    print(f"  Base value: {result['base_value_2026']}")
    print(f"  Timeline points: {len(result['timeline'])}")
    for pt in result['timeline'][:3]:
        print(f"    {pt['label']}: {pt['value']}")
    print(f"    ...")

print("\n" + "=" * 60)
print("4. TESTING O3 PREDICTOR")
print("=" * 60)
from o3_predictor import o3_predictor
result = o3_predictor.predict_at_coords(LAT, LON, '1Y')
if result.get('error'):
    print(f"  ERROR: {result['error']}")
else:
    print(f"  Base value: {result['base_value_2026']}")
    print(f"  Timeline points: {len(result['timeline'])}")
    for pt in result['timeline'][:3]:
        print(f"    {pt['label']}: {pt['value']}")
    print(f"    ...")
    # Verify values differ per month
    vals = [pt['value'] for pt in result['timeline']]
    unique_vals = len(set(vals))
    print(f"  Unique values across 12 months: {unique_vals}/12 {'✅ REAL' if unique_vals > 1 else '❌ SAME'}")

print("\n" + "=" * 60)
print("5. TESTING SO2 PREDICTOR")
print("=" * 60)
from so2_predictor import so2_predictor
result = so2_predictor.predict_at_coords(LAT, LON, '1Y')
if result.get('error'):
    print(f"  ERROR: {result['error']}")
else:
    print(f"  Base value: {result['base_value_2026']}")
    print(f"  Timeline points: {len(result['timeline'])}")
    for pt in result['timeline'][:3]:
        print(f"    {pt['label']}: {pt['value']}")
    print(f"    ...")
    vals = [pt['value'] for pt in result['timeline']]
    unique_vals = len(set(vals))
    print(f"  Unique values across 12 months: {unique_vals}/12 {'✅ REAL' if unique_vals > 1 else '❌ SAME'}")

print("\n" + "=" * 60)
print("6. TESTING RANGE PARAMETER (O3 with 1W)")
print("=" * 60)
result = o3_predictor.predict_at_coords(LAT, LON, '1W')
if result.get('error'):
    print(f"  ERROR: {result['error']}")
else:
    print(f"  Range: {result['range']}, Points: {len(result['timeline'])}")
    for pt in result['timeline']:
        print(f"    {pt['label']}: {pt['value']} (doy={pt['day_of_year']})")
    vals = [pt['value'] for pt in result['timeline']]
    unique_vals = len(set(vals))
    print(f"  Unique values: {unique_vals}/{len(vals)} {'✅ REAL' if unique_vals > 1 else '❌ SAME'}")

print("\n✅ ALL TESTS COMPLETE")
