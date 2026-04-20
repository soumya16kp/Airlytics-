import csv, math

# SO2
with open(r'../so2_weather_data/SO2_Odisha_2024.csv') as f:
    reader = csv.DictReader(f)
    row = next(reader)
    print('=== SO2 CSV Row ===')
    for k, v in row.items():
        print(f'  {k}: {v}')
    temp_k = float(row['temp'])
    print(f'\nTemp in CSV: {temp_k}K = {temp_k - 273.15:.1f}C')
    u = float(row['u'])
    v_w = float(row['v'])
    ws = math.sqrt(u*u + v_w*v_w)
    wd = math.degrees(math.atan2(-u, -v_w)) % 360
    print(f'Wind u={u:.2f}, v={v_w:.2f} -> speed={ws:.2f} m/s, dir={wd:.1f} deg')
    so2_val = float(row['so2'])
    print(f'SO2 observed: {so2_val:.2e}')
    print(f'PBL: {float(row["pbl"]):.1f} m')
    cld = float(row['cld'])
    print(f'Cloud: {cld:.4f} (fraction 0-1? model expects %)')

print()

# O3
with open(r'../o3_weather_data/O3_Odisha_improv2024.csv') as f:
    reader = csv.DictReader(f)
    row = next(reader)
    print('=== O3 CSV Row ===')
    for k, v in row.items():
        print(f'  {k}: {v}')
    temp_k = float(row['temp'])
    print(f'\nTemp in CSV: {temp_k}K = {temp_k - 273.15:.1f}C')
    u = float(row['u'])
    v_w = float(row['v'])
    ws = math.sqrt(u*u + v_w*v_w)
    print(f'Wind u={u:.2f}, v={v_w:.2f} -> speed={ws:.2f} m/s')
    o3_val = float(row['o3'])
    print(f'O3 observed: {o3_val:.6f} DU')
    print(f'Solar: {float(row["solar"]):.1f}')
    print(f'PBL: {float(row["pbl"]):.1f} m')
    cld = float(row['cld'])
    print(f'Cloud: {cld:.4f}')
