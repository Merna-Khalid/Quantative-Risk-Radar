import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class VisualizationService:
    """
    Service to generate data for interactive risk visualization charts.
    Returns structured data that can be used with Plotly on the frontend.
    """
    
    def __init__(self):
        self.crisis_periods = {
            "Global Financial Crisis": ("2007-12-01", "2009-06-30"),
            "Eurozone Crisis": ("2010-04-01", "2012-12-31"), 
            "COVID-19 Crash": ("2020-02-01", "2020-04-30"),
            "2022 Inflation Shock": ("2022-01-01", "2022-12-31")
        }
    
    def generate_risk_cascade_data(self, risk_signals: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate structured data for risk cascade visualization.
        
        Returns:
            Dictionary with data for frontend Plotly charts
        """
        try:
            if risk_signals.empty:
                return {"error": "No risk signals data available"}
            
            # Calculate thresholds
            pca_threshold = risk_signals['Systemic_Score'].quantile(0.95)
            quantile_threshold = risk_signals['Quantile_Signal'].quantile(0.05)
            dcc_threshold = risk_signals['DCC_Corr'].quantile(0.95)
            har_threshold = 2.0  # Standard z-score threshold
            
            # Prepare main traces data
            traces = {
                "systemic_score": self._series_to_plotly_data(
                    risk_signals['Systemic_Score'], 
                    "Systemic Score (PCA + Credit)", 
                    "red"
                ),
                "quantile_signal": self._series_to_plotly_data(
                    risk_signals['Quantile_Signal'],
                    "5th Percentile Returns (HYG)",
                    "purple"
                ),
                "dcc_correlation": self._series_to_plotly_data(
                    risk_signals['DCC_Corr'],
                    "DCC Correlation (XLK vs XLF)", 
                    "darkorange"
                ),
                "har_excess_vol": self._series_to_plotly_data(
                    risk_signals['HAR_ExcessVol_Z'],
                    "HAR Excess Vol (z-score)",
                    "green"
                )
            }
            
            # Prepare threshold lines
            thresholds = {
                "pca_threshold": float(pca_threshold),
                "quantile_threshold": float(quantile_threshold),
                "dcc_threshold": float(dcc_threshold),
                "har_threshold": float(har_threshold)
            }
            
            # Prepare warning periods
            warning_periods = self._extract_warning_periods(risk_signals)
            
            # Prepare bootstrap exceedance markers
            exceedance_markers = self._extract_exceedance_markers(risk_signals)
            
            # Prepare crisis periods
            crisis_periods_formatted = self._format_crisis_periods()
            
            return {
                "traces": traces,
                "thresholds": thresholds,
                "warning_periods": warning_periods,
                "exceedance_markers": exceedance_markers,
                "crisis_periods": crisis_periods_formatted,
                "metadata": {
                    "date_range": {
                        "start": risk_signals.index[0].strftime('%Y-%m-%d'),
                        "end": risk_signals.index[-1].strftime('%Y-%m-%d')
                    },
                    "data_points": len(risk_signals),
                    "last_updated": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating risk cascade data: {e}")
            return {"error": str(e)}
    
    def _series_to_plotly_data(self, series: pd.Series, name: str, color: str) -> Dict[str, Any]:
        """Convert pandas Series to Plotly-ready data structure."""
        return {
            "x": series.index.strftime('%Y-%m-%d').tolist(),
            "y": series.fillna(0).tolist(),
            "name": name,
            "color": color,
            "type": "scatter",
            "mode": "lines"
        }
    
    def _extract_warning_periods(self, risk_signals: pd.DataFrame) -> List[Dict[str, str]]:
        """Extract warning periods from risk signals."""
        warning_periods = []
        
        if 'is_warning' not in risk_signals.columns:
            return warning_periods
            
        warning_starts = risk_signals[risk_signals['is_warning'].diff() == 1].index
        warning_ends = risk_signals[risk_signals['is_warning'].diff() == -1].index
        
        # Handle case where warning continues to the end
        if len(warning_starts) > len(warning_ends):
            warning_ends = warning_ends.append(pd.Index([risk_signals.index[-1]]))
        
        for start, end in zip(warning_starts, warning_ends):
            warning_periods.append({
                "start": start.strftime('%Y-%m-%d'),
                "end": end.strftime('%Y-%m-%d'),
                "color": "red",
                "opacity": 0.1
            })
        
        return warning_periods
    
    def _extract_exceedance_markers(self, risk_signals: pd.DataFrame) -> Dict[str, Any]:
        """Extract bootstrap exceedance markers."""
        if 'Corr_Exceeds_Bootstrap' not in risk_signals.columns:
            return {"x": [], "y": []}
            
        exceed_idx = risk_signals[risk_signals['Corr_Exceeds_Bootstrap'] == 1].index
        return {
            "x": exceed_idx.strftime('%Y-%m-%d').tolist(),
            "y": risk_signals.loc[exceed_idx, 'DCC_Corr'].tolist(),
            "name": "Corr Exceeds Bootstrap",
            "color": "black",
            "symbol": "x"
        }
    
    def _format_crisis_periods(self) -> List[Dict[str, Any]]:
        """Format crisis periods for frontend display."""
        crisis_periods_formatted = []
        for name, (start, end) in self.crisis_periods.items():
            crisis_periods_formatted.append({
                "name": name,
                "start": start,
                "end": end,
                "color": "gray",
                "opacity": 0.3
            })
        return crisis_periods_formatted
    
    def generate_signal_breakdown_data(self, risk_signals: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate data for individual signal breakdown visualization.
        """
        try:
            signals_data = {}
            
            # Individual signal traces
            signal_columns = ['Systemic_Score', 'Quantile_Signal', 'DCC_Corr', 'HAR_ExcessVol_Z']
            colors = ['red', 'purple', 'darkorange', 'green']
            
            for i, col in enumerate(signal_columns):
                if col in risk_signals.columns:
                    signals_data[col] = self._series_to_plotly_data(
                        risk_signals[col],
                        col.replace('_', ' ').title(),
                        colors[i]
                    )
            
            # Composite risk score if available
            if 'Composite_Risk_Score' in risk_signals.columns:
                signals_data['composite'] = self._series_to_plotly_data(
                    risk_signals['Composite_Risk_Score'],
                    "Composite Risk Score",
                    "blue"
                )
            
            return {
                "signals": signals_data,
                "metadata": {
                    "available_signals": list(signals_data.keys()),
                    "date_range": {
                        "start": risk_signals.index[0].strftime('%Y-%m-%d'),
                        "end": risk_signals.index[-1].strftime('%Y-%m-%d')
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating signal breakdown data: {e}")
            return {"error": str(e)}
    
    def generate_correlation_matrix_data(self, correlation_matrix: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate data for correlation matrix heatmap.
        """
        try:
            return {
                "z": correlation_matrix.values.tolist(),
                "x": correlation_matrix.columns.tolist(),
                "y": correlation_matrix.index.tolist(),
                "type": "heatmap",
                "colorscale": "RdBu",
                "zmin": -1,
                "zmax": 1
            }
        except Exception as e:
            logger.error(f"Error generating correlation matrix data: {e}")
            return {"error": str(e)}
    
    def generate_volatility_data(self, volatility_series: pd.Series) -> Dict[str, Any]:
        """
        Generate data for volatility visualization.
        """
        try:
            return {
                "volatility": self._series_to_plotly_data(
                    volatility_series,
                    "Conditional Volatility",
                    "blue"
                ),
                "metadata": {
                    "mean_volatility": float(volatility_series.mean()),
                    "max_volatility": float(volatility_series.max()),
                    "current_volatility": float(volatility_series.iloc[-1]) if len(volatility_series) > 0 else 0.0
                }
            }
        except Exception as e:
            logger.error(f"Error generating volatility data: {e}")
            return {"error": str(e)}
    
    def generate_systemic_risk_data(self, systemic_df: pd.DataFrame, pca_meta: dict) -> Dict[str, Any]:
        """
        Generate specialized systemic risk visualization data.
        """
        try:
            return {
                "components": {
                    "systemic": self._series_to_plotly_data(
                        systemic_df['Systemic'], "Systemic Risk", "red"
                    ),
                    "pca": self._series_to_plotly_data(
                        systemic_df['PCA'], "PCA Component", "blue" 
                    ),
                    "credit": self._series_to_plotly_data(
                        systemic_df['Credit'], "Credit Component", "green"
                    )
                },
                "thresholds": {
                    "systemic_alert": float(systemic_df['Systemic'].quantile(0.95)),
                    "pca_alert": float(systemic_df['PCA'].quantile(0.95)),
                    "credit_alert": float(systemic_df['Credit'].quantile(0.95))
                },
                "metadata": pca_meta
            }
        except Exception as e:
            logger.error(f"Error generating systemic risk data: {e}")
            return {"error": str(e)}

# Singleton instance
visualization_service = VisualizationService()