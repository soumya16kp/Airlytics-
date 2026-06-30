import os
import pandas as pd
import numpy as np

try:
    from scipy.spatial import KDTree
    HAS_KDTREE = True
except ImportError:
    HAS_KDTREE = False

class GridDataService:
    """
    Singleton service that loads the spatial grid data (population, elevation)
    from HuggingFace via DuckDB and provides fast coordinate-based lookups.
    Falls back to safe defaults if unavailable.
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

        self.df = None
        self.tree = None

        # Try DuckDB → HuggingFace parquet first
        try:
            import duckdb
            hf_token = os.getenv("HF_TOKEN")
            con = duckdb.connect()
            con.execute("INSTALL httpfs;")
            con.execute("LOAD httpfs;")
            if hf_token:
                con.execute(f"CREATE SECRET hf_secret (TYPE HUGGINGFACE, TOKEN '{hf_token}');")

            # Query grid data from the HF dataset — lat/lon/pop/elev columns
            # Dataset: ObitUchiha91/Airlytics_data_set (main project dataset)
            hf_path = "hf://datasets/ObitUchiha91/Airlytics_data_set/NO2/**/*.parquet"
            print(f"[GridData] Loading spatial grid via DuckDB from HuggingFace NO2 dataset...")

            query = f"""
                SELECT lat, lon,
                       AVG(pop)  AS pop,
                       AVG(elev) AS elev
                FROM '{hf_path}'
                GROUP BY lat, lon
                LIMIT 50000
            """
            result_df = con.execute(query).df()
            con.close()

            if not result_df.empty:
                self.df = result_df.drop_duplicates(subset=['lat', 'lon']).reset_index(drop=True)
                if HAS_KDTREE:
                    coords = self.df[['lat', 'lon']].values
                    self.tree = KDTree(coords)
                print(f"[GridData] Loaded {len(self.df)} unique grid points from HuggingFace.")
            else:
                print("[GridData] WARNING: DuckDB returned empty result — using default fallbacks.")
        except Exception as e:
            print(f"[GridData] WARNING: DuckDB/HF load failed: {e}. Using default fallbacks (pop=5000, elev=100).")
            self.df = None
            self.tree = None

        self._initialized = True

    def get_data_at(self, lat, lon):
        """Returns (pop, elev) for the closest grid point. Falls back to safe defaults."""
        if self.tree is None or self.df is None:
            return 5000.0, 100.0

        dist, idx = self.tree.query([lat, lon])

        # Only use if within 0.5 degrees (≈55 km)
        if dist < 0.5:
            row = self.df.iloc[idx]
            pop  = float(row.get('pop',  5000.0) or 5000.0)
            elev = float(row.get('elev', 100.0)  or 100.0)
            if pop <= 0:
                pop = 5000.0
            return pop, elev

        return 5000.0, 100.0

# Singleton instance (loaded once at Django startup)
grid_data_service = GridDataService()
