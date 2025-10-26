import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def get_historical_risk_by_range(start_date: str = None, end_date: str = None, days: int = None):
    """
    Generate historical risk data for the frontend with flexible date ranges.
    
    Args:
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format  
        days: Number of days from end_date backwards (alternative to start_date)
    """
    try:
        # Determine date range
        if end_date:
            end_date = pd.to_datetime(end_date)
        else:
            end_date = datetime.now()
            
        if start_date:
            start_date = pd.to_datetime(start_date)
        elif days:
            start_date = end_date - timedelta(days=days)
        else:
            # Default to 180 days if nothing specified
            start_date = end_date - timedelta(days=180)
        
        # Ensure start_date is before end_date
        if start_date >= end_date:
            start_date = end_date - timedelta(days=1)
        
        # Generate business days only (exclude weekends)
        dates = pd.date_range(start=start_date, end=end_date, freq='B')  # 'B' = business days
        
        risk_data = []
        
        for i, date in enumerate(dates):
            time_factor = i / 30  # Monthly cycles
            
            base_risk = 0.3 + 0.4 * np.sin(time_factor)
            market_shock = 0.8 if i % 120 == 0 else 0.0
            noise = np.random.normal(0, 0.15)
            
            systemic_risk = max(-2, min(2, base_risk + market_shock + noise))
            pca_signal = systemic_risk * 0.9 + np.random.normal(0, 0.1)
            credit_signal = systemic_risk * 0.7 + np.random.normal(0, 0.12)
            
            if systemic_risk >= 0.5:
                regime = "RED"
                interpretation = "High systemic risk detected. Monitor markets closely."
            elif systemic_risk > 0.0:
                regime = "YELLOW" 
                interpretation = "Elevated risk levels. Increased vigilance recommended."
            else:
                regime = "GREEN"
                interpretation = "Normal market conditions. Standard monitoring procedures."
            
            risk_data.append({
                "date": date.strftime('%Y-%m-%d'),
                "systemic_risk": float(systemic_risk), 
                "pca_signal_score": float(pca_signal),
                "credit_signal_score": float(credit_signal),
                "market_regime": regime,
                "risk_interpretation": interpretation
            })
        
        logger.info(f"Generated {len(risk_data)} trading days of risk data from {start_date.date()} to {end_date.date()}")
        return pd.DataFrame(risk_data)
        
    except Exception as e:
        logger.error(f"Error generating historical risk data: {e}")
        return pd.DataFrame()

def get_historical_risk(days=180):
    """Backward compatibility wrapper"""
    return get_historical_risk_by_range(days=days)