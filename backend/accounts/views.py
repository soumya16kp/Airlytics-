from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.models import User

from .models import District, Town, CarbonEmission, UserProfile
from .serializers import (
    UserSerializer, DistrictSerializer, TownSerializer,
    CarbonEmissionSerializer, UserProfileSerializer, RegisterSerializer
)

# ── Live predictors (loaded once at startup) ─────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from co_predictor import co_predictor
from no2_predictor import no2_predictor
from o3_predictor import o3_predictor
from so2_predictor import so2_predictor
from weather_service import get_live_weather


class UserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer


class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.all()
    serializer_class = DistrictSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class TownViewSet(viewsets.ModelViewSet):
    queryset = Town.objects.all()
    serializer_class = TownSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        district_id = self.request.query_params.get('district')
        if district_id:
            return Town.objects.filter(district_id=district_id)
        return Town.objects.all()


class CarbonEmissionViewSet(viewsets.ModelViewSet):
    queryset = CarbonEmission.objects.all()
    serializer_class = CarbonEmissionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        town_id = self.request.query_params.get('town')
        if town_id:
            return CarbonEmission.objects.filter(town_id=town_id)
        return CarbonEmission.objects.all()


class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Shared response formatter ────────────────────────────────────────────────

def format_prediction_response(result, extra_info=None, coords=None):
    """Formats predictor output into a unified API response."""
    resp = {
        'base_value_2026': result.get('base_value_2026'),
        'timeline':        result.get('timeline', []),
        'range':           result.get('range', '1Y'),
        'pollutant':       result.get('pollutant', 'unknown'),
    }
    if 'comparison_table' in result:
        resp['comparison_table'] = result['comparison_table']
        
    if extra_info:
        resp.update(extra_info)
    # Attach live weather snapshot for the predicted location
    if coords:
        try:
            resp['weather_snapshot'] = get_live_weather(coords[0], coords[1])
            resp['weather_synced'] = True
        except Exception:
            resp['weather_snapshot'] = None
            resp['weather_synced'] = False
    return resp


VALID_RANGES = {'1D', '1W', '1M', '3M', '6M', '1Y', 'H1M', 'H3M', 'H1Y', 'H3Y', 'H5Y'}

def _get_range(request):
    """Extract and validate the range query parameter."""
    r = request.query_params.get('range', '1Y').upper()
    return r if r in VALID_RANGES else '1Y'


# ══════════════════════════════════════════════════════════════════════════════
# CO VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class PredictCOView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        town_id = request.query_params.get('town')
        if not town_id:
            return Response({'error': 'town query param is required.'}, status=400)
        try:
            town = Town.objects.get(pk=town_id)
        except Town.DoesNotExist:
            return Response({'error': f'Town {town_id} not found.'}, status=404)
        if town.latitude is None or town.longitude is None:
            return Response({'error': f"Town '{town.name}' has no coordinates."}, status=422)

        range_str = _get_range(request)
        result = co_predictor.predict_for_town(town, range_str)
        if result.get('error'):
            return Response({'error': result['error']}, status=500)

        data = format_prediction_response(result, {
            'town_id': town.id, 'town_name': town.name,
            'district': town.district.name,
            'latitude': town.latitude, 'longitude': town.longitude,
        }, coords=(town.latitude, town.longitude))
        return Response(data)


class PredictCOAtCoordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lon = float(request.query_params.get('lon'))
        except (TypeError, ValueError):
            return Response({'error': 'lat and lon must be valid numbers.'}, status=400)

        range_str = _get_range(request)
        result = co_predictor.predict_at_coords(lat, lon, range_str)
        if result.get('error'):
            return Response({'error': result['error']}, status=422)

        data = format_prediction_response(result, {
            'latitude': result['lat'], 'longitude': result['lon'],
            'is_custom': True,
        }, coords=(lat, lon))
        return Response(data)


