import os
import duckdb
import pandas as pd

# Centralized pollutant configuration
POLLUTANT_CONFIGS = {
    "co": {
        "dataset_folder": "CO",
        "fallback_csv_pattern": "CO_Data_Improv*.csv"
    },
    "no2": {
        "dataset_folder": "NO2",
        "fallback_csv_pattern": "NO2_Data_Improv*.csv"
    },
    "o3": {
        "dataset_folder": "O3",
        "fallback_csv_pattern": "O3_Data_Improv*.csv"
    },
    "so2": {
        "dataset_folder": "SO2",
        "fallback_csv_pattern": "SO2_Data_Improv*.csv"
    },
    "pm25": {
        "dataset_folder": "PM25",
        "fallback_csv_pattern": "PM25_Data_Improv*.csv"
    }
}

class HuggingFaceBaseAPI:
    def __init__(self, pollutant_name, hf_token=None):
        self.pollutant_name = pollutant_name
        cfg = POLLUTANT_CONFIGS[pollutant_name]
        self.dataset_folder = cfg["dataset_folder"]
        self.fallback_csv_pattern = cfg["fallback_csv_pattern"]
        
        self.base_path = f"hf://datasets/ObitUchiha91/Airlytics_data_set/{self.dataset_folder}"
        self.con = duckdb.connect()
        
        try:
            self.con.execute("INSTALL httpfs;")
            self.con.execute("LOAD httpfs;")
        except Exception as e:
            print(f"[{self.__class__.__name__}] Failed to install/load httpfs: {e}")
            
        token = hf_token or os.environ.get("HF_TOKEN")
        if token:
            try:
                self.con.execute(f"CREATE SECRET hf_secret (TYPE HUGGINGFACE, TOKEN '{token}');")
                print(f"[{self.__class__.__name__}] Successfully authenticated with Hugging Face.")
            except Exception as e:
                print(f"[{self.__class__.__name__}] Failed to create HF secret: {e}")
        else:
            print(f"[{self.__class__.__name__}] No HF_TOKEN provided. Querying public dataset.")

    def _init_hf_files(self):
        if hasattr(self, '_hf_files_initialized') and self._hf_files_initialized:
            return
        self.hf_files = []
        try:
            from huggingface_hub import HfApi
            api = HfApi()
            nodes = api.list_repo_tree(
                repo_id='ObitUchiha91/Airlytics_data_set',
                repo_type='dataset',
                recursive=True
            )
            # Find all files belonging to this pollutant folder
            prefix = f"{self.dataset_folder}/"
            self.hf_files = [
                node.path for node in nodes
                if node.path.startswith(prefix) 
                and node.path.endswith('.parquet') 
                and getattr(node, 'size', 0) > 0 
                and 'tmp' not in node.path
            ]
            print(f"[{self.__class__.__name__}] Lazily loaded {len(self.hf_files)} valid files from Hugging Face.")
        except Exception as e:
            print(f"[{self.__class__.__name__}] Failed to list HF files lazily: {e}. Using fallback glob pattern.")
            self.hf_files = []
        self._hf_files_initialized = True

    def _get_year_folder(self, year):
        # Specific folder override for NO2 2021
        if self.dataset_folder == "NO2" and str(year) == "2021":
            return "2021 (1)"
        return str(year)

    def _get_valid_files(self, year="*"):
        self._init_hf_files()
        
        if not self.hf_files:
            # Fallback glob pattern
            year_folder = self._get_year_folder(year)
            if year == "*":
                return [f"{self.base_path}/*/*.parquet"]
            else:
                return [f"{self.base_path}/{year_folder}/*.parquet"]

        matched = []
        for path in self.hf_files:
            parts = path.split('/')
            if len(parts) >= 3:
                file_year_folder = parts[1]
                # Match if folder starts with queried year (handles "2021 (1)" for "2021")
                if year == "*" or file_year_folder.startswith(str(year)):
                    matched.append(f"hf://datasets/ObitUchiha91/Airlytics_data_set/{path}")
        
        if not matched:
            year_folder = self._get_year_folder(year)
            if year == "*":
                return [f"{self.base_path}/*/*.parquet"]
            else:
                return [f"{self.base_path}/{year_folder}/*.parquet"]
                
        return matched

    def get_by_state_and_year(self, state_name, year):
        print(f"[{self.__class__.__name__}] Fetching data for {state_name} in {year}...")
        file_paths = self._get_valid_files(year)
        print(f"Reading {file_paths}")
        
        # Get schema columns dynamically to avoid Binder Errors
        temp_df = self.con.execute(f"SELECT * FROM read_parquet({file_paths}, union_by_name=true) LIMIT 0").df()
        cols = temp_df.columns.tolist()
        
        # Resolve coordinates and pollutant columns
        lat_expr = "lat" if "lat" in cols else "latitude"
        lon_expr = "lon" if "lon" in cols else "longitude"
        if "lat" in cols and "latitude" in cols:
            lat_expr = "coalesce(lat, latitude)"
        if "lon" in cols and "longitude" in cols:
            lon_expr = "coalesce(lon, longitude)"
            
        target_val_col = f"{self.pollutant_name}_level"
        val_expr = self.pollutant_name
        if target_val_col in cols:
            val_expr = target_val_col
        if target_val_col in cols and self.pollutant_name in cols:
            val_expr = f"coalesce({self.pollutant_name}, {target_val_col})"

        other_cols = ["pbl", "temp", "u", "v", "humidity", "lights", "elev", "pop", "ndvi", "cld"]
        select_others = [c for c in other_cols if c in cols]
        select_others_str = ", ".join(select_others)
        if select_others_str:
            select_others_str = ", " + select_others_str

        query = f"""
            SELECT 
                date,
                cast({lat_expr} as double) as lat,
                cast({lon_expr} as double) as lon,
                {val_expr} as {target_val_col}
                {select_others_str}
            FROM read_parquet({file_paths}, union_by_name=true)
        """
        return self.con.execute(query).df()

    def get_by_bounding_box(self, min_lat, max_lat, min_lon, max_lon, year="*"):
        print(f"[{self.__class__.__name__}] Fetching bounding box for year(s): {year}...")
        file_paths = self._get_valid_files(year)
        print(f"Reading {file_paths}")
        
        temp_df = self.con.execute(f"SELECT * FROM read_parquet({file_paths}, union_by_name=true) LIMIT 0").df()
        cols = temp_df.columns.tolist()
        
        lat_expr = "lat" if "lat" in cols else "latitude"
        lon_expr = "lon" if "lon" in cols else "longitude"
        if "lat" in cols and "latitude" in cols:
            lat_expr = "coalesce(lat, latitude)"
        if "lon" in cols and "longitude" in cols:
            lon_expr = "coalesce(lon, longitude)"
            
        target_val_col = f"{self.pollutant_name}_level"
        val_expr = self.pollutant_name
        if target_val_col in cols:
            val_expr = target_val_col
        if target_val_col in cols and self.pollutant_name in cols:
            val_expr = f"coalesce({self.pollutant_name}, {target_val_col})"

        other_cols = ["pbl", "temp", "u", "v", "humidity", "lights", "elev", "pop", "ndvi", "cld"]
        select_others = [c for c in other_cols if c in cols]
        select_others_str = ", ".join(select_others)
        if select_others_str:
            select_others_str = ", " + select_others_str

        query = f"""
            SELECT 
                date,
                cast({lat_expr} as double) as lat,
                cast({lon_expr} as double) as lon,
                {val_expr} as {target_val_col}
                {select_others_str}
            FROM read_parquet({file_paths}, union_by_name=true)
            WHERE cast({lat_expr} as double) BETWEEN {min_lat} AND {max_lat}
              AND cast({lon_expr} as double) BETWEEN {min_lon} AND {max_lon}
        """
        df = self.con.execute(query).df()
        print(f"[{self.__class__.__name__}] Query returned {len(df)} rows.")
        return df

    def get_state_summary(self, year="*"):
        print(f"[{self.__class__.__name__}] Calculating summary statistics for year(s): {year}...")
        file_paths = self._get_valid_files(year)
        print(f"Reading {file_paths}")
        
        temp_df = self.con.execute(f"SELECT * FROM read_parquet({file_paths}, union_by_name=true) LIMIT 0").df()
        cols = temp_df.columns.tolist()
        
        target_val_col = f"{self.pollutant_name}_level"
        val_col = self.pollutant_name
        if target_val_col in cols:
            val_col = target_val_col
            
        query = f"""
            SELECT 
                filename as source_file,
                COUNT(*) as total_readings,
                AVG({val_col}) as mean_{self.pollutant_name},
                MAX({val_col}) as max_{self.pollutant_name}
            FROM read_parquet({file_paths}, union_by_name=true, filename=true)
            GROUP BY source_file
        """
        return self.con.execute(query).df()

    def get_data_for_coordinate(self, lat, lon, year="2023"):
        use_hf = True

        if use_hf:
            try:
                tolerance = 0.05
                df = self.get_by_bounding_box(lat - tolerance, lat + tolerance, lon - tolerance, lon + tolerance, year)
                if df.empty:
                    print(f"[{self.__class__.__name__}] Tight bbox empty, widening to 0.2 for ({lat}, {lon})")
                    df = self.get_by_bounding_box(lat - 0.2, lat + 0.2, lon - 0.2, lon + 0.2, year)
                
                if not df.empty:
                    print(f"[{self.__class__.__name__}] HF data: {len(df)} rows, columns: {list(df.columns)}")
                    lat_col = 'lat'
                    lon_col = 'lon'
                    
                    df['dist'] = (df[lat_col] - lat)**2 + (df[lon_col] - lon)**2
                    min_dist = df['dist'].min()
                    closest_coords = df[df['dist'] == min_dist]
                    closest_coords = closest_coords.drop(columns=['dist'])
                    print(f"[{self.__class__.__name__}] [SUCCESS] SOURCE=HuggingFace for ({lat}, {lon}), "
                          f"closest={len(closest_coords)} rows, dist={min_dist:.6f}")
                    return closest_coords
                else:
                    print(f"[{self.__class__.__name__}] [WARNING] HF returned empty for ({lat}, {lon}), year={year}")
            except Exception as e:
                print(f"[{self.__class__.__name__}] [ERROR] Hugging Face query failed: {e}. Falling back to local CSV.")

        # Fallback: Query local CSV files in `no2_weather_data/`
        is_production = "SPACE_ID" in os.environ or os.environ.get("ENV") == "production"
        if is_production:
            print(f"[{self.__class__.__name__}] Running in production space, skipping local CSV fallback.")
            return pd.DataFrame()

        try:
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            project_dir = os.path.dirname(backend_dir)
            csv_dir = os.path.join(project_dir, "no2_weather_data")
            
            if year == "*":
                file_pattern = os.path.join(csv_dir, self.fallback_csv_pattern)
            else:
                prefix_csv = self.fallback_csv_pattern.split("*")[0]
                file_pattern = os.path.join(csv_dir, f"{prefix_csv}{year}.csv")
            
            if not os.path.exists(csv_dir):
                print(f"[{self.__class__.__name__}] Local CSV directory not found at {csv_dir}")
                return pd.DataFrame()

            tolerance = 0.05
            safe_file_pattern = file_pattern.replace("\\", "/")
            print(f"Reading local CSV fallback: {safe_file_pattern}")
            
            query = f"""
                SELECT * 
                FROM '{safe_file_pattern}'
                WHERE lat BETWEEN {lat - tolerance} AND {lat + tolerance}
                  AND lon BETWEEN {lon - tolerance} AND {lon + tolerance}
            """
            df = self.con.execute(query).df()
            if df.empty:
                query = f"""
                    SELECT * 
                    FROM '{safe_file_pattern}'
                    WHERE lat BETWEEN {lat - 0.2} AND {lat + 0.2}
                      AND lon BETWEEN {lon - 0.2} AND {lon + 0.2}
                """
                df = self.con.execute(query).df()

            if not df.empty:
                df['dist'] = (df['lat'] - lat)**2 + (df['lon'] - lon)**2
                min_dist = df['dist'].min()
                closest_coords = df[df['dist'] == min_dist]
                closest_coords = closest_coords.drop(columns=['dist'])
                print(f"[{self.__class__.__name__}] Loaded closest coordinates from local CSV fallback for ({lat}, {lon})")
                return closest_coords
        except Exception as e:
            print(f"[{self.__class__.__name__}] Local CSV query failed: {e}")
            
        return pd.DataFrame()

    def close(self):
        try:
            self.con.close()
        except Exception:
            pass
