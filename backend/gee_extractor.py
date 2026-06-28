import ee
import datetime
import math
import pandas as pd
from api_app.views.gee import initialize_ee

class EarthEngineExtractor:
    def __init__(self):
        initialize_ee()

    def get_monthly_data(self, lat, lon, pollutant, years):
        """
        Fetches monthly aggregated weather and pollutant data from GEE
        for the specified point and years.
        Returns a list of dicts to be consumed by HistoricalDataService.
        """
        point = ee.Geometry.Point(lon, lat)

        # 1. Define Datasets
        if pollutant == 'so2':
            pollutant_col = ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_SO2")\
                .select(['SO2_column_number_density', 'cloud_fraction'])
            val_col = 'so2'
        elif pollutant == 'no2':
            pollutant_col = ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")\
                .select(['NO2_column_number_density', 'cloud_fraction'])
            val_col = 'no2'
        else:
            pollutant_col = ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_O3")\
                .select(['O3_column_number_density', 'cloud_fraction'])
            val_col = 'o3'

        # ERA5 for weather (Removed boundary_layer_height as it's not in DAILY)
        era5_col = ee.ImageCollection("ECMWF/ERA5/DAILY")\
            .select(['mean_2m_air_temperature', 'u_component_of_wind_10m', 'v_component_of_wind_10m'])
            
        # MERRA-2 for actual Planetary Boundary Layer Height (PBLH)
        # NASA/GSFC/MERRA/flx/2 has real PBLH measurements (metres)
        merra2_col = ee.ImageCollection("NASA/GSFC/MERRA/flx/2")\
            .select(['PBLH'])

        # Elevation and Population (Static)
        elev_img = ee.Image('USGS/SRTMGL1_003').select('elevation')
        pop_img = ee.ImageCollection("WorldPop/GP/100m/pop").filter(ee.Filter.eq('year', 2020)).first()

        start_year = min(years)
        end_year = max(years)
        start_date = f"{start_year}-01-01"
        end_date = f"{end_year + 1}-01-01"

        # Filter collections by date
        filtered_pol   = pollutant_col.filterDate(start_date, end_date)
        filtered_era5  = era5_col.filterDate(start_date, end_date)
        filtered_merra2 = merra2_col.filterDate(start_date, end_date)

        pol_data    = filtered_pol.getRegion(point, 11132).getInfo()
        era5_data   = filtered_era5.getRegion(point, 11132).getInfo()
        merra2_data = filtered_merra2.getRegion(point, 27750).getInfo()  # MERRA-2 native ~0.5°x0.625°
        
        elev_data = elev_img.reduceRegion(ee.Reducer.mean(), point, 1000).getInfo()
        try:
            pop_data = pop_img.reduceRegion(ee.Reducer.mean(), point, 1000).getInfo()
            pop_val = pop_data.get('population', 0)
        except Exception:
            pop_val = 0

        elev_val = elev_data.get('elevation', 0)

        # Helper to process 'time' column into year-month string safely
        def get_ym_from_time(t_ms):
            if not t_ms: return None, None
            # GEE returns time in milliseconds
            dt = datetime.datetime.fromtimestamp(t_ms / 1000.0, tz=datetime.timezone.utc)
            return f"{dt.year}-{dt.month:02d}", dt

        # Process Pollution Data
        pol_headers = pol_data[0]
        pol_rows = pol_data[1:]
        pol_monthly = {}
        
        val_idx = pol_headers.index(pollutant_col.first().bandNames().getInfo()[0])
        cld_idx = pol_headers.index('cloud_fraction')
        time_idx = pol_headers.index('time')

        for row in pol_rows:
            ym, _ = get_ym_from_time(row[time_idx])
            if not ym: continue
            
            val = row[val_idx]
            cld = row[cld_idx]
            if val is None or cld is None: continue
            
            if ym not in pol_monthly:
                pol_monthly[ym] = {'val': [], 'cld': []}
            pol_monthly[ym]['val'].append(val)
            pol_monthly[ym]['cld'].append(cld)

        # Process ERA5 Weather Data
        era5_headers = era5_data[0]
        era5_rows = era5_data[1:]
        era5_monthly = {}
        
        t_idx = era5_headers.index('mean_2m_air_temperature')
        u_idx = era5_headers.index('u_component_of_wind_10m')
        v_idx = era5_headers.index('v_component_of_wind_10m')
        time_idx = era5_headers.index('time')
        
        for row in era5_rows:
            ym, dt = get_ym_from_time(row[time_idx])
            if not ym: continue
            
            t, u, v = row[t_idx], row[u_idx], row[v_idx]
            if None in (t, u, v): continue
            
            if ym not in era5_monthly:
                era5_monthly[ym] = {'t': [], 'u': [], 'v': [], 'doy': []}
            era5_monthly[ym]['t'].append(t)
            era5_monthly[ym]['u'].append(u)
            era5_monthly[ym]['v'].append(v)
            era5_monthly[ym]['doy'].append(dt.timetuple().tm_yday)

        # Process MERRA-2 PBLH — real planetary boundary layer height in metres
        merra2_headers = merra2_data[0]
        merra2_rows    = merra2_data[1:]
        merra2_monthly = {}

        pblh_idx = merra2_headers.index('PBLH')
        time_idx = merra2_headers.index('time')

        for row in merra2_rows:
            ym, _ = get_ym_from_time(row[time_idx])
            if not ym: continue

            pblh = row[pblh_idx]
            if pblh is None: continue

            if ym not in merra2_monthly:
                merra2_monthly[ym] = {'pbl': []}
            merra2_monthly[ym]['pbl'].append(pblh)

        # Combine into final monthly results
        monthly_results = []
        for ym in pol_monthly.keys():
            if ym not in era5_monthly: continue

            # Use real MERRA-2 PBLH; fallback to 1000m if unavailable for that month
            if ym in merra2_monthly and len(merra2_monthly[ym]['pbl']) > 0:
                avg_pbl = sum(merra2_monthly[ym]['pbl']) / len(merra2_monthly[ym]['pbl'])
            else:
                avg_pbl = 1000.0
            
            avg_val = sum(pol_monthly[ym]['val']) / len(pol_monthly[ym]['val'])
            avg_cld = sum(pol_monthly[ym]['cld']) / len(pol_monthly[ym]['cld'])
            
            avg_t = sum(era5_monthly[ym]['t']) / len(era5_monthly[ym]['t'])
            avg_u = sum(era5_monthly[ym]['u']) / len(era5_monthly[ym]['u'])
            avg_v = sum(era5_monthly[ym]['v']) / len(era5_monthly[ym]['v'])
            
            # Median DOY
            sorted_doy = sorted(era5_monthly[ym]['doy'])
            med_doy = sorted_doy[len(sorted_doy)//2] if sorted_doy else 180
            
            year, month = map(int, ym.split('-'))
            
            row_dict = {
                'ym': pd.Period(ym, freq='M'),
                'temp': avg_t,
                'cld': avg_cld,
                'u': avg_u,
                'v': avg_v,
                'pbl': avg_pbl,
                'elev': elev_val or 10.0,
                'pop': pop_val or 0.0,
                val_col: avg_val,
                'day_of_year': med_doy,
                'month': month,
                'year': year,
                'solar': 400.0  # default
            }
            monthly_results.append(row_dict)

        return monthly_results