class MapDataView(APIView):
    """Returns live CO predictions for all towns (heatmap)."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        towns = Town.objects.select_related('district').filter(
            latitude__isnull=False, longitude__isnull=False
        )
        data = []
        for town in towns:
            result = co_predictor.predict_for_town(town, '1Y')
            if result.get('error'):
                data.append({
                    'id': town.id, 'name': town.name,
                    'district': town.district.name,
                    'coords': [town.latitude, town.longitude],
                    'value': None, 'error': result['error'],
                })
            else:
                # Use the base averaged value
                data.append({
                    'id': town.id, 'name': town.name,
                    'district': town.district.name,
                    'coords': [town.latitude, town.longitude],
                    'value': round(result['base_value_2026'], 6),
                    'error': None,
                })
        return Response(data)


# ══════════════════════════════════════════════════════════════════════════════
# NO2 VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class PredictNO2View(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        town_id = request.query_params.get('town')
        if not town_id:
            return Response({'error': 'town query param is required.'}, status=400)
        try:
            town = Town.objects.get(pk=town_id)
        except Town.DoesNotExist:
            return Response({'error': f'Town {town_id} not found.'}, status=404)
        if town.latitude is None or town.longitude is None:
            return Response({'error': f"Town '{town.name}' has no coordinates."}, status=422)

        range_str = _get_range(request)
        result = no2_predictor.predict_for_town(town, range_str)
        if result.get('error'):
            return Response({'error': result['error']}, status=500)

        data = format_prediction_response(result, {
            'town_id': town.id, 'town_name': town.name,
            'district': town.district.name,
            'latitude': town.latitude, 'longitude': town.longitude,
        }, coords=(town.latitude, town.longitude))
        return Response(data)


class PredictNO2AtCoordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lon = float(request.query_params.get('lon'))
        except (TypeError, ValueError):
            return Response({'error': 'lat and lon must be valid numbers.'}, status=400)

        range_str = _get_range(request)
        result = no2_predictor.predict_at_coords(lat, lon, range_str)
        if result.get('error'):
            return Response({'error': result['error']}, status=422)

        data = format_prediction_response(result, {
            'latitude': result['lat'], 'longitude': result['lon'],
            'is_custom': True,
        }, coords=(lat, lon))
        return Response(data)


class MapDataNO2View(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        towns = Town.objects.select_related('district').filter(
            latitude__isnull=False, longitude__isnull=False
        )
        data = []
        for town in towns:
            result = no2_predictor.predict_for_town(town, '1Y')
            if result.get('error'):
                data.append({
                    'id': town.id, 'name': town.name,
                    'district': town.district.name,
                    'coords': [town.latitude, town.longitude],
                    'value': None, 'error': result['error'],
                })
            else:
                data.append({
                    'id': town.id, 'name': town.name,
                    'district': town.district.name,
                    'coords': [town.latitude, town.longitude],
                    'value': round(result['base_value_2026'], 6),
                    'error': None,
                })
        return Response(data)


# ══════════════════════════════════════════════════════════════════════════════
# O3 VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class PredictO3View(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        town_id = request.query_params.get('town')
        if not town_id:
            return Response({'error': 'town query param is required.'}, status=400)
        try:
            town = Town.objects.get(pk=town_id)
        except Town.DoesNotExist:
            return Response({'error': f'Town {town_id} not found.'}, status=404)
        if town.latitude is None or town.longitude is None:
            return Response({'error': f"Town '{town.name}' has no coordinates."}, status=422)

        range_str = _get_range(request)
        result = o3_predictor.predict_for_town(town, range_str)
        if result.get('error'):
            return Response({'error': result['error']}, status=500)

        data = format_prediction_response(result, {
            'town_id': town.id, 'town_name': town.name,
            'district': town.district.name,
            'latitude': town.latitude, 'longitude': town.longitude,
        }, coords=(town.latitude, town.longitude))
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
        result = o3_predictor.predict_at_coords(lat, lon, range_str)
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
        towns = Town.objects.select_related('district').filter(
            latitude__isnull=False, longitude__isnull=False
        )
        data = []
        for town in towns:
            result = o3_predictor.predict_for_town(town, '1Y')
            if result.get('error'):
                data.append({
                    'id': town.id, 'name': town.name,
                    'district': town.district.name,
                    'coords': [town.latitude, town.longitude],
                    'value': None, 'error': result['error'],
                })
            else:
                data.append({
                    'id': town.id, 'name': town.name,
                    'district': town.district.name,
                    'coords': [town.latitude, town.longitude],
                    'value': round(result['base_value_2026'], 6),
                    'error': None,
                })
        return Response(data)


# ══════════════════════════════════════════════════════════════════════════════
# SO2 VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class PredictSO2View(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        town_id = request.query_params.get('town')
        if not town_id:
            return Response({'error': 'town query param is required.'}, status=400)
        try:
            town = Town.objects.get(pk=town_id)
        except Town.DoesNotExist:
            return Response({'error': f'Town {town_id} not found.'}, status=404)
        if town.latitude is None or town.longitude is None:
            return Response({'error': f"Town '{town.name}' has no coordinates."}, status=422)

        range_str = _get_range(request)
        result = so2_predictor.predict_for_town(town, range_str)
        if result.get('error'):
            return Response({'error': result['error']}, status=500)

        data = format_prediction_response(result, {
            'town_id': town.id, 'town_name': town.name,
            'district': town.district.name,
            'latitude': town.latitude, 'longitude': town.longitude,
        }, coords=(town.latitude, town.longitude))
        return Response(data)


class PredictSO2AtCoordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lon = float(request.query_params.get('lon'))
        except (TypeError, ValueError):
            return Response({'error': 'lat and lon must be valid numbers.'}, status=400)

        range_str = _get_range(request)
        result = so2_predictor.predict_at_coords(lat, lon, range_str)
        if result.get('error'):
            return Response({'error': result['error']}, status=422)

        data = format_prediction_response(result, {
            'latitude': result['lat'], 'longitude': result['lon'],
            'is_custom': True,
        }, coords=(lat, lon))
        return Response(data)


class MapDataSO2View(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        towns = Town.objects.select_related('district').filter(
            latitude__isnull=False, longitude__isnull=False
        )
        data = []
        for town in towns:
            result = so2_predictor.predict_for_town(town, '1Y')
            if result.get('error'):
                data.append({
                    'id': town.id, 'name': town.name,
                    'district': town.district.name,
                    'coords': [town.latitude, town.longitude],
                    'value': None, 'error': result['error'],
                })
            else:
                data.append({
                    'id': town.id, 'name': town.name,
                    'district': town.district.name,
                    'coords': [town.latitude, town.longitude],
                    'value': round(result['base_value_2026'], 6),
                    'error': None,
                })
        return Response(data)
