from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from compare_service import get_comparison_data

class CompareView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        pollutant = request.query_params.get('pollutant', 'no2').lower().strip()
        year_str = request.query_params.get('year', '2024')
        mode = request.query_params.get('mode', 'monthly').lower().strip()
        page = int(request.query_params.get('page', 1))
        month = int(request.query_params.get('month', 1))

        if not lat or not lon:
            return Response({'error': 'lat and lon are required parameters.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            return Response({'error': 'lat and lon must be valid numbers.'}, status=status.HTTP_400_BAD_REQUEST)

        if year_str != 'all':
            try:
                year = int(year_str)
                if not (2020 <= year <= 2026):
                    return Response({'error': 'year must be between 2020 and 2026, or "all".'}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({'error': 'year must be a valid integer or "all".'}, status=status.HTTP_400_BAD_REQUEST)

        if pollutant not in ['co', 'no2', 'so2', 'o3', 'pm25']:
            return Response({'error': f'Unsupported pollutant: {pollutant}'}, status=status.HTTP_400_BAD_REQUEST)

        if mode not in ['monthly', 'weekly', 'daily', 'yearly']:
            return Response({'error': f'Unsupported mode: {mode}'}, status=status.HTTP_400_BAD_REQUEST)

        result = get_comparison_data(lat, lon, pollutant, year_str, mode, page, month)
        if result.get('error'):
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)
