import os

import requests
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

OPENAQ_API_KEY = os.environ.get('OPENAQ_API_KEY', '')
OPENAQ_BASE_URL = 'https://api.openaq.org/v3'

class OpenAQProxyLocationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not OPENAQ_API_KEY:
            return Response(
                {'error': 'OPENAQ_API_KEY is not configured on the server. Please add it to your .env file.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        bbox = request.query_params.get('bbox')
        limit = request.query_params.get('limit', 30)

        params = {}
        if bbox:
            params['bbox'] = bbox
        if limit:
            params['limit'] = limit

        headers = {
            'X-API-Key': OPENAQ_API_KEY
        }

        try:
            resp = requests.get(f"{OPENAQ_BASE_URL}/locations", params=params, headers=headers, timeout=10)
            return Response(resp.json(), status=resp.status_code)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OpenAQProxyLatestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, location_id):
        if not OPENAQ_API_KEY:
            return Response(
                {'error': 'OPENAQ_API_KEY is not configured on the server. Please add it to your .env file.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        headers = {
            'X-API-Key': OPENAQ_API_KEY
        }

        try:
            resp = requests.get(f"{OPENAQ_BASE_URL}/locations/{location_id}/latest", headers=headers, timeout=10)
            return Response(resp.json(), status=resp.status_code)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
