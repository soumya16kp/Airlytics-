import duckdb
import os
import pandas as pd

class O3HuggingFaceAPI:
    def __init__(self, hf_token=None):
        """
        Initializes the connection to Hugging Face using DuckDB.
        """
        self.base_path = "hf://datasets/ObitUchiha91/Airlytics_data_set/O3"
        
        # Initialize DuckDB connection
        self.con = duckdb.connect()
        
        # Install and load the extension required to read from URLs/Hugging Face
        try:
            self.con.execute("INSTALL httpfs;")
            self.con.execute("LOAD httpfs;")
        except Exception as e:
            print(f"[O3Extractor] Failed to install/load httpfs extension: {e}")
        
        # Set up Hugging Face authentication
        # If no token is passed, it looks for an environment variable named HF_TOKEN
        token = hf_token or os.environ.get("HF_TOKEN")
        if token:
            try:
                self.con.execute(f"CREATE SECRET hf_secret (TYPE HUGGINGFACE, TOKEN '{token}');")
                print("[O3Extractor] Successfully authenticated with Hugging Face.")
            except Exception as e:
                print(f"[O3Extractor] Failed to create Hugging Face secret: {e}")
        else:
            print("[O3Extractor] No HF_TOKEN provided. Dataset is public, so DuckDB should still work.")

    def get_by_state_and_year(self, state_name, year):
        """
        Replaces GEE Region/Time filtering. 
        Fetches data for a specific state and year instantly.
        """
        print(f"Fetching data for {state_name} in {year}...")
        
        # Uses union_by_name to handle minor schema drift in public datasets
        file_path = f"{self.base_path}/{year}/{state_name}.parquet"
        query = f"SELECT * FROM read_parquet('{file_path}', union_by_name=true)"
        
        return self.con.execute(query).df()

    def get_by_bounding_box(self, min_lat, max_lat, min_lon, max_lon, year="*"):
        """
        Replaces GEE Bounding Box filtering.
        """
        print(f"Fetching bounding box for year(s): {year}...")
        
        # Optimize by querying Orissa specifically if coordinate is within Orissa bounds
        if 17.0 <= min_lat <= 23.5 and 81.0 <= min_lon <= 88.0:
            file_path = f"{self.base_path}/{year}/*Orissa*.parquet"
        else:
            file_path = f"{self.base_path}/{year}/**/*.parquet"
            
        query = f"""
            SELECT * 
            FROM read_parquet('{file_path}', union_by_name=true)
            WHERE lat BETWEEN {min_lat} AND {max_lat}
              AND lon BETWEEN {min_lon} AND {max_lon}
        """
        return self.con.execute(query).df()

    def get_state_summary(self, year="*"):
        """
        Replaces GEE Reducers.
        """
        print(f"Calculating summary statistics for year(s): {year}...")
        file_path = f"{self.base_path}/{year}/*.parquet"
        
        query = f"""
            SELECT 
                file_name() as source_file,
                COUNT(*) as total_readings,
                AVG(o3_level) as mean_o3,
                MAX(o3_level) as max_o3
            FROM '{file_path}'
            GROUP BY source_file
        """
        return self.con.execute(query).df()

    def get_data_for_coordinate(self, lat, lon, year="2023"):
        """
        Fetches the closest coordinate data and returns a Pandas DataFrame.
        """
        use_hf = False
        token = os.environ.get("HF_TOKEN")
        if token:
            use_hf = True

        # Try Hugging Face first if token is available
        if use_hf:
            try:
                tolerance = 0.05
                df = self.get_by_bounding_box(lat - tolerance, lat + tolerance, lon - tolerance, lon + tolerance, year)
                if df.empty:
                    print(f"[O3Extractor] Tight bbox empty, widening to 0.2 for ({lat}, {lon})")
                    df = self.get_by_bounding_box(lat - 0.2, lat + 0.2, lon - 0.2, lon + 0.2, year)
                
                if not df.empty:
                    print(f"[O3Extractor] HF data: {len(df)} rows, columns: {list(df.columns)}")
                    lat_col = 'latitude' if 'latitude' in df.columns else 'lat'
                    lon_col = 'longitude' if 'longitude' in df.columns else 'lon'
                    
                    df['dist'] = (df[lat_col] - lat)**2 + (df[lon_col] - lon)**2
                    min_dist = df['dist'].min()
                    closest_coords = df[df['dist'] == min_dist]
                    closest_coords = closest_coords.drop(columns=['dist'])
                    print(f"[O3Extractor] âœ… SOURCE=HuggingFace for ({lat}, {lon}), "
                          f"closest={len(closest_coords)} rows, dist={min_dist:.6f}")
                    return closest_coords
                else:
                    print(f"[O3Extractor] âš  HF returned empty for ({lat}, {lon}), year={year}")
            except Exception as e:
                print(f"[O3Extractor] âŒ Hugging Face query failed: {e}. Falling back to local CSV.")

        # Fallback: Query local CSV files in `no2_weather_data/`
        try:
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            project_dir = os.path.dirname(backend_dir)
            csv_dir = os.path.join(project_dir, "no2_weather_data")
            
            if year == "*":
                file_pattern = os.path.join(csv_dir, "O3_Data_Improv*.csv")
            else:
                file_pattern = os.path.join(csv_dir, f"O3_Data_Improv{year}.csv")
            
            if not os.path.exists(csv_dir):
                print(f"[O3Extractor] Local CSV directory not found at {csv_dir}")
                return pd.DataFrame()

            # Query the CSV using DuckDB
            tolerance = 0.05
            safe_file_pattern = file_pattern.replace("\\", "/")
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
                print(f"[O3Extractor] Loaded closest coordinates from local CSV fallback for ({lat}, {lon})")
                return closest_coords
        except Exception as e:
            print(f"[O3Extractor] Local CSV query failed: {e}")
            
        return pd.DataFrame()

    def close(self):
        try:
            self.con.close()
        except Exception:
            pass

