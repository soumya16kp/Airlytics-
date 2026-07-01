from base_extractor import HuggingFaceBaseAPI

class PM25HuggingFaceAPI(HuggingFaceBaseAPI):
    def __init__(self, hf_token=None):
        super().__init__(
            pollutant_name="pm25",
            hf_token=hf_token
        )
