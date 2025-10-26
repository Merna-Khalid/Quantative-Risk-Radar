import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd
from arch import arch_model

from app.models.risk import SystemicRiskSnapshot
from app.core.db import AsyncSessionLocal
from app.core.observer import SignalObserver, log_event, notify_dashboard
from app.services.systemic_risk import compute_systemic_risk
from app.services.strategies.dcc_garch_strategy import RegimeSwitchingDCC, compute_quantile_regression
from app.core.db_utils import save_systemic_snapshot, save_quantile_results, save_risk_snapshot
from app.core.cache import (
    get_cached_full_risk, cache_full_risk,
    get_cached_systemic_snapshot, cache_systemic_snapshot,
    get_cached_quantile_snapshot, cache_quantile_snapshot,
    get_cached_data, set_cached_data
)
from app.services.decorators import log_execution, safe_execute
import logging

logger = logging.getLogger(__name__)

class RiskEngine:
    def __init__(self):
        self.observer = SignalObserver()
        self.observer.attach(log_event)
        self.observer.attach(notify_dashboard)
        self._dcc_cache_key = "dcc_latest_result"
        self._cache_ttl = 9000
        self.dcc_model = None

    # -----------------------------
    # CACHE MANAGEMENT METHODS
    # -----------------------------
    async def get_cached_risk_metrics(self) -> Optional[Dict[str, Any]]:
        """Get cached full risk metrics with validation"""
        try:
            cached = await get_cached_full_risk()
            if cached and self._is_cache_valid(cached):
                logger.info("Using cached risk metrics")
                return cached
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")
        return None

    def _is_cache_valid(self, cached_data: Dict[str, Any]) -> bool:
        """Validate cache freshness"""
        try:
            cache_time = datetime.fromisoformat(cached_data.get("timestamp", "").replace("Z", ""))
            age = (datetime.utcnow() - cache_time).total_seconds()
            return age < self._cache_ttl
        except:
            return False

    async def cache_risk_computation(self, result: Dict[str, Any]):
        """Cache risk computation results"""
        try:
            await cache_full_risk(result["metrics"], self._cache_ttl)
            
            if "systemic_df" in result and result["systemic_df"] is not None:
                systemic_data = {
                    "data": result["systemic_df"].to_dict(),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await cache_systemic_snapshot(systemic_data, self._cache_ttl)
            
            logger.info("Risk computation cached successfully")
        except Exception as e:
            logger.warning(f"Failed to cache risk computation: {e}")

    # -----------------------------
    # Process signal
    # -----------------------------
    @log_execution
    @safe_execute
    async def compute_full_risk(self, force_refresh: bool = False, days: int = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        Enhanced end-to-end risk computation using ALL systemic risk signals
        """
        logger.info(f"Starting full risk computation for range: days={days}, start={start_date}, end={end_date}")
        start_time = datetime.utcnow()

        cache_key = f"full_risk_{days}_{start_date}_{end_date}"
        if not force_refresh:
            cached_metrics = await get_cached_data(cache_key)
            if cached_metrics:
                return {"systemic_df": None, "metrics": cached_metrics, "source": "cache"}

        try:
            # Compute systemic risk with ALL signals
            systemic_df, pca_meta = await compute_systemic_risk(
                force_refresh=force_refresh, 
                days=days,
                start_date=start_date, 
                end_date=end_date
            )
            
            if systemic_df.empty:
                logger.error("Systemic risk computation returned empty data")
                raise ValueError("Systemic risk computation returned empty data")

            # Extract date range from systemic_df
            if systemic_df is not None and not systemic_df.empty:
                snapshot_start_date = systemic_df.index[0].to_pydatetime()
                snapshot_end_date = systemic_df.index[-1].to_pydatetime()
            else:
                snapshot_start_date = datetime.utcnow() - timedelta(days=1)
                snapshot_end_date = datetime.utcnow()

            # Save systemic snapshot to database WITH DATE RANGE
            systemic_snapshot = await save_systemic_snapshot(
                systemic_df, 
                start_date=snapshot_start_date, 
                end_date=snapshot_end_date
            )

            # Compute basic metrics
            dcc_metrics = await self.compute_comprehensive_dcc_metrics(systemic_df)

            credit_metrics = await self.compute_credit_metrics(systemic_df, days, start_date, end_date)
            macro_metrics = await self.compute_macro_metrics(systemic_df, days, start_date, end_date)
            
            forecast_metrics = await self.compute_forecast_risk(systemic_df, days, start_date, end_date)

            # Compute Quantile Regression using all available signals
            try:
                quantile_summary, quantile_results = await compute_quantile_regression(systemic_df)
                quantile_summary = self._enhance_quantile_analysis(quantile_summary, systemic_df)
                
                quantile_snapshot = await save_quantile_results(
                    quantile_summary, 
                    quantile_results,
                    start_date=snapshot_start_date,
                    end_date=snapshot_end_date
                )
                await cache_quantile_snapshot({
                    "summary": quantile_summary,
                    "results": quantile_results,
                    "timestamp": datetime.utcnow().isoformat(),
                    "date_range": {
                        "start": snapshot_start_date.isoformat(),
                        "end": snapshot_end_date.isoformat()
                    }
                }, self._cache_ttl)
            except Exception as e:
                logger.warning(f"Quantile regression failed: {e}")
                quantile_summary = {"error": str(e), "warning": "Quantile regression unavailable"}

            systemic_metrics = self._compute_comprehensive_systemic_metrics(systemic_df, dcc_metrics)
            # Derive comprehensive risk regime using ALL signals
            risk_level, regime_details = self._calculate_comprehensive_risk_regime(systemic_df)


            computation_time = datetime.utcnow()
            

            full_summary = {
                "timestamp": computation_time.isoformat() + "Z",
                
                # Core systemic metrics
                "systemic_risk": systemic_metrics["current_systemic"],
                "systemic_mean": systemic_metrics["mean_systemic"],
                "systemic_std": systemic_metrics["std_systemic"],
                
                # Risk regime with DCC
                "risk_level": risk_level,
                "regime_details": self.convert_for_json(regime_details),
                
                # DCC-specific metrics
                "dcc_correlation": dcc_metrics.get("dcc_correlation"),
                "dcc_regime_analysis": self.convert_for_json(dcc_metrics.get("regime_analysis", {})),
                "dcc_pair_correlations": self.convert_for_json(dcc_metrics.get("pair_correlations", {})),
                
                # Other signal values
                "quantile_signal": systemic_metrics.get("quantile_signal"),
                "har_excess_vol": systemic_metrics.get("har_excess_vol"),
                "credit_spread_change": systemic_metrics.get("credit_spread_change"),
                "vix_change": systemic_metrics.get("vix_change"),
                "composite_warning": systemic_metrics.get("composite_warning"),
                "composite_risk_score": systemic_metrics.get("composite_risk_score"),
                
                # Signal analysis metadata
                "signal_analysis": self.convert_for_json(systemic_metrics["signal_analysis"]),
                "component_analysis": self.convert_for_json(systemic_metrics["component_analysis"]),
                
                "credit_spread": credit_metrics.get("spread"),
                "market_volatility": macro_metrics.get("volatility"),
                "macro_oil": macro_metrics.get("oil_return"),
                "macro_fx": macro_metrics.get("fx_change"),
                "forecast_next_risk": forecast_metrics.get("predicted_next"),
                
                # PCA and quantile data
                "pca_variance": self.convert_for_json(pca_meta.get("explained_variance", {})),
                "quantile_summary": self.convert_for_json(quantile_summary),
                "pca_metadata": self.convert_for_json(pca_meta),
                
                # Computation metadata
                "data_points": systemic_metrics["data_points"],
                "available_signals": list(systemic_df.columns),
                "computation_time": computation_time.isoformat() + "Z",
                "source": "risk_engine",
                "computation_duration": (computation_time - start_time).total_seconds(),
                "date_range": {
                    "days": days,
                    "start_date": start_date,
                    "end_date": end_date,
                    "actual_start": systemic_df.index[0].strftime('%Y-%m-%d') if not systemic_df.empty else None,
                    "actual_end": systemic_df.index[-1].strftime('%Y-%m-%d') if not systemic_df.empty else None
                }
            }


            await set_cached_data(cache_key, full_summary, expire_seconds=self._cache_ttl)

            await save_risk_snapshot(full_summary, start_date=snapshot_start_date, end_date=snapshot_end_date)

            logger.info(f"Full risk computation completed with {len(systemic_df.columns)} signals in {full_summary['computation_duration']:.2f}s")

            return {"systemic_df": systemic_df, "metrics": full_summary, "source": "computation"}

        except Exception as e:
            logger.error(f"Full risk computation failed: {e}")
            from app.main import snapshot_ws_manager
            await snapshot_ws_manager.broadcast({
                "event": "risk_error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            })
            raise
    
    def convert_for_json(self, obj):
        if isinstance(obj, (np.bool_, np.bool)):  # Remove np.bool8
            return bool(obj)
        elif isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self.convert_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_for_json(item) for item in obj]
        elif pd.isna(obj):
            return None
        else:
            return obj

    def _compute_comprehensive_systemic_metrics(self, systemic_df: pd.DataFrame, dcc_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """Compute comprehensive metrics for ALL systemic risk signals including DCC"""
        if systemic_df.empty:
            return {
                "current_systemic": 0.0,
                "mean_systemic": 0.0,
                "std_systemic": 0.0,
                "data_points": 0,
                "signal_analysis": {},
                "component_analysis": {}
            }
        
        systemic_series = systemic_df["Systemic"]
        pca_series = systemic_df["PCA"]
        credit_series = systemic_df["Credit"]
        
        # Basic statistics
        current_systemic = float(systemic_series.iloc[-1])
        mean_systemic = float(systemic_series.mean())
        std_systemic = float(systemic_series.std())
        
        component_analysis = {
            "correlation_matrix": systemic_df[["Systemic", "PCA", "Credit"]].corr().to_dict(),
            "pca_contribution": float((pca_series / systemic_series).mean()) if not (systemic_series == 0).any() else 0.0,
            "credit_contribution": float((credit_series / systemic_series).mean()) if not (systemic_series == 0).any() else 0.0,
            "pca_volatility": float(pca_series.pct_change().std()) if len(pca_series) > 1 else 0.0,
            "credit_volatility": float(credit_series.pct_change().std()) if len(credit_series) > 1 else 0.0,
            "pca_trend": float(pca_series.tail(10).mean() - pca_series.head(10).mean()) if len(pca_series) >= 10 else 0.0,
            "credit_trend": float(credit_series.tail(10).mean() - credit_series.head(10).mean()) if len(credit_series) >= 10 else 0.0,
            "current_pca": float(pca_series.iloc[-1]),
            "current_credit": float(credit_series.iloc[-1])
        }
        
        # Add DCC metrics if available
        if dcc_metrics:
            component_analysis["dcc_correlation"] = dcc_metrics.get("dcc_correlation")
            component_analysis["dcc_regime"] = dcc_metrics.get("regime_analysis", {}).get("current_regime")
            component_analysis["dcc_stress_contrast"] = dcc_metrics.get("regime_analysis", {}).get("stress_correlation_contrast")
        
        metrics = {
            "current_systemic": current_systemic,
            "mean_systemic": mean_systemic,
            "std_systemic": std_systemic,
            "data_points": len(systemic_df),
            "signal_analysis": {},
            "component_analysis": component_analysis
        }
        
        # Analyze each signal (existing code remains the same)
        for signal_name in systemic_df.columns:
            if signal_name not in ["Systemic", "PCA", "Credit"]:
                signal_series = systemic_df[signal_name]
                if not signal_series.dropna().empty:
                    current_val = float(signal_series.iloc[-1])
                    mean_val = float(signal_series.mean())
                    std_val = float(signal_series.std())
                    
                    metrics["signal_analysis"][signal_name] = {
                        "current": current_val,
                        "mean": mean_val,
                        "std": std_val,
                        "is_extreme": abs(current_val) > 2.0
                    }
                    
                    # Map signal names to metrics (existing code)
                    if signal_name == "HAR_ExcessVol_Z":
                        metrics["har_excess_vol"] = current_val
                    elif signal_name == "DCC_Corr":
                        # Use computed DCC value if available, otherwise fallback
                        metrics["dcc_correlation"] = dcc_metrics.get("dcc_correlation", current_val) if dcc_metrics else current_val
                    elif signal_name == "Quantile_Signal":
                        metrics["quantile_signal"] = current_val
                    elif signal_name == "Credit_Spread_Change":
                        metrics["credit_spread_change"] = current_val
                    elif signal_name == "VIX_Change":
                        metrics["vix_change"] = current_val
                    elif signal_name == "is_warning":
                        metrics["composite_warning"] = bool(current_val)
                    elif signal_name == "Composite_Risk_Score":
                        metrics["composite_risk_score"] = current_val
        
        return metrics

    def _enhance_quantile_analysis(self, quantile_summary: Dict[str, Any], systemic_df: pd.DataFrame) -> Dict[str, Any]:
        """quantile analysis with component-specific insights"""
        if systemic_df.empty:
            return quantile_summary
        
        try:
            # Component-specific quantile analysis
            pca_quantiles = systemic_df["PCA"].quantile([0.05, 0.25, 0.5, 0.75, 0.95])
            credit_quantiles = systemic_df["Credit"].quantile([0.05, 0.25, 0.5, 0.75, 0.95])
            
            # Current position in distribution
            current_pca = systemic_df["PCA"].iloc[-1]
            current_credit = systemic_df["Credit"].iloc[-1]
            
            pca_percentile = float((systemic_df["PCA"] < current_pca).mean())
            credit_percentile = float((systemic_df["Credit"] < current_credit).mean())
            
            # Enhanced summary
            enhanced_summary = quantile_summary.copy()
            enhanced_summary.update({
                "component_quantiles": {
                    "pca": pca_quantiles.to_dict(),
                    "credit": credit_quantiles.to_dict()
                },
                "current_percentiles": {
                    "pca": pca_percentile,
                    "credit": credit_percentile
                },
                "component_extremes": {
                    "pca_extreme": bool(current_pca > pca_quantiles[0.95]),  # Convert to Python bool
                    "credit_extreme": bool(current_credit > credit_quantiles[0.95])  # Convert to Python bool
                }
            })
            
            return enhanced_summary
        except Exception as e:
            logger.warning(f"Failed to enhance quantile analysis: {e}")
            return quantile_summary

    def _calculate_comprehensive_risk_regime(self, systemic_df: pd.DataFrame, dcc_metrics: Dict[str, Any] = None) -> tuple:
        """Calculate risk regime using all systemic components including DCC"""
        if systemic_df.empty:
            return "low", {}
        
        systemic_series = systemic_df["Systemic"]
        pca_series = systemic_df["PCA"]
        credit_series = systemic_df["Credit"]
        
        current_systemic = systemic_series.iloc[-1]
        current_pca = pca_series.iloc[-1]
        current_credit = credit_series.iloc[-1]
        
        mean_systemic = systemic_series.mean()
        std_systemic = systemic_series.std()
        
        # Individual component thresholds
        pca_mean, pca_std = pca_series.mean(), pca_series.std()
        credit_mean, credit_std = credit_series.mean(), credit_series.std()
        
        # Multi-dimensional regime determination
        systemic_z = (current_systemic - mean_systemic) / std_systemic if std_systemic != 0 else 0
        pca_z = (current_pca - pca_mean) / pca_std if pca_std != 0 else 0
        credit_z = (current_credit - credit_mean) / credit_std if credit_std != 0 else 0
        
        # Include DCC in regime calculation if available
        dcc_z = 0
        if dcc_metrics and dcc_metrics.get("dcc_correlation") is not None:
            dcc_corr = dcc_metrics["dcc_correlation"]
            # Higher correlations indicate higher systemic risk
            dcc_z = (dcc_corr - 0.5) / 0.2  # Normalize correlation to z-score
        
        # Weighted regime score (adjust weights based on importance)
        regime_score = (0.4 * systemic_z + 0.25 * pca_z + 0.2 * credit_z + 0.15 * dcc_z)
        
        # Determine regime with DCC consideration
        if regime_score > 1.0 or (dcc_metrics and dcc_metrics.get("regime_analysis", {}).get("current_regime") == "highly_correlated"):
            risk_level = "high"
        elif regime_score > 0.5:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        regime_details = {
            "regime_score": float(regime_score),
            "component_z_scores": {
                "systemic": float(systemic_z),
                "pca": float(pca_z),
                "credit": float(credit_z),
                "dcc": float(dcc_z)
            },
            "component_contributions": {
                "pca": float(pca_series.iloc[-1]),
                "credit": float(credit_series.iloc[-1])
            },
            "dcc_metrics": dcc_metrics.get("regime_analysis", {}) if dcc_metrics else {},
            "thresholds": {
                "high": 1.0,
                "medium": 0.5
            }
        }
        
        return risk_level, regime_details


    def _handle_metric_result(self, result, metric_name: str) -> Dict[str, Any]:
        """Handle results from parallel metric computations"""
        if isinstance(result, Exception):
            logger.warning(f"{metric_name} computation failed: {result}")
            return {}
        return result

    def _calculate_risk_regime(self, current_val: float, mean_val: float, std_val: float) -> str:
        """Calculate risk regime with adaptive thresholds"""
        thr_high = mean_val + std_val
        thr_med = mean_val + 0.5 * std_val
        
        if current_val >= thr_high:
            return "high"
        elif current_val >= thr_med:
            return "medium"
        else:
            return "low"

    # ----------------------------------------------------
    # Regime-Switching DCC integration
    # ----------------------------------------------------

    @log_execution
    @safe_execute
    async def initialize_dcc_model(self, returns_df: pd.DataFrame, stress_indicator: pd.Series = None):
        """Initialize and fit the DCC model with proper error handling"""
        try:
            logger.info("Initializing DCC model")
            
            if returns_df.empty or len(returns_df) < 100:
                logger.warning("Insufficient data for DCC model initialization")
                return None

            # Create stress indicator if not provided (using volatility regime)
            if stress_indicator is None:
                vol_regime = returns_df.std().mean()
                stress_threshold = returns_df.rolling(30).std().mean().mean() * 1.5
                stress_indicator = (returns_df.rolling(30).std().mean(axis=1) > stress_threshold).astype(int)

            # Align data
            common_idx = returns_df.index.intersection(stress_indicator.index)
            if len(common_idx) < 50:
                logger.warning("Insufficient common data points for DCC")
                return None

            returns_aligned = returns_df.loc[common_idx]
            stress_aligned = stress_indicator.loc[common_idx]

            # Initialize and fit DCC model
            self.dcc_model = RegimeSwitchingDCC(returns_aligned, stress_aligned)
            self.dcc_model.fit()
            
            logger.info("DCC model initialized successfully")
            return self.dcc_model

        except Exception as e:
            logger.error(f"DCC model initialization failed: {e}")
            return None

    @log_execution
    @safe_execute
    async def compute_comprehensive_dcc_metrics(self, systemic_df: pd.DataFrame) -> Dict[str, Any]:
        """Compute comprehensive DCC metrics integrated with systemic risk"""
        try:
            if systemic_df.empty:
                return {"dcc_correlation": None, "regime_analysis": {}, "pair_correlations": {}}

            asset_columns = [col for col in systemic_df.columns if col in ['SPY', 'XLF', 'XLK', 'HYG', 'LQD']]
            
            if len(asset_columns) < 2:
                logger.warning("Insufficient asset columns for DCC analysis")
                return {"dcc_correlation": None, "regime_analysis": {}, "pair_correlations": {}}

            asset_returns = systemic_df[asset_columns].pct_change().dropna()
            
            if asset_returns.empty or len(asset_returns) < 50:
                return {"dcc_correlation": None, "regime_analysis": {}, "pair_correlations": {}}

            # Create stress indicator based on systemic risk
            systemic_stress = (systemic_df['Systemic'] > systemic_df['Systemic'].quantile(0.8)).astype(int)
            systemic_stress = systemic_stress.reindex(asset_returns.index).fillna(0)

            # Initialize DCC model if not already done
            if self.dcc_model is None:
                await self.initialize_dcc_model(asset_returns, systemic_stress)

            dcc_metrics = {}

            if self.dcc_model and hasattr(self.dcc_model, 'compute_pair_corr'):
                # Compute pair-wise correlations
                pair_correlations = {}
                tickers = asset_returns.columns.tolist()
                
                for i in range(len(tickers)):
                    for j in range(i + 1, len(tickers)):
                        pair = (tickers[i], tickers[j])
                        try:
                            corr_series = self.dcc_model.compute_pair_corr(pair)
                            current_corr = corr_series.iloc[-1]
                            if pd.isna(current_corr):
                                # Fallback to the last non-NaN value in the series
                                current_corr = corr_series.dropna().iloc[-1] if not corr_series.dropna().empty else None
                            if not corr_series.empty:
                                pair_correlations[f"{tickers[i]}_{tickers[j]}"] = {
                                    "current": float(corr_series.iloc[-1]),
                                    "mean": float(corr_series.mean()),
                                    "std": float(corr_series.std()),
                                    "trend": float(corr_series.tail(5).mean() - corr_series.head(5).mean()) if len(corr_series) >= 10 else 0.0,
                                    "regime_contrast": self._compute_regime_contrast(corr_series, systemic_stress)
                                }
                        except Exception as e:
                            logger.warning(f"DCC correlation failed for pair {pair}: {e}")

                dcc_metrics["pair_correlations"] = pair_correlations
                
                # Compute overall DCC signal
                if pair_correlations:
                    all_current_corrs = [v["current"] for v in pair_correlations.values()]
                    dcc_metrics["dcc_correlation"] = float(np.mean(all_current_corrs))
                else:
                    dcc_metrics["dcc_correlation"] = None

                # Regime analysis
                dcc_metrics["regime_analysis"] = self._analyze_dcc_regimes(pair_correlations, systemic_stress)

            else:
                # Fallback to simple correlation
                current_corr = asset_returns.corr().mean().mean()
                dcc_metrics["dcc_correlation"] = float(current_corr) if not pd.isna(current_corr) else None
                dcc_metrics["pair_correlations"] = {}
                dcc_metrics["regime_analysis"] = {}

            return dcc_metrics

        except Exception as e:
            logger.error(f"Comprehensive DCC computation failed: {e}")
            return {"dcc_correlation": None, "regime_analysis": {}, "pair_correlations": {}}

    def _compute_regime_contrast(self, corr_series: pd.Series, stress_indicator: pd.Series) -> Dict[str, float]:
        """Compute correlation contrast between stress and normal regimes"""
        try:
            aligned_stress = stress_indicator.reindex(corr_series.index).fillna(0)
            
            stress_corrs = corr_series[aligned_stress == 1]
            normal_corrs = corr_series[aligned_stress == 0]
            
            return {
                "stress_mean": float(stress_corrs.mean()) if len(stress_corrs) > 0 else 0.0,
                "normal_mean": float(normal_corrs.mean()) if len(normal_corrs) > 0 else 0.0,
                "contrast": float(stress_corrs.mean() - normal_corrs.mean()) if len(stress_corrs) > 0 and len(normal_corrs) > 0 else 0.0,
                "stress_vol": float(stress_corrs.std()) if len(stress_corrs) > 0 else 0.0,
                "normal_vol": float(normal_corrs.std()) if len(normal_corrs) > 0 else 0.0
            }
        except Exception as e:
            logger.warning(f"Regime contrast computation failed: {e}")
            return {}

    def _analyze_dcc_regimes(self, pair_correlations: Dict, stress_indicator: pd.Series) -> Dict[str, Any]:
        """Analyze DCC correlation regimes"""
        try:
            if not pair_correlations:
                return {}

            # Extract current correlations
            current_corrs = [metrics["current"] for metrics in pair_correlations.values() if metrics.get("current") is not None]
            
            if not current_corrs:
                return {}

            avg_correlation = np.mean(current_corrs)
            corr_dispersion = np.std(current_corrs)
            
            # Regime classification
            if avg_correlation > 0.7:
                regime = "highly_correlated"
            elif avg_correlation > 0.4:
                regime = "moderately_correlated"
            else:
                regime = "low_correlation"

            # Stress regime alignment
            current_stress = stress_indicator.iloc[-1] if not stress_indicator.empty else 0
            stress_corr_contrast = np.mean([metrics.get("regime_contrast", {}).get("contrast", 0) 
                                          for metrics in pair_correlations.values()])

            return {
                "current_regime": regime,
                "average_correlation": float(avg_correlation),
                "correlation_dispersion": float(corr_dispersion),
                "stress_regime": bool(current_stress),
                "stress_correlation_contrast": float(stress_corr_contrast),
                "n_pairs": len(pair_correlations),
                "extreme_pairs": len([c for c in current_corrs if abs(c) > 0.8])
            }
        except Exception as e:
            logger.warning(f"DCC regime analysis failed: {e}")
            return {}
        
    async def _broadcast_dcc_update(self, event_type: str, data: Dict[str, Any]):
        """Helper method to broadcast DCC updates."""
        broadcast_data = {"event": event_type, **data}
        from app.main import snapshot_ws_manager
        await snapshot_ws_manager.broadcast(broadcast_data)

    async def _cache_dcc_result(self, result: Dict[str, Any]):
        """Cache DCC results in Redis."""
        try:
            await set_cached_data(self._dcc_cache_key, result, expire_seconds=3600)  # 1-hour TTL
            logger.info("DCC results cached successfully")
        except Exception as e:
            logger.warning(f"Failed to cache DCC result: {e}")

    async def get_cached_dcc_result(self) -> Optional[Dict[str, Any]]:
        """Retrieve cached DCC results."""
        try:
            cached_data = await get_cached_data(self._dcc_cache_key)
            if cached_data is not None:
                logger.info("Loaded DCC results from cache")
            return cached_data
        except Exception as e:
            logger.warning(f"Failed to load cached DCC result: {e}")
        
        return None

    # ----------------------------------------------------
    # Internal helper computations for full risk pipeline
    # ----------------------------------------------------
    async def compute_credit_metrics(self, systemic_df: pd.DataFrame, days: int = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Compute credit metrics for the specified date range"""
        if systemic_df.empty:
            return {"spread": None}
        
        try:
            # Filter systemic_df if date range is provided
            if days or start_date or end_date:
                systemic_df = self._filter_by_date_range(systemic_df, days, start_date, end_date)
                
            systemic_series = systemic_df["Systemic"]
            rolling_vol = systemic_series.pct_change().rolling(window=20).std()
            spread_estimate = float(rolling_vol.iloc[-1]) if not rolling_vol.dropna().empty else None
            return {"spread": spread_estimate}
        except Exception as e:
            logger.warning(f"compute_credit_metrics failed: {e}")
            return {"spread": None}

    async def compute_macro_metrics(self, systemic_df: pd.DataFrame, days: int = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        Compute macro metrics for the specified date range.
        FIX: Extract oil and FX directly from the systemic_df.
        """
        if systemic_df.empty:
            return {"oil_return": None, "fx_change": None, "volatility": None}

        try:
            # 1. Filter systemic_df if date range is provided
            if days or start_date or end_date:
                # Assuming self._filter_by_date_range exists and works correctly
                systemic_df = self._filter_by_date_range(systemic_df, days, start_date, end_date)
            
            # 2. Try cached macro data first (existing logic)
            macro_data = await get_cached_data("macro_latest_snapshot")
            if macro_data:
                return {
                    "oil_return": macro_data.get("oil_return"),
                    "fx_change": macro_data.get("fx_change"),
                    "volatility": macro_data.get("market_volatility")
                }
            
            # 3. If cache miss, extract from the latest row of systemic_df (The FIX)
            latest_data = systemic_df.iloc[-1]

            # Use the column names confirmed in your data pipeline
            current_oil = latest_data.get('oil_return') if 'oil_return' in latest_data else None
            current_fx = latest_data.get('fx_change') if 'fx_change' in latest_data else None
            
            # 4. Calculate volatility (existing logic)
            systemic_returns = systemic_df["Systemic"].pct_change().dropna()
            vol = float(systemic_returns.rolling(window=30).std().iloc[-1]) if not systemic_returns.empty else None

            # 5. Return the extracted and calculated metrics
            return {
                "oil_return": self.convert_for_json(current_oil), # Use extracted oil return
                "fx_change": self.convert_for_json(current_fx),   # Use extracted fx change
                "volatility": self.convert_for_json(vol)          # Use calculated volatility
            }
        
        except Exception as e:
            logger.warning(f"compute_macro_metrics failed: {e}")
            return {"oil_return": None, "fx_change": None, "volatility": None}

    async def compute_dcc_correlation(self, systemic_df: pd.DataFrame, days: int = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Compute DCC correlation for the specified date range"""
        try:
            # Filter systemic_df if date range is provided
            if days or start_date or end_date:
                systemic_df = self._filter_by_date_range(systemic_df, days, start_date, end_date)
                
            cached_dcc = await self.get_cached_dcc_result()
            if cached_dcc and "mean_corr_series" in cached_dcc:
                avg_corr = float(np.mean(cached_dcc["mean_corr_series"]))
                return {"avg_corr": avg_corr}

            systemic_series = systemic_df["Systemic"]
            autocorr = systemic_series.autocorr(lag=1)
            return {"avg_corr": float(autocorr)}
        except Exception as e:
            logger.warning(f"compute_dcc_correlation failed: {e}")
            return {"avg_corr": None}

    async def compute_forecast_risk(self, systemic_df: pd.DataFrame, days: int = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Compute forecast risk for the specified date range"""
        try:
            # Filter systemic_df if date range is provided
            if days or start_date or end_date:
                systemic_df = self._filter_by_date_range(systemic_df, days, start_date, end_date)
                
            series = systemic_df["Systemic"].dropna()
            if len(series) < 5:
                return {"predicted_next": None}

            # Basic AR(1) estimation
            y = series.values
            phi = np.corrcoef(y[1:], y[:-1])[0, 1] if len(y) > 1 and not np.isnan(np.corrcoef(y[1:], y[:-1])[0, 1]) else 0
            forecast_next = float(phi * y[-1])
            return {"predicted_next": forecast_next}
        except Exception as e:
            logger.warning(f"compute_forecast_risk failed: {e}")
            return {"predicted_next": None}

    def _filter_by_date_range(self, df, days=None, start_date=None, end_date=None):
        """Filter DataFrame by date range parameters"""
        if df.empty:
            return df
        
        # Convert string dates to datetime if provided
        if start_date:
            start_date = pd.to_datetime(start_date)
        if end_date:
            end_date = pd.to_datetime(end_date)
        
        # Apply date range filtering
        if days:
            # Last N days from today
            end_date_real = datetime.now()
            start_date_real = end_date_real - timedelta(days=days)
            mask = (df.index >= start_date_real) & (df.index <= end_date_real)
            filtered_df = df.loc[mask]
        elif start_date and end_date:
            # Specific date range
            mask = (df.index >= start_date) & (df.index <= end_date)
            filtered_df = df.loc[mask]
        elif start_date:
            # From start date to most recent
            mask = df.index >= start_date
            filtered_df = df.loc[mask]
        elif end_date:
            # From earliest to end date
            mask = df.index <= end_date
            filtered_df = df.loc[mask]
        else:
            # No filtering
            filtered_df = df
        
        logger.info(f"Date range filtering: {len(df)} -> {len(filtered_df)} rows")
        return filtered_df