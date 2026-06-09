import os
import django
import pandas as pd
import numpy as np

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import Town

def seed_population_and_elevation():
    csv_path = os.path.join('New folder', 'SO2_Odisha_2020.csv')
    if not os.path.exists(csv_path):
        print(f"CSV not found at {csv_path}")
        return

    print(f"Loading CSV: {csv_path}...")
    # Read only necessary columns and drop duplicates to save memory
    df = pd.read_csv(csv_path, usecols=['lat', 'lon', 'pop', 'elev'])
    df = df.drop_duplicates(subset=['lat', 'lon'])
    
    print(f"Loaded {len(df)} unique grid points.")

    towns = Town.objects.all()
    updated_count = 0

    for town in towns:
        if town.latitude is None or town.longitude is None:
            continue

        # Find the closest grid point
        # Calculate Euclidean distance
        df['dist'] = np.sqrt((df['lat'] - town.latitude)**2 + (df['lon'] - town.longitude)**2)
        closest = df.loc[df['dist'].idxmin()]
        
        # If distance is reasonably small (e.g., within 0.1 degrees)
        if closest['dist'] < 0.1:
            town.pop = float(closest['pop'])
            town.elevation = float(closest['elev'])
            # The CSV seems to have -200 for population in some places, 
            # let's use a sensible fallback if it's negative or zero
            if town.pop <= 0:
                town.pop = 5000.0
            
            town.save()
            print(f"Updated {town.name}: pop={town.pop}, elev={town.elevation} (dist={closest['dist']:.4f})")
            updated_count += 1
        else:
            print(f"Skipping {town.name}: No close grid point found (min dist={closest['dist']:.4f})")

    print(f"\nDone! Updated {updated_count} towns.")

if __name__ == '__main__':
    seed_population_and_elevation()
