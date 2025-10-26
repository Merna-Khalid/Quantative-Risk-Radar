import numpy as np
from .base_strategy import AnalysisStrategy

class BayesianStrategy(AnalysisStrategy):
    
    def analyze(self, signal):
        print("Running Bayesian strategy...")
        
        if not isinstance(signal, np.ndarray):
            signal = np.array(signal)
        
        signal = signal[~np.isnan(signal)]
        
        if len(signal) < 10:
            return {"risk_score": 0.5, "strategy": "bayesian", "warning": "Insufficient data"}
        
        volatility = np.std(signal) if len(signal) > 1 else 0.1
        mean_abs = np.mean(np.abs(signal))
        max_deviation = np.max(np.abs(signal))
        
        risk_score = min(1.0, (volatility * 0.4 + mean_abs * 0.3 + max_deviation * 0.3))
        
        return {
            "risk_score": float(risk_score),
            "volatility": float(volatility),
            "mean_absolute": float(mean_abs),
            "max_deviation": float(max_deviation),
            "strategy": "bayesian"
        }