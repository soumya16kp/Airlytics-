from .auth import UserView, RegisterView, UserProfileView
from .co import PredictCOView, PredictCOAtCoordsView, MapDataView
from .no2 import PredictNO2View, PredictNO2AtCoordsView, MapDataNO2View
from .o3 import PredictO3View, PredictO3AtCoordsView, MapDataO3View
from .so2 import PredictSO2View, PredictSO2AtCoordsView, MapDataSO2View
from .pm25 import PredictPM25View, PredictPM25AtCoordsView, MapDataPM25View
from .ai import PollutionInsightView
from .openaq import OpenAQProxyLocationsView, OpenAQProxyLatestView
from .gee import GEETileView
from .compare import CompareView

__all__ = [
    'RegisterView', 'UserProfileView', 'UserView',
    'MapDataView', 'PredictCOView', 'PredictCOAtCoordsView',
    'PredictNO2View', 'MapDataNO2View', 'PredictNO2AtCoordsView',
    'PredictO3View', 'PredictO3AtCoordsView', 'MapDataO3View',
    'PredictSO2View', 'PredictSO2AtCoordsView', 'MapDataSO2View',
    'PredictPM25View', 'PredictPM25AtCoordsView', 'MapDataPM25View',
    'PollutionInsightView',
    'OpenAQProxyLocationsView', 'OpenAQProxyLatestView',
    'GEETileView',
    'CompareView',
]
