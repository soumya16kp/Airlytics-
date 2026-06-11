from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from .views import (
    RegisterView, UserProfileView, UserView,
    # CO
    MapDataView, PredictCOView, PredictCOAtCoordsView,
    # NO2
    PredictNO2View, MapDataNO2View, PredictNO2AtCoordsView,
    # O3
    PredictO3View, PredictO3AtCoordsView, MapDataO3View,
    # SO2
    PredictSO2View, PredictSO2AtCoordsView, MapDataSO2View,
    # AI
    PollutionInsightView,
)

urlpatterns = [
    path('user/',              UserView.as_view(),                name='user'),
    path('register/',          RegisterView.as_view(),             name='register'),
    path('login/',             TokenObtainPairView.as_view(),     name='token_obtain_pair'),
    path('token/refresh/',     TokenRefreshView.as_view(),        name='token_refresh'),
    path('profile/',           UserProfileView.as_view(),         name='profile'),

    # CO endpoints
    path('map-data/',          MapDataView.as_view(),             name='map-data'),
    path('predict-co/',        PredictCOView.as_view(),           name='predict-co'),
    path('predict-co-at/',     PredictCOAtCoordsView.as_view(),   name='predict-co-at'),

    # NO2 endpoints
    path('predict-no2/',       PredictNO2View.as_view(),          name='predict-no2'),
    path('predict-no2-at/',    PredictNO2AtCoordsView.as_view(),  name='predict-no2-at'),
    path('map-data-no2/',      MapDataNO2View.as_view(),          name='map-data-no2'),

    # O3 endpoints
    path('predict-o3/',        PredictO3View.as_view(),           name='predict-o3'),
    path('predict-o3-at/',     PredictO3AtCoordsView.as_view(),   name='predict-o3-at'),
    path('map-data-o3/',       MapDataO3View.as_view(),           name='map-data-o3'),

    # SO2 endpoints
    path('predict-so2/',       PredictSO2View.as_view(),          name='predict-so2'),
    path('predict-so2-at/',    PredictSO2AtCoordsView.as_view(),  name='predict-so2-at'),
    path('map-data-so2/',      MapDataSO2View.as_view(),          name='map-data-so2'),
    # AI Insight
    path('pollution-insight/', PollutionInsightView.as_view(),    name='pollution-insight'),
]
