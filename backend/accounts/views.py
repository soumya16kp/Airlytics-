from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.models import User
import datetime

from .models import District, Town, CarbonEmission, UserProfile
from .serializers import (
    UserSerializer, DistrictSerializer, TownSerializer,
    CarbonEmissionSerializer, UserProfileSerializer, RegisterSerializer
)

# ── Live CO predictor (loads model + raster once at startup) ──────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from co_predictor import co_predictor


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


def format_prediction_response(result, extra_info=None):
    """Formats the raw result from co_predictor into a unified API response."""
    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    timeline = []

    # Historical
    for year, values in sorted(result['monthly_history'].items()):
        for i, val in enumerate(values):
            timeline.append({
                'year': year, 'month': i + 1,
                'monthName': months[i],
                'label': f"{months[i]} {year}",
                'value': val,
                'is_prediction': False,
            })

    # Future 2026
    for i, val in enumerate(result['monthly_2026']):
        timeline.append({
            'year': 2026, 'month': i + 1,
            'monthName': months[i],
            'label': f"{months[i]} 2026",
            'value': val,
            'is_prediction': True,
        })

    resp = {
        'base_co_2026': result['base_co_2026'],
        'timeline':     timeline,
    }
    if extra_info:
        resp.update(extra_info)
    return resp


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
            return Response(
                {'error': f"Town '{town.name}' has no coordinates."}, status=422
            )

        result = co_predictor.predict_for_town(town)
        if result.get('error'):
            return Response({'error': result['error']}, status=500)

        data = format_prediction_response(result, {
            'town_id':      town.id,
            'town_name':    town.name,
            'district':     town.district.name,
            'latitude':     town.latitude,
            'longitude':    town.longitude,
        })
        return Response(data)


class MapDataView(APIView):
    """
    GET /api/map-data/

    Returns live model CO predictions for all towns that have coordinates.
    Used by the regional heatmap.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        towns = Town.objects.select_related('district').filter(
            latitude__isnull=False, longitude__isnull=False
        )

        data = []
        for town in towns:
            result = co_predictor.predict_for_town(town)
            if result.get('error'):
                data.append({
                    'id':       town.id,
                    'name':     town.name,
                    'district': town.district.name,
                    'coords':   [town.latitude, town.longitude],
                    'value':    None,
                    'error':    result['error'],
                })
            else:
                # Use March 2026 (month index 2) as "current" value
                current_co = result['monthly_2026'][2]
                data.append({
                    'id':       town.id,
                    'name':     town.name,
                    'district': town.district.name,
                    'coords':   [town.latitude, town.longitude],
                    'value':    round(current_co, 6),
                    'error':    None,
                })

        return Response(data)


class PredictCOAtCoordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lon = float(request.query_params.get('lon'))
        except (TypeError, ValueError):
            return Response({'error': 'lat and lon must be valid numbers.'}, status=400)

        result = co_predictor.predict_at_coords(lat, lon)
        if result.get('error'):
            return Response({'error': result['error']}, status=422)

        data = format_prediction_response(result, {
            'latitude':  result['lat'],
            'longitude': result['lon'],
            'is_custom': True,
        })
        return Response(data)
