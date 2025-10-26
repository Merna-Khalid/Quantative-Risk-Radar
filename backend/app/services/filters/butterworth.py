from .base_filter import BaseFilter

class ButterworthFilter(BaseFilter):
    def apply(self, signal):
        print("Applying Butterworth filter...")
        return [s * 0.9 for s in signal]
