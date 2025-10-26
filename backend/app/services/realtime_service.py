import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from app.core.cache import get_cached_data, set_cached_data
from app.services.risk_engine import RiskEngine

logger = logging.getLogger(__name__)

class RealtimeRiskService:
    def __init__(self):
        self.current_risk_metrics = {}
        self.last_computation_time = None
        self.computation_interval = 300  # 5 minutes
        self.is_computing = False
        self._computation_lock = asyncio.Lock()
        self._last_metrics_cache = None
        self._cache_timeout = 30  # 30 seconds for quick cache
        
    async def get_current_metrics(self):
        """Get current risk metrics with proper caching and locking."""
        current_time = datetime.utcnow()
        
        # Check quick cache (30 seconds)
        if (self._last_metrics_cache and 
            (current_time - self._last_metrics_cache.get('timestamp', datetime.min)).total_seconds() < self._cache_timeout):
            logger.debug("Returning cached metrics (30s cache)")
            return self._last_metrics_cache['metrics']
        
        # Check main computation cache (5 minutes)
        if (self.last_computation_time and 
            (current_time - self.last_computation_time).total_seconds() < self.computation_interval and
            self.current_risk_metrics):
            logger.debug("Returning cached risk metrics (5min cache)")
            self._last_metrics_cache = {
                'timestamp': current_time,
                'metrics': self.current_risk_metrics
            }
            return self.current_risk_metrics
        
        # Compute new metrics if needed
        async with self._computation_lock:
            if (self.last_computation_time and 
                (current_time - self.last_computation_time).total_seconds() < self.computation_interval):
                return self.current_risk_metrics
                
            if not self.is_computing:
                await self._compute_risk_metrics()
        
        # Update quick cache
        self._last_metrics_cache = {
            'timestamp': current_time,
            'metrics': self.current_risk_metrics
        }
        
        return self.current_risk_metrics
    
    async def _compute_risk_metrics(self):
        """Compute risk metrics using RiskEngine's compute_full_risk method."""
        self.is_computing = True
        try:
            logger.info("Computing real-time risk metrics using RiskEngine...")

            engine = RiskEngine()
            full_result = await engine.compute_full_risk(force_refresh=False)
            
            metrics = full_result.get("metrics", {})
            
            self.current_risk_metrics = {
                "timestamp": metrics.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                
                # Core systemic metrics
                "systemic_risk": metrics.get("systemic_risk", 0.0),
                "systemic_mean": metrics.get("systemic_mean", 0.0),
                "systemic_std": metrics.get("systemic_std", 1.0),
                "risk_level": metrics.get("risk_level", "unknown"),
                
                # Risk regime details
                "regime_details": metrics.get("regime_details", {}),
                
                # DCC-specific metrics
                "dcc_correlation": metrics.get("dcc_correlation"),
                "dcc_regime_analysis": metrics.get("dcc_regime_analysis", {}),
                "dcc_pair_correlations": metrics.get("dcc_pair_correlations", {}),
                
                # All risk signals
                "quantile_signal": metrics.get("quantile_signal"),
                "har_excess_vol": metrics.get("har_excess_vol"),
                "credit_spread_change": metrics.get("credit_spread_change"),
                "vix_change": metrics.get("vix_change"),
                "composite_warning": metrics.get("composite_warning"),
                "composite_risk_score": metrics.get("composite_risk_score"),
                
                # Signal analysis metadata
                "signal_analysis": metrics.get("signal_analysis", {}),
                "component_analysis": metrics.get("component_analysis", {}),
            
                "credit_spread": metrics.get("credit_spread"),
                "market_volatility": metrics.get("market_volatility"),
                "macro_oil": metrics.get("macro_oil"),
                "macro_fx": metrics.get("macro_fx"),
                "forecast_next_risk": metrics.get("forecast_next_risk"),
                
                # PCA and quantile data
                "pca_variance": metrics.get("pca_variance", {}),
                "quantile_summary": metrics.get("quantile_summary", {}),
                "pca_metadata": metrics.get("pca_metadata", {}),
                
                # Computation metadata
                "data_points": metrics.get("data_points", 0),
                "available_signals": metrics.get("available_signals", []),
                "computation_time": metrics.get("computation_time"),
                "source": metrics.get("source", "risk_engine"),
                "computation_duration": metrics.get("computation_duration", 0.0),
                "date_range": metrics.get("date_range", {})
            }

            self.last_computation_time = datetime.utcnow()
            logger.info("Real-time risk metrics updated from RiskEngine with comprehensive data")

        except Exception as e:
            logger.error(f"RiskEngine integration failed: {e}")
            try:
                cached_metrics = await get_cached_data("risk_engine:current_full_risk")
                if cached_metrics:
                    logger.info("Using cached comprehensive risk metrics as fallback")
                    self.current_risk_metrics = cached_metrics
                else:
                    self.current_risk_metrics = self._get_fallback_metrics()
            except Exception as cache_error:
                logger.error(f"Cache fallback also failed: {cache_error}")
                self.current_risk_metrics = self._get_fallback_metrics()
        finally:
            self.is_computing = False

    async def get_websocket_metrics(self):
        """Get optimized metrics for WebSocket broadcasting."""
        full_metrics = await self.get_current_metrics()
        
        return {
            "timestamp": full_metrics.get("timestamp"),
            "systemic_risk": full_metrics.get("systemic_risk", 0.0),
            "risk_level": full_metrics.get("risk_level", "unknown"),
            "dcc_correlation": full_metrics.get("dcc_correlation"),
            "composite_risk_score": full_metrics.get("composite_risk_score"),
            "credit_spread": full_metrics.get("credit_spread"),
            "market_volatility": full_metrics.get("market_volatility"),
            "is_warning": full_metrics.get("composite_warning", False),
            "signals": {
                "quantile": full_metrics.get("quantile_signal"),
                "har_vol": full_metrics.get("har_excess_vol"),
                "vix_change": full_metrics.get("vix_change")
            },
            "components": full_metrics.get("component_analysis", {}),
            "regime": full_metrics.get("regime_details", {})
        }

    async def get_comprehensive_metrics(self):
        """Get full comprehensive metrics for detailed analysis."""
        return await self.get_current_metrics()
    
    async def _get_cached_market_data(self):
        """Get cached market data if available."""
        try:
            market_data = await get_cached_data("market_data_latest")
            if market_data:
                return pd.DataFrame(market_data)
        except Exception as e:
            logger.warning(f"Could not load cached market data: {e}")
        return pd.DataFrame()
    
    async def _get_credit_spread(self, market_data):
        """Extract credit spread from market data."""
        if not market_data.empty and "HY_Spread_Change" in market_data.columns:
            return float(market_data["HY_Spread_Change"].iloc[-1])
        return 3.0 
    
    async def _get_market_volatility(self, market_data):
        """Calculate market volatility from cached data."""
        if not market_data.empty and "SPY" in market_data.columns:
            spy_returns = market_data["SPY"].pct_change().dropna()
            if len(spy_returns) > 20:
                return float(spy_returns.rolling(20).std().iloc[-1] * 100)
        return 20.0
    
    def _get_fallback_metrics(self):
        """Fallback when computation fails."""
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "systemic_risk": 0.0,
            "systemic_mean": 0.0,
            "systemic_std": 1.0,
            "risk_level": "unknown",
            "credit_spread": 3.0,
            "market_volatility": 20.0,
            "dcc_correlation": None,
            "composite_risk_score": 0.0,
            "data_points": 0,
            "warning": "Computation failed - using fallback",
            "regime_details": {},
            "signal_analysis": {},
            "component_analysis": {}
        }

# Global instance
realtime_service = RealtimeRiskService()