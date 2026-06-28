from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from predictor.o3_predictor import o3_predictor
from .utils import (
    format_prediction_response, _get_range, _get_overrides, TOWN_COORDS
)

class PredictO3View(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        lat = profile.latitude
        lon = profile.longitude

        if lat is None or lon is None:
            return Response({'error': 'Location coordinates (latitude and longitude) must be set in User Profile.'}, status=400)

        range_str = _get_range(request)
        overrides = _get_overrides(request)
        result = o3_predictor.predict_at_coords(lat, lon, range_str, overrides=overrides)
        if result.get('error'):
            return Response({'error': result['error']}, status=422)

        data = format_prediction_response(result, {
            'latitude': lat, 'longitude': lon,
        }, coords=(lat, lon))
        return Response(data)


class PredictO3AtCoordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lon = float(request.query_params.get('lon'))
        except (TypeError, ValueError):
            return Response({'error': 'lat and lon must be valid numbers.'}, status=400)

        range_str = _get_range(request)
        overrides = _get_overrides(request)
        result = o3_predictor.predict_at_coords(lat, lon, range_str, overrides=overrides)
        if result.get('error'):
            return Response({'error': result['error']}, status=422)

        data = format_prediction_response(result, {
            'latitude': result['lat'], 'longitude': result['lon'],
            'is_custom': True,
        }, coords=(lat, lon))
        return Response(data)


class MapDataO3View(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = []
        for name, info in TOWN_COORDS.items():
            lat, lon, district, town_id = info
            result = o3_predictor.predict_at_coords(lat, lon, '1Y')
            if result.get('error'):
                data.append({
                    'id': town_id, 'name': name,
                    'district': district,
                    'coords': [lat, lon],
                    'value': None, 'error': result['error'],
                })
            else:
                data.append({
                    'id': town_id, 'name': name,
                    'district': district,
                    'coords': [lat, lon],
                    'value': round(result['base_value_2026'], 6),
                    'error': None,
                })
        return Response(data)
