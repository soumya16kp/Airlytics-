import os
import json
import datetime
import ee
from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

# Resolve the service key path relative to this file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "..", "frontend", "asymtotes-05b94e2a6039.json"))

# Initialize GEE once at startup
def initialize_ee():
    try:
        with open(KEY_PATH) as f:
            key_data = json.load(f)
        email = key_data['client_email']
        credentials = ee.ServiceAccountCredentials(email, KEY_PATH)
        ee.Initialize(credentials)
        print("Earth Engine initialized successfully in gee.py")
    except Exception as e:
        print(f"Error initializing Earth Engine at startup: {e}")

initialize_ee()

POLLUTANT_CONFIGS = {
    'no2': {
        'collection': 'COPERNICUS/S5P/NRTI/L3_NO2',
        'band': 'NO2_column_number_density',
        'vis': {
            'min': 0.0,
            'max': 0.0002,
            'palette': ['0f766e', '22c55e', 'facc15', 'f97316', 'dc2626']
        }
    },
    'so2': {
        'collection': 'COPERNICUS/S5P/NRTI/L3_SO2',
        'band': 'SO2_column_number_density',
        'vis': {
            'min': 0.0,
            'max': 0.001,
            'palette': ['0891b2', '22c55e', 'eab308', 'f97316', 'b91c1c']
        }
    },
    'co': {
        'collection': 'COPERNICUS/S5P/NRTI/L3_CO',
        'band': 'CO_column_number_density',
        'vis': {
            'min': 0.0,
            'max': 0.05,
            'palette': ['0284c7', '22c55e', 'f59e0b', 'ea580c', 'dc2626']
        }
    },
    'o3': {
        'collection': 'COPERNICUS/S5P/NRTI/L3_O3',
        'band': 'O3_column_number_density',
        'vis': {
            'min': 0.1,
            'max': 0.15,
            'palette': ['2563eb', '06b6d4', '22c55e', 'f59e0b', 'ef4444']
        }
    },
    'ch4': {
        'collection': 'COPERNICUS/S5P/OFFL/L3_CH4',
        'band': 'CH4_column_volume_mixing_ratio_dry_air',
        'vis': {
            'min': 1750.0,
            'max': 1900.0,
            'palette': ['4f46e5', '06b6d4', '10b981', 'f59e0b', 'ef4444']
        }
    }
}

class GEETileView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        pollutant = request.query_params.get('pollutant', 'no2').lower()
        if pollutant not in POLLUTANT_CONFIGS:
            return Response({'error': f'Unsupported pollutant: {pollutant}'}, status=status.HTTP_400_BAD_REQUEST)

        config = POLLUTANT_CONFIGS[pollutant]
        
        try:
            # Get date range: last 14 days to ensure coverage

            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=14)
            
            # Load collection
            col = ee.ImageCollection(config['collection']) \
                .filterDate(start_date.strftime('%Y-%m-%d'), (end_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')) \
                .select(config['band'])

            # Fallback if 14 days returns no images (just load last 30 days)
            if col.size().getInfo() == 0:
                start_date = end_date - datetime.timedelta(days=30)
                col = ee.ImageCollection(config['collection']) \
                    .filterDate(start_date.strftime('%Y-%m-%d'), (end_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')) \
                    .select(config['band'])

            image = col.mean()

            # Clip to India boundary
            india = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq('country_na', 'India'))
            image_clipped = image.clip(india)

            # Get Map ID for Leaflet TileLayer
            map_id_dict = image_clipped.getMapId(config['vis'])
            tile_url = map_id_dict['tile_fetcher'].url_format

            return Response({
                'pollutant': pollutant,
                'tile_url': tile_url,
                'vis_params': config['vis']
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
