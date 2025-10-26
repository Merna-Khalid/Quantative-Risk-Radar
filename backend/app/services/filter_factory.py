from app.services.filters.butterworth import ButterworthFilter
from app.services.filters.wavelet import WaveletFilter

class FilterFactory:
    @staticmethod
    def create_filter(filter_type: str):
        filters = {
            "butterworth": ButterworthFilter,
            "wavelet": WaveletFilter
        }
        if filter_type not in filters:
            raise ValueError(f"Unknown filter type: {filter_type}")
        return filters[filter_type]()