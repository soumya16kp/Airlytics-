import requests
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

OPENAQ_API_KEY = '7df3613a1cd7ef856e545d699316b4f907d45e88246cde6a7932a27895a33007'
OPENAQ_BASE_URL = 'https://api.openaq.org/v3'

class OpenAQProxyLocationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
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
        headers = {
            'X-API-Key': OPENAQ_API_KEY
        }

        try:
            resp = requests.get(f"{OPENAQ_BASE_URL}/locations/{location_id}/latest", headers=headers, timeout=10)
            return Response(resp.json(), status=resp.status_code)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
