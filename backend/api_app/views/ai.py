from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from ai_service import get_pollution_insight

class PollutionInsightView(APIView):
    """Provides dynamic AI-generated health advice using Gemini."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        pollutant = request.query_params.get('pollutant')
        value = request.query_params.get('value')
        unit = request.query_params.get('unit')
        status_label = request.query_params.get('status')
        question = request.query_params.get('question')

        if not all([pollutant, value, unit, status_label]):
            return Response({'error': 'Missing required parameters.'}, status=400)

        insight = get_pollution_insight(pollutant, value, unit, status_label, question)
        
        if not insight:
            return Response({
                'insight': "AI integration in progress. Please refer to standard WHO safety guidelines.",
                'is_ai': False
            })

        return Response({
            'insight': insight,
            'is_ai': True
        })
