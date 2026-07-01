from base_extractor import HuggingFaceBaseAPI

class O3HuggingFaceAPI(HuggingFaceBaseAPI):
    def __init__(self, hf_token=None):
        super().__init__(
            pollutant_name="o3",
            hf_token=hf_token
        )
