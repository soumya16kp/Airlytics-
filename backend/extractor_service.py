# backend/extractor_service.py
from co_extractor import COHuggingFaceAPI
from no2_extractor import NO2HuggingFaceAPI
from o3_extractor import O3HuggingFaceAPI
from so2_extractor import SO2HuggingFaceAPI
from pm25_extractor import PM25HuggingFaceAPI

# Singletons initialized once
co_api = COHuggingFaceAPI()
no2_api = NO2HuggingFaceAPI()
o3_api = O3HuggingFaceAPI()
so2_api = SO2HuggingFaceAPI()
pm25_api = PM25HuggingFaceAPI()
