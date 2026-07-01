from base_extractor import HuggingFaceBaseAPI

class COHuggingFaceAPI(HuggingFaceBaseAPI):
    def __init__(self, hf_token=None):
        super().__init__(
            pollutant_name="co",
            hf_token=hf_token
        )
