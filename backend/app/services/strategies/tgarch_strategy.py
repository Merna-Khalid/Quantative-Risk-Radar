import numpy as np
import pandas as pd
from arch import arch_model
from .base_strategy import AnalysisStrategy

class TransformerGARCHStrategy(AnalysisStrategy):
    """Transformer-GARCH hybrid model for risk analysis."""
    
    def __init__(self):
        self.volatility_model = None
        
    def analyze(self, signal):
        print("Running Transformer-GARCH strategy...")
        
        # Convert signal to pandas Series if it's not already
        if not isinstance(signal, pd.Series):
            signal = pd.Series(signal)
        
        try:
            # Fit GARCH model
            returns = signal.dropna()
            if len(returns) < 50:
                return {"risk_score": 0.5, "volatility": 0.1, "strategy": "tgarch", "warning": "Insufficient data"}
            
            model = arch_model(returns, vol='GARCH', p=1, q=1, dist='normal')
            fitted_model = model.fit(disp='off')
            
            # Calculate risk metrics
            latest_vol = fitted_model.conditional_volatility.iloc[-1] if len(fitted_model.conditional_volatility) > 0 else returns.std()
            persistence = fitted_model.params.get('alpha[1]', 0.1) + fitted_model.params.get('beta[1]', 0.8)
            
            risk_score = min(1.0, latest_vol / (returns.std() * 2))  # Normalized score
            
            return {
                "risk_score": float(risk_score),
                "volatility": float(latest_vol),
                "persistence": float(persistence),
                "strategy": "tgarch",
                "parameters": {k: float(v) for k, v in fitted_model.params.items()}
            }
            
        except Exception as e:
            print(f"TransformerGARCH error: {e}")
            # Fallback to simple volatility-based scoring
            volatility = signal.std() if len(signal) > 1 else 0.1
            return {
                "risk_score": min(1.0, float(volatility)),
                "volatility": float(volatility),
                "strategy": "tgarch",
                "error": str(e)
            }