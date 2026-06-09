import os
import pandas as pd
import numpy as np
from scipy.spatial import KDTree

class GridDataService:
    """
    Singleton service that loads the spatial grid data (population, elevation)
    from CSV once and provides fast coordinate-based lookups.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GridDataService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        # Look for grid data in the root so2_weather_data folder
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'so2_weather_data', 'SO2_Odisha_2020.csv')
        if not os.path.exists(csv_path):
            print(f"[GridData] ERROR: CSV not found at {csv_path}")
            self.df = None
            self.tree = None
            self._initialized = True
            return

        print(f"[GridData] Loading spatial grid from {csv_path}...")
        try:
            # Read unique grid points
            full_df = pd.read_csv(csv_path, usecols=['lat', 'lon', 'pop', 'elev'])
            self.df = full_df.drop_duplicates(subset=['lat', 'lon']).reset_index(drop=True)
            
            # Build KDTree for fast spatial lookup
            coords = self.df[['lat', 'lon']].values
            self.tree = KDTree(coords)
            
            print(f"[GridData] Loaded {len(self.df)} unique points. Ready for lookup.")
        except Exception as e:
            print(f"[GridData] ERROR loading CSV: {e}")
            self.df = None
            self.tree = None
            
        self._initialized = True

    def get_data_at(self, lat, lon):
        """Returns (pop, elev) for the closest grid point."""
        if self.tree is None:
            return 5000.0, 100.0 # Fallbacks
            
        dist, idx = self.tree.query([lat, lon])
        
        # If the point is reasonably close (within 0.1 deg)
        if dist < 0.1:
            row = self.df.iloc[idx]
            pop = float(row['pop'])
            elev = float(row['elev'])
            
            # Sanitization
            if pop <= 0: pop = 5000.0
            return pop, elev
        
        return 5000.0, 100.0

# Singleton instance
grid_data_service = GridDataService()
