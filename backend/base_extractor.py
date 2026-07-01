import os
import time
import duckdb
import pandas as pd
import threading

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

# State bounding boxes in India
STATE_BBOXES = {
    'Chandigarh': (30.7693, 30.7693, 76.7906, 76.7906),
    'Goa': (14.9916, 15.6916, 73.7790, 74.2790),
    'Gujarat': (20.2208, 24.6208, 68.4782, 74.3782),
    'Jharkhand': (22.0666, 25.2666, 83.4236, 87.9236),
    'Nagaland': (25.3020, 26.9020, 93.4317, 95.2317),
    'Puducherry': (10.9111, 16.7111, 75.3211, 82.2211),
    'Uttar Pradesh': (23.9728, 30.2728, 77.1849, 84.5849),
    'Haryana': (27.7560, 30.8560, 74.5653, 77.5653),
    'Tamil Nadu': (8.1745, 13.4745, 76.3257, 80.3257),
    'West Bengal': (21.5685, 27.1685, 85.9264, 89.8264),
    'Daman and Diu': (20.7687, 20.8687, 70.7712, 70.8712),
    'Meghalaya': (25.1288, 26.0288, 89.9157, 92.7157),
    'Chhattisgarh': (17.8828, 24.0828, 80.3396, 84.3396),
    'Tripura': (23.0290, 24.5290, 91.2509, 92.2509),
    'Dadra and Nagar Haveli': (20.1516, 20.2516, 73.0223, 73.1223),
    'Manipur': (23.9360, 25.6360, 93.0736, 94.6736),
    'Arunachal Pradesh': (26.7426, 28.2426, 94.2358, 97.1358),
    'Himachal Pradesh': (30.4845, 33.0845, 75.6788, 78.8788),
    'Kerala': (8.3973, 12.6973, 74.9661, 77.3661),
    'Andhra Pradesh': (12.7118, 19.8118, 76.8570, 84.6570),
    'Maharashtra': (15.7046, 21.9046, 72.7504, 80.8504),
    'Orissa': (17.9026, 22.5026, 81.4830, 87.3830),
    'Delhi': (28.5085, 28.8085, 76.9329, 77.3329),
    'Mizoram': (22.0467, 24.4467, 92.3594, 93.3594),
    'Assam': (24.2348, 27.9348, 89.7948, 95.8948),
    'Karnataka': (11.6745, 18.3745, 74.1547, 78.5547),
    'Madhya Pradesh': (21.1753, 26.7753, 74.1347, 82.7347),
    'Rajasthan': (23.1627, 30.0627, 69.5837, 78.1837),
    'Sikkim': (27.1816, 28.0816, 88.1169, 88.8169),
    'Uttarakhand': (28.8156, 31.2156, 77.6622, 80.9622),
    'Bihar': (24.3870, 27.4870, 83.4161, 88.2161),
    'Punjab': (29.6462, 32.4462, 73.9709, 76.8709),
    'Andaman and Nicobar': (6.8560, 13.6560, 92.4042, 93.9042),
}

def resolve_partitions(lat, lon, buffer_deg=0.5):
    candidate_states = []
    for state, (min_lat, max_lat, min_lon, max_lon) in STATE_BBOXES.items():
        if (min_lat - buffer_deg) <= lat <= (max_lat + buffer_deg) and \
           (min_lon - buffer_deg) <= lon <= (max_lon + buffer_deg):
            candidate_states.append(state)
    return candidate_states

# Lightweight thread-safe TTL cache
class SimpleTTLCache:
    def __init__(self, maxsize=1024, ttl=3600):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = {}
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key in self.cache:
                val, expire_time = self.cache[key]
                if time.time() < expire_time:
                    return val
                else:
                    del self.cache[key]
            return None

    def set(self, key, val):
        with self.lock:
            if len(self.cache) >= self.maxsize:
                now = time.time()
                expired_keys = [k for k, (_, exp) in self.cache.items() if now >= exp]
                if expired_keys:
                    for k in expired_keys:
                        del self.cache[k]
                else:
                    del self.cache[next(iter(self.cache))]
            self.cache[key] = (val, time.time() + self.ttl)

