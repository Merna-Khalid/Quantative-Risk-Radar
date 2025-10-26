from .base_filter import BaseFilter

class WaveletFilter(BaseFilter):
    def apply(self, signal):
        print("Applying Wavelet filter...")
        return [s * 0.8 for s in signal]
