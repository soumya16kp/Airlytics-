from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from .views import (
    RegisterView, DistrictViewSet, TownViewSet, CarbonEmissionViewSet,
    UserProfileView, UserView, MapDataView, PredictCOView, PredictCOAtCoordsView
)

router = DefaultRouter()
router.register(r'districts', DistrictViewSet)
router.register(r'towns', TownViewSet)
router.register(r'emissions', CarbonEmissionViewSet)

urlpatterns = [
    path('user/',              UserView.as_view(),                name='user'),
    path('register/',          RegisterView.as_view(),             name='register'),
    path('login/',             TokenObtainPairView.as_view(),     name='token_obtain_pair'),
    path('token/refresh/',     TokenRefreshView.as_view(),        name='token_refresh'),
    path('profile/',           UserProfileView.as_view(),         name='profile'),
    path('map-data/',          MapDataView.as_view(),             name='map-data'),
    path('predict-co/',        PredictCOView.as_view(),           name='predict-co'),
    path('predict-co-at/',     PredictCOAtCoordsView.as_view(),   name='predict-co-at'),  # drag-to-predict
    path('',                   include(router.urls)),
]