class HuggingFaceBaseAPI:
    # Single global DuckDB connection shared across all threads
    _GLOBAL_CONN = None
    _GLOBAL_CONN_LOCK = threading.Lock()
    _GLOBAL_FILE_CACHE = {}

    def __init__(self, pollutant_name, hf_token=None):
        self.pollutant_name = pollutant_name
        cfg = POLLUTANT_CONFIGS[pollutant_name]
        self.dataset_folder = cfg["dataset_folder"]
        self.fallback_csv_pattern = cfg["fallback_csv_pattern"]
        
        self.base_path = f"hf://datasets/ObitUchiha91/Airlytics_data_set/{self.dataset_folder}"
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self._query_cache = SimpleTTLCache(maxsize=1024, ttl=3600)
        
        # Initialize connection once
        with HuggingFaceBaseAPI._GLOBAL_CONN_LOCK:
            if HuggingFaceBaseAPI._GLOBAL_CONN is None:
                conn = duckdb.connect()
                try:
                    conn.execute("INSTALL httpfs; LOAD httpfs;")
                    if self.hf_token:
                        conn.execute(f"CREATE SECRET hf_secret (TYPE HUGGINGFACE, TOKEN '{self.hf_token}');")
                except Exception as e:
                    print(f"[{self.__class__.__name__}] Failed to initialize DuckDB global connection: {e}")
                HuggingFaceBaseAPI._GLOBAL_CONN = conn

    def _get_cursor(self):
        return HuggingFaceBaseAPI._GLOBAL_CONN.cursor()

    def _init_hf_files(self):
        if self.dataset_folder in HuggingFaceBaseAPI._GLOBAL_FILE_CACHE:
            self.hf_files = HuggingFaceBaseAPI._GLOBAL_FILE_CACHE[self.dataset_folder]
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
            prefix = f"{self.dataset_folder}/"
            self.hf_files = [
                node.path for node in nodes
                if node.path.startswith(prefix) 
                and node.path.endswith('.parquet') 
                and getattr(node, 'size', 0) > 0 
                and 'tmp' not in node.path
            ]
            HuggingFaceBaseAPI._GLOBAL_FILE_CACHE[self.dataset_folder] = self.hf_files
            print(f"[{self.__class__.__name__}] Lazily loaded {len(self.hf_files)} valid files from Hugging Face.")
        except Exception as e:
            print(f"[{self.__class__.__name__}] Failed to list HF files lazily: {e}. Using fallback glob pattern.")
            self.hf_files = []

    def _get_year_folder(self, year):
        if self.dataset_folder == "NO2" and str(year) == "2021":
            return "2021 (1)"
        return str(year)

    def _get_valid_files(self, year="*", partitions=None):
        self._init_hf_files()
        
        if self.dataset_folder == "PM25":
            partitions = None

        if not self.hf_files:
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
                filename = parts[2].lower()
                
                if year == "*" or file_year_folder.startswith(str(year)):
                    if partitions:
                        state_matched = False
                        for state in partitions:
                            state_clean = state.lower().replace(" ", "_")
                            state_clean_no_space = state.lower().replace(" ", "")
                            if (state_clean in filename or 
                                state_clean_no_space in filename or 
                                state.lower() in filename):
                                state_matched = True
                                break
                        if not state_matched:
                            continue
                            
                    matched.append(f"hf://datasets/ObitUchiha91/Airlytics_data_set/{path}")
        
        if not matched:
            year_folder = self._get_year_folder(year)
            if year == "*":
                return [f"{self.base_path}/*/*.parquet"]
            else:
                return [f"{self.base_path}/{year_folder}/*.parquet"]
                
        return matched

    def get_by_state_and_year(self, state_name, year):
        t0 = time.time()
        print(f"[{self.__class__.__name__}] Fetching data for {state_name} in {year}...")
        
        # Partition pruning: query specific state's folder if it exists in partitions bounds
        t_list_start = time.time()
        file_paths = self._get_valid_files(year, [state_name])
        t_list = time.time() - t_list_start
        print(f"Reading {file_paths}")
        
        cursor = self._get_cursor()
        temp_df = cursor.execute(f"SELECT * FROM read_parquet({file_paths}, union_by_name=true) LIMIT 0").df()
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
        
        cast_others = [f"try_cast({c} as double) as {c}" for c in select_others]
        cast_others_str = ", ".join(cast_others)
        if cast_others_str:
            cast_others_str = ", " + cast_others_str

        query = f"""
            SELECT 
                date,
                try_cast({lat_expr} as double) as lat,
                try_cast({lon_expr} as double) as lon,
                try_cast({val_expr} as double) as {target_val_col}
                {cast_others_str}
            FROM read_parquet({file_paths}, union_by_name=true)
        """
        
        t_query_start = time.time()
        df = cursor.execute(query).df()
        t_query = time.time() - t_query_start
        
        t_total = time.time() - t0
        print(f"[{self.__class__.__name__}] Query returned {len(df)} rows. Timings -> File list: {t_list:.3f}s, Query: {t_query:.3f}s, Total: {t_total:.3f}s")
        return df

    def get_by_bounding_box(self, min_lat, max_lat, min_lon, max_lon, year="*"):
        t0 = time.time()
        print(f"[{self.__class__.__name__}] Fetching bounding box for year(s): {year}...")
        
        partitions = []
        for state, (s_min_lat, s_max_lat, s_min_lon, s_max_lon) in STATE_BBOXES.items():
            if s_min_lat <= max_lat and s_max_lat >= min_lat and \
               s_min_lon <= max_lon and s_max_lon >= min_lon:
                partitions.append(state)

        t_list_start = time.time()
        file_paths = self._get_valid_files(year, partitions)
        t_list = time.time() - t_list_start
        print(f"Reading {file_paths}")
        
        cursor = self._get_cursor()
        temp_df = cursor.execute(f"SELECT * FROM read_parquet({file_paths}, union_by_name=true) LIMIT 0").df()
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
        
        cast_others = [f"try_cast({c} as double) as {c}" for c in select_others]
        cast_others_str = ", ".join(cast_others)
        if cast_others_str:
            cast_others_str = ", " + cast_others_str

        query = f"""
            SELECT 
                date,
                try_cast({lat_expr} as double) as lat,
                try_cast({lon_expr} as double) as lon,
                try_cast({val_expr} as double) as {target_val_col}
                {cast_others_str}
            FROM read_parquet({file_paths}, union_by_name=true)
            WHERE try_cast({lat_expr} as double) BETWEEN $1 AND $2
              AND try_cast({lon_expr} as double) BETWEEN $3 AND $4
        """
        
        t_query_start = time.time()
        df = cursor.execute(query, [min_lat, max_lat, min_lon, max_lon]).df()
        t_query = time.time() - t_query_start
        
        t_total = time.time() - t0
        print(f"[{self.__class__.__name__}] Query returned {len(df)} rows. Timings -> File list: {t_list:.3f}s, Query: {t_query:.3f}s, Total: {t_total:.3f}s")
        return df

    def get_state_summary(self, year="*"):
        t0 = time.time()
        print(f"[{self.__class__.__name__}] Calculating summary statistics for year(s): {year}...")
        file_paths = self._get_valid_files(year)
        print(f"Reading {file_paths}")
        
        cursor = self._get_cursor()
        temp_df = cursor.execute(f"SELECT * FROM read_parquet({file_paths}, union_by_name=true) LIMIT 0").df()
        cols = temp_df.columns.tolist()
        
        target_val_col = f"{self.pollutant_name}_level"
        val_col = self.pollutant_name
        if target_val_col in cols:
            val_col = target_val_col
            
        query = f"""
            SELECT 
                filename as source_file,
                COUNT(*) as total_readings,
                AVG(try_cast({val_col} as double)) as mean_{self.pollutant_name},
                MAX(try_cast({val_col} as double)) as max_{self.pollutant_name}
            FROM read_parquet({file_paths}, union_by_name=true, filename=true)
            GROUP BY source_file
        """
        df = cursor.execute(query).df()
        t_total = time.time() - t0
        print(f"[{self.__class__.__name__}] State summary took {t_total:.3f}s")
        return df

    def get_data_for_coordinate(self, lat, lon, year="2023"):
        cache_key = (lat, lon, year)
        cached_df = self._query_cache.get(cache_key)
        if cached_df is not None:
            print(f"[{self.__class__.__name__}] Cache hit for key {cache_key}")
            return cached_df.copy()

        t0 = time.time()
        print(f"[{self.__class__.__name__}] Fetching closest coordinate for ({lat}, {lon}) in year {year}...")
        
        partitions = resolve_partitions(lat, lon, buffer_deg=0.5)
        
        t_list_start = time.time()
        file_paths = self._get_valid_files(year, partitions)
        t_list = time.time() - t_list_start
        print(f"Reading {file_paths}")
        
        cursor = self._get_cursor()
        
        temp_df = cursor.execute(f"SELECT * FROM read_parquet({file_paths}, union_by_name=true) LIMIT 0").df()
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
        
        cast_others = [f"try_cast({c} as double) as {c}" for c in select_others]
        cast_others_str = ", ".join(cast_others)
        if cast_others_str:
            cast_others_str = ", " + cast_others_str

        radius = 0.2
        min_lat, max_lat = lat - radius, lat + radius
        min_lon, max_lon = lon - radius, lon + radius

        query = f"""
            SELECT 
                date,
                try_cast({lat_expr} as double) as lat,
                try_cast({lon_expr} as double) as lon,
                try_cast({val_expr} as double) as {target_val_col}
                {cast_others_str}
            FROM read_parquet({file_paths}, union_by_name=true)
            WHERE try_cast({lat_expr} as double) BETWEEN $1 AND $2
              AND try_cast({lon_expr} as double) BETWEEN $3 AND $4
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY date 
                ORDER BY (try_cast({lat_expr} as double) - $5)^2 + (try_cast({lon_expr} as double) - $6)^2
            ) = 1
        """
        
        try:
            t_query_start = time.time()
            df = cursor.execute(query, [min_lat, max_lat, min_lon, max_lon, lat, lon]).df()
            t_query = time.time() - t_query_start
            
            if df.empty:
                print(f"[{self.__class__.__name__}] Radius 0.2 returned empty. Retrying with radius 0.5...")
                df = cursor.execute(query, [lat - 0.5, lat + 0.5, lon - 0.5, lon + 0.5, lat, lon]).df()
                t_query = time.time() - t_query_start
                
            t_total = time.time() - t0
            print(f"[{self.__class__.__name__}] Query returned {len(df)} rows. Timings -> File list: {t_list:.3f}s, Query: {t_query:.3f}s, Total: {t_total:.3f}s")
            
            if not df.empty:
                self._query_cache.set(cache_key, df)
                print(f"[{self.__class__.__name__}] [SUCCESS] SOURCE=HuggingFace for ({lat}, {lon}), rows={len(df)}")
                return df.copy()
            else:
                print(f"[{self.__class__.__name__}] [WARNING] HF returned empty for ({lat}, {lon}), year={year}")
        except Exception as e:
            print(f"[{self.__class__.__name__}] [ERROR] Hugging Face query failed: {e}. Falling back to local CSV.")

        # Fallback to local CSV
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

            tolerance = 0.2
            safe_file_pattern = file_pattern.replace("\\", "/")
            
            # Check file existence prior to read_parquet
            if not os.path.exists(safe_file_pattern):
                print(f"[{self.__class__.__name__}] Fallback file does not exist: {safe_file_pattern}")
                return pd.DataFrame()

            print(f"Reading local CSV fallback: {safe_file_pattern}")
            
            query = f"""
                SELECT * 
                FROM '{safe_file_pattern}'
                WHERE try_cast(lat as double) BETWEEN $1 AND $2
                  AND try_cast(lon as double) BETWEEN $3 AND $4
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY date 
                    ORDER BY (try_cast(lat as double) - $5)^2 + (try_cast(lon as double) - $6)^2
                ) = 1
            """
            df = cursor.execute(query, [lat - tolerance, lat + tolerance, lon - tolerance, lon + tolerance, lat, lon]).df()
            if not df.empty:
                print(f"[{self.__class__.__name__}] Loaded closest coordinates from local CSV fallback for ({lat}, {lon})")
                return df
        except Exception as e:
            print(f"[{self.__class__.__name__}] Local CSV query failed: {e}")
            
        return pd.DataFrame()

    def close(self):
        # NOP since it's a global connection closed on exit
        pass

# Graceful shutdown hook
import atexit
@atexit.register
def _shutdown():
    if HuggingFaceBaseAPI._GLOBAL_CONN:
        try:
            HuggingFaceBaseAPI._GLOBAL_CONN.close()
            print("[HuggingFaceBaseAPI] Closed shared global DuckDB connection.")
        except Exception:
            pass
