import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from so2_predictor import so2_predictor
r = so2_predictor.predict_at_coords(20.2961, 85.8245, '1Y')
print('Error:', r.get('error'))
print('Base:', r.get('base_value_2026'))
print('Points:', len(r.get('timeline', [])))
for p in r.get('timeline', [])[:4]:
    print(f"  {p['label']}: {p['value']}")

# Also test 1W range for O3
from o3_predictor import o3_predictor
r2 = o3_predictor.predict_at_coords(20.2961, 85.8245, '1W')
print('\nO3 1W range:')
print('Points:', len(r2.get('timeline', [])))
for p in r2.get('timeline', []):
    print(f"  {p['label']}: {p['value']} (doy={p['day_of_year']})")
vals = [p['value'] for p in r2.get('timeline', [])]
unique = len(set(vals))
print(f"Unique daily values: {unique}/{len(vals)}")
