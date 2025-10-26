from abc import ABC, abstractmethod
from typing import Dict, Any

class AnalysisStrategy(ABC):
    """Base class for all analysis strategies."""
    
    @abstractmethod
    def analyze(self, signal) -> Dict[str, Any]:
        """Analyze signal and return risk metrics."""
        pass