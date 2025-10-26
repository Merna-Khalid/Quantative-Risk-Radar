from fastapi import APIRouter, HTTPException, WebSocket, Query
from sqlalchemy.future import select
from app.core.db import AsyncSessionLocal
from app.models.risk import RiskSnapshot, CreditSignalSnapshot, SystemicRiskSnapshot
from app.core.historical_risk import get_historical_risk_by_range
from app.services.data_pipeline import get_credit_signals, get_full_market_dataset
from app.core.cache import get_cached_data, set_cached_data
from app.core.db_utils import save_credit_snapshot
from app.services.systemic_risk import compute_systemic_risk
from app.services.risk_engine import RiskEngine
import pandas as pd
import json
import anyio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Risk Analytics"])
engine = RiskEngine()


@router.get("/history")
async def get_risk_history(
    days: int = Query(None, ge=1, le=3650, description="Number of days from today"),
    start_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    use_cache: bool = Query(True, description="Use cached risk computations")
):
    """
    Get REAL historical systemic risk data from RiskEngine computations with comprehensive metrics.
    """
    if days:
        cache_key = f"risk_history_days_{days}"
    elif start_date and end_date:
        cache_key = f"risk_history_range_{start_date}_{end_date}"
    elif start_date:
        cache_key = f"risk_history_from_{start_date}"
    else:
        days = 180
        cache_key = f"risk_history_days_180"

    if use_cache:
        cached_data = await get_cached_data(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for {cache_key}")
            return cached_data

    try:
        full_result = await engine.compute_full_risk(
            force_refresh=not use_cache,
            days=days,
            start_date=start_date,
            end_date=end_date
        )
        
        systemic_df = full_result.get("systemic_df")
        metrics = full_result.get("metrics", {})
        
        if systemic_df is None or systemic_df.empty or "Systemic" not in systemic_df.columns:
            logger.error("RiskEngine returned empty systemic data")
            return {
                "data": [],
                "summary": {},
                "current_metrics": metrics,
                "metadata": {
                    "error": "No systemic data available",
                    "cache_key": cache_key,
                    "cached": False
                }
            }
        
        logger.info(f"Already filtered dataset: {len(systemic_df)} rows from {systemic_df.index[0]} to {systemic_df.index[-1]}")
        
        current_metrics = metrics
        current_systemic = current_metrics.get("systemic_risk", 0.0)
        systemic_mean = current_metrics.get("systemic_mean", 0.0)
        systemic_std = current_metrics.get("systemic_std", 1.0)
        
        high_threshold = systemic_mean + systemic_std
        medium_threshold = systemic_mean + 0.5 * systemic_std
        
        result = []
        for date, row in systemic_df.iterrows():
            systemic_risk = row["Systemic"]
            
            if systemic_risk >= high_threshold:
                regime = "RED"
                interpretation = "High systemic risk detected. Monitor markets closely."
            elif systemic_risk >= medium_threshold:
                regime = "YELLOW" 
                interpretation = "Elevated risk levels. Increased vigilance recommended."
            else:
                regime = "GREEN"
                interpretation = "Normal market conditions. Standard monitoring procedures."
            
            pca_component = row.get("PCA", systemic_risk * 0.6)
            credit_component = row.get("Credit", systemic_risk * 0.4)
            
            z_score = (systemic_risk - systemic_mean) / systemic_std if systemic_std > 0 else 0
            percentile = min(max(0, (z_score + 2) / 4), 1)
            
            # Enhanced data point with all available signals
            data_point = {
                "date": date.strftime('%Y-%m-%d'),
                "systemic_risk": float(systemic_risk),
                "systemic_risk_score": float(systemic_risk),
                "pca_signal_score": float(pca_component),
                "credit_signal_score": float(credit_component),
                "market_regime": regime,
                "risk_interpretation": interpretation,
                "z_score": float(z_score),
                "percentile": float(percentile),
                "relative_to_current": float(systemic_risk - current_systemic),
                "components": {
                    "pca_contribution": float(pca_component),
                    "credit_contribution": float(credit_component),
                    "other_contribution": float(systemic_risk - pca_component - credit_component)
                }
            }
            
            # Add all available risk signals
            signal_mapping = {
                "Quantile_Signal": "quantile_signal",
                "DCC_Corr": "dcc_correlation", 
                "HAR_ExcessVol_Z": "har_excess_vol",
                "Credit_Spread_Change": "credit_spread_change",
                "VIX_Change": "vix_change",
                "Composite_Risk_Score": "composite_risk_score"
            }
            
            for df_col, api_col in signal_mapping.items():
                if df_col in row and pd.notna(row[df_col]):
                    data_point[api_col] = float(row[df_col])
            
            # Add warning signal if available
            if "is_warning" in row:
                data_point["is_warning"] = bool(row["is_warning"])
            
            result.append(data_point)
        
        # Enhanced summary with comprehensive metrics
        summary = {
            "current_risk": current_systemic,
            "period_mean": float(systemic_df["Systemic"].mean()),
            "period_std": float(systemic_df["Systemic"].std()),
            "period_min": float(systemic_df["Systemic"].min()),
            "period_max": float(systemic_df["Systemic"].max()),
            "data_points": len(systemic_df),
            "date_range": {
                "start": systemic_df.index[0].strftime('%Y-%m-%d'),
                "end": systemic_df.index[-1].strftime('%Y-%m-%d')
            },
            "risk_distribution": {
                "high_threshold": float(high_threshold),
                "medium_threshold": float(medium_threshold),
                "current_regime": current_metrics.get("risk_level", "unknown")
            },
            "signal_summary": {
                "available_signals": list(systemic_df.columns),
                "current_dcc_correlation": current_metrics.get("dcc_correlation"),
                "current_quantile_signal": current_metrics.get("quantile_signal"),
                "current_har_excess_vol": current_metrics.get("har_excess_vol"),
                "current_composite_score": current_metrics.get("composite_risk_score")
            }
        }
        
        response = {
            "data": result,
            "summary": summary,
            "current_metrics": current_metrics,
            "metadata": {
                "computation_time": current_metrics.get("computation_time"),
                "source": current_metrics.get("source", "risk_engine"),
                "cache_key": cache_key,
                "cached": False,
                "available_signals_count": len(systemic_df.columns),
                "computation_duration": current_metrics.get("computation_duration", 0)
            }
        }
        
        logger.info(f"Returning {len(result)} risk data points with {len(systemic_df.columns)} signals")
        
        if use_cache:
            await set_cached_data(cache_key, response, expire_seconds=3600)
            response["metadata"]["cached"] = True

        return response

    except Exception as e:
        logger.error(f"Error getting risk history from RiskEngine: {e}")
        
        try:
            cached_fallback = await get_cached_data(cache_key)
            if cached_fallback:
                logger.info("Using cached data as fallback due to computation error")
                cached_fallback["metadata"]["fallback"] = True
                cached_fallback["metadata"]["error"] = str(e)
                return cached_fallback
        except:
            pass
            
        raise HTTPException(
            status_code=500, 
            detail=f"Error getting risk history: {e}"
        )
