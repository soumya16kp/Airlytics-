from base_extractor import HuggingFaceBaseAPI

class NO2HuggingFaceAPI(HuggingFaceBaseAPI):
    def __init__(self, hf_token=None):
        super().__init__(
            pollutant_name="no2",
            hf_token=hf_token
        )
