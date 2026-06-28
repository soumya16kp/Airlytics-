import duckdb
import os
import pandas as pd

class NO2HuggingFaceAPI:
    def __init__(self, hf_token=None):
        """
        Initializes the connection to Hugging Face using DuckDB.
        """
        self.base_path = "hf://datasets/ObitUchiha91/no2_data_yearly"
        
        # Initialize DuckDB connection
        self.con = duckdb.connect()
        
        # Install and load the extension required to read from URLs/Hugging Face
        try:
            self.con.execute("INSTALL httpfs;")
            self.con.execute("LOAD httpfs;")
        except Exception as e:
            print(f"[NO2Extractor] Failed to install/load httpfs extension: {e}")
        
        # Set up Hugging Face authentication
        # If no token is passed, it looks for an environment variable named HF_TOKEN
        token = hf_token or os.environ.get("HF_TOKEN")
        if token:
            try:
                self.con.execute(f"CREATE SECRET hf_secret (TYPE HUGGINGFACE, TOKEN '{token}');")
                print("[NO2Extractor] Successfully authenticated with Hugging Face.")
            except Exception as e:
                print(f"[NO2Extractor] Failed to create Hugging Face secret: {e}")
        else:
            print("[NO2Extractor] No HF_TOKEN provided. This will only work if the dataset is public.")

    def get_by_state_and_year(self, state_name, year):
        """
        Replaces GEE Region/Time filtering. 
        Fetches data for a specific state and year instantly.
        """
        print(f"Fetching data for {state_name} in {year}...")
        
        # Points directly to the specific parquet file in the folder structure
        file_path = f"{self.base_path}/{year}/{state_name}.parquet"
        
        query = f"SELECT * FROM '{file_path}'"
        
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
            file_path = f"{self.base_path}/{year}/*.parquet"
            
        query = f"""
            SELECT * 
            FROM '{file_path}'
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
                AVG(no2_level) as mean_no2,
                MAX(no2_level) as max_no2
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
                    df = self.get_by_bounding_box(lat - 0.2, lat + 0.2, lon - 0.2, lon + 0.2, year)
                
                if not df.empty:
                    lat_col = 'latitude' if 'latitude' in df.columns else 'lat'
                    lon_col = 'longitude' if 'longitude' in df.columns else 'lon'
                    
                    df['dist'] = (df[lat_col] - lat)**2 + (df[lon_col] - lon)**2
                    min_dist = df['dist'].min()
                    closest_coords = df[df['dist'] == min_dist]
                    closest_coords = closest_coords.drop(columns=['dist'])
                    print(f"[NO2Extractor] Loaded closest coordinates from Hugging Face for ({lat}, {lon})")
                    return closest_coords
            except Exception as e:
                print(f"[NO2Extractor] Hugging Face query failed: {e}. Falling back to local CSV.")

        # Fallback: Query local CSV files in `no2_weather_data/`
        try:
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            project_dir = os.path.dirname(backend_dir)
            csv_dir = os.path.join(project_dir, "no2_weather_data")
            
            if year == "*":
                file_pattern = os.path.join(csv_dir, "NO2_Data_Improv*.csv")
            else:
                file_pattern = os.path.join(csv_dir, f"NO2_Data_Improv{year}.csv")
            
            if not os.path.exists(csv_dir):
                print(f"[NO2Extractor] Local CSV directory not found at {csv_dir}")
                return pd.DataFrame()

            # Query the CSV using DuckDB
            tolerance = 0.05
            query = f"""
                SELECT * 
                FROM '{file_pattern.replace('\\', '/')}'
                WHERE lat BETWEEN {lat - tolerance} AND {lat + tolerance}
                  AND lon BETWEEN {lon - tolerance} AND {lon + tolerance}
            """
            df = self.con.execute(query).df()
            if df.empty:
                query = f"""
                    SELECT * 
                    FROM '{file_pattern.replace('\\', '/')}'
                    WHERE lat BETWEEN {lat - 0.2} AND {lat + 0.2}
                      AND lon BETWEEN {lon - 0.2} AND {lon + 0.2}
                """
                df = self.con.execute(query).df()

            if not df.empty:
                df['dist'] = (df['lat'] - lat)**2 + (df['lon'] - lon)**2
                min_dist = df['dist'].min()
                closest_coords = df[df['dist'] == min_dist]
                closest_coords = closest_coords.drop(columns=['dist'])
                print(f"[NO2Extractor] Loaded closest coordinates from local CSV fallback for ({lat}, {lon})")
                return closest_coords
        except Exception as e:
            print(f"[NO2Extractor] Local CSV query failed: {e}")
            
        return pd.DataFrame()

    def close(self):
        try:
            self.con.close()
        except Exception:
            pass
