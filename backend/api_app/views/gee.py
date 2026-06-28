import os
import json
import datetime
try:
    import ee
except ImportError:
    ee = None
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


GEE_INITIALIZATION_ERROR = None


def get_gee_credentials():
    if ee is None:
        raise RuntimeError('earthengine-api is not installed')

    key_json = os.environ.get('GEE_SERVICE_ACCOUNT_JSON')
    key_path = os.environ.get('GEE_SERVICE_ACCOUNT_KEY_PATH')

    if key_json:
        key_data = json.loads(key_json)
        email = os.environ.get('GEE_SERVICE_ACCOUNT_EMAIL') or key_data['client_email']
        return ee.ServiceAccountCredentials(email, key_data=json.dumps(key_data))

    if key_path:
        with open(key_path) as f:
            key_data = json.load(f)
        email = os.environ.get('GEE_SERVICE_ACCOUNT_EMAIL') or key_data['client_email']
        return ee.ServiceAccountCredentials(email, key_path)

    raise RuntimeError('Set GEE_SERVICE_ACCOUNT_JSON or GEE_SERVICE_ACCOUNT_KEY_PATH')


# Initialize GEE once at startup

def initialize_ee():
    global GEE_INITIALIZATION_ERROR
    try:
        credentials = get_gee_credentials()
        ee.Initialize(credentials)
        GEE_INITIALIZATION_ERROR = None
        print('Earth Engine initialized successfully in gee.py')
    except Exception as e:
        GEE_INITIALIZATION_ERROR = str(e)
        print(f'Error initializing Earth Engine at startup: {e}')


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
        if GEE_INITIALIZATION_ERROR:
            return Response({'error': GEE_INITIALIZATION_ERROR}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        pollutant = request.query_params.get('pollutant', 'no2').lower()
        if pollutant not in POLLUTANT_CONFIGS:
            return Response({'error': f'Unsupported pollutant: {pollutant}'}, status=status.HTTP_400_BAD_REQUEST)

        config = POLLUTANT_CONFIGS[pollutant]

        try:
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=14)

            col = ee.ImageCollection(config['collection']) \
                .filterDate(start_date.strftime('%Y-%m-%d'), (end_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')) \
                .select(config['band'])

            if col.size().getInfo() == 0:
                start_date = end_date - datetime.timedelta(days=30)
                col = ee.ImageCollection(config['collection']) \
                    .filterDate(start_date.strftime('%Y-%m-%d'), (end_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')) \
                    .select(config['band'])

            image = col.mean()
            india = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017').filter(ee.Filter.eq('country_na', 'India'))
            image_clipped = image.clip(india)
            map_id_dict = image_clipped.getMapId(config['vis'])

            return Response({
                'pollutant': pollutant,
                'tile_url': map_id_dict['tile_fetcher'].url_format,
                'vis_params': config['vis']
            })

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)