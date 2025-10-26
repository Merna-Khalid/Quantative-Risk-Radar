from fastapi import APIRouter, HTTPException
from app.services.visualization_service import visualization_service
# from app.services.risk_engine import RiskEngine
from app.services.data_pipeline import get_full_market_dataset, get_credit_signals, get_sector_data
from app.services.systemic_risk import compute_systemic_risk
import logging
import traceback
import json
import numpy as np
import pandas as pd
from decimal import Decimal

router = APIRouter()
logger = logging.getLogger(__name__)

def safe_json_serializer(obj):
    """Handle problematic JSON values"""
    if isinstance(obj, (np.float32, np.float64, np.int32, np.int64)):
        return float(obj) if not np.isnan(obj) and np.isfinite(obj) else None
    elif isinstance(obj, float):
        return obj if not np.isnan(obj) and np.isfinite(obj) else None
    elif isinstance(obj, (np.ndarray, pd.Series)):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif pd.isna(obj):
        return None
    elif isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@router.get("/visualization/risk-cascade")
async def get_risk_cascade_visualization(force_refresh: bool = False):
    try:
        market_data = await get_full_market_dataset(force_refresh=force_refresh)
        
        if market_data.empty:
            raise HTTPException(status_code=404, detail="No market data available")
        
        systemic_df, pca_meta = await compute_systemic_risk(force_refresh=force_refresh)
        
        risk_signals = await _generate_comprehensive_risk_signals(systemic_df, market_data)
        
        visualization_data = visualization_service.generate_risk_cascade_data(risk_signals)
        
        return {
            "success": True,
            "data": visualization_data,
            "metadata": {
                "pca_components": pca_meta,
                "data_shape": f"{len(risk_signals)} rows, {len(risk_signals.columns)} columns",
                "computation_timestamp": pd.Timestamp.now().isoformat()
            },
            "message": "Risk cascade visualization data generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error generating risk cascade visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _generate_comprehensive_risk_signals(systemic_df: pd.DataFrame, market_data: pd.DataFrame) -> pd.DataFrame:
    """
    Generate comprehensive risk signals by combining systemic risk with other risk measures.
    """
    risk_signals = pd.DataFrame(index=systemic_df.index)
    
    # 1. Systemic Score (from PCA + Credit)
    risk_signals['Systemic_Score'] = systemic_df['Systemic']
    
    # 2. Quantile Signal (5th percentile of HYG returns)
    if 'HYG' in market_data.columns:
        hyg_returns = market_data['HYG'].dropna()
        risk_signals['Quantile_Signal'] = hyg_returns.rolling(window=63).quantile(0.05)  # 3-month rolling 5th percentile
    
    # 3. DCC Correlation Signal (XLK vs XLF if available)
    if 'XLK' in market_data.columns and 'XLF' in market_data.columns:
        xlk_returns = market_data['XLK'].dropna()
        xlf_returns = market_data['XLF'].dropna()
        
        # Simple rolling correlation as proxy for DCC
        rolling_corr = xlk_returns.rolling(window=21).corr(xlf_returns)
        risk_signals['DCC_Corr'] = rolling_corr
        
        # Bootstrap exceedance
        risk_signals['Corr_Exceeds_Bootstrap'] = (rolling_corr > rolling_corr.quantile(0.95)).astype(int)
    
    # 4. HAR Excess Volatility
    if 'SPY' in market_data.columns:
        spy_returns = market_data['SPY'].dropna()
        
        # Realized volatility (21-day)
        realized_vol = spy_returns.rolling(window=21).std()
        
        # HAR model components
        daily_vol = spy_returns.rolling(window=1).std()
        weekly_vol = spy_returns.rolling(window=5).std()
        monthly_vol = spy_returns.rolling(window=21).std()
        
        # HAR forecast (simplified)
        har_forecast = (daily_vol + weekly_vol + monthly_vol) / 3
        excess_vol = realized_vol - har_forecast
        
        # Z-score of excess vol
        risk_signals['HAR_ExcessVol_Z'] = (excess_vol - excess_vol.mean()) / excess_vol.std()
    
    # 5. Credit Spread Signals
    if 'HY_Spread_Change' in market_data.columns:
        risk_signals['Credit_Spread_Change'] = market_data['HY_Spread_Change']
    
    if 'IG_Spread_Change' in market_data.columns:
        risk_signals['IG_Spread_Change'] = market_data['IG_Spread_Change']
    
    # 6. Volatility Signals
    if 'VIX_Change' in market_data.columns:
        risk_signals['VIX_Change'] = market_data['VIX_Change']
    
    # 7. Composite Warning Signal
    warning_components = []
    if 'Systemic_Score' in risk_signals.columns:
        systemic_warning = risk_signals['Systemic_Score'] > risk_signals['Systemic_Score'].quantile(0.95)
        warning_components.append(systemic_warning)
    
    if 'DCC_Corr' in risk_signals.columns:
        dcc_warning = risk_signals['DCC_Corr'] > risk_signals['DCC_Corr'].quantile(0.95)
        warning_components.append(dcc_warning)
    
    if 'HAR_ExcessVol_Z' in risk_signals.columns:
        har_warning = risk_signals['HAR_ExcessVol_Z'] > 2.0
        warning_components.append(har_warning)
    
    if warning_components:
        risk_signals['is_warning'] = pd.concat(warning_components, axis=1).any(axis=1).astype(int)
    
    # 8. Composite Risk Score (normalized combination)
    risk_components = []
    component_weights = {}
    
    if 'Systemic_Score' in risk_signals.columns:
        normalized_systemic = (risk_signals['Systemic_Score'] - risk_signals['Systemic_Score'].mean()) / risk_signals['Systemic_Score'].std()
        risk_components.append(normalized_systemic)
        component_weights['systemic'] = 0.4
    
    if 'Quantile_Signal' in risk_signals.columns:
        normalized_quantile = (risk_signals['Quantile_Signal'] - risk_signals['Quantile_Signal'].mean()) / risk_signals['Quantile_Signal'].std()
        risk_components.append(normalized_quantile)
        component_weights['quantile'] = 0.2
    
    if 'DCC_Corr' in risk_signals.columns:
        normalized_dcc = (risk_signals['DCC_Corr'] - risk_signals['DCC_Corr'].mean()) / risk_signals['DCC_Corr'].std()
        risk_components.append(normalized_dcc)
        component_weights['dcc'] = 0.2
    
    if 'HAR_ExcessVol_Z' in risk_signals.columns:
        risk_components.append(risk_signals['HAR_ExcessVol_Z'])
        component_weights['har'] = 0.2
    
    if risk_components:
        # Weighted combination
        total_weight = sum(component_weights.values())
        weighted_components = []
        
        for i, component in enumerate(risk_components):
            weight = list(component_weights.values())[i] / total_weight
            weighted_components.append(component * weight)
        
        composite_score = pd.concat(weighted_components, axis=1).sum(axis=1)
        risk_signals['Composite_Risk_Score'] = composite_score
    
    return risk_signals.fillna(method='ffill').dropna()

@router.get("/visualization/systemic-risk")
async def get_systemic_risk_visualization(force_refresh: bool = False):
    """
    Get focused systemic risk visualization data.
    """
    try:
        systemic_df, pca_meta = await compute_systemic_risk(force_refresh=force_refresh)
        
        if systemic_df.empty:
            raise HTTPException(status_code=404, detail="No systemic risk data available")
        
        visualization_data = {
            "systemic_risk": visualization_service._series_to_plotly_data(
                systemic_df['Systemic'], 
                "Systemic Risk", 
                "red"
            ),
            "pca_component": visualization_service._series_to_plotly_data(
                systemic_df['PCA'],
                "PCA Component",
                "blue"
            ),
            "credit_component": visualization_service._series_to_plotly_data(
                systemic_df['Credit'],
                "Credit Component", 
                "green"
            ),
            "metadata": {
                "pca_variance": pca_meta.get('explained_variance', {}),
                "date_range": {
                    "start": systemic_df.index[0].strftime('%Y-%m-%d'),
                    "end": systemic_df.index[-1].strftime('%Y-%m-%d')
                },
                "statistics": {
                    "mean_systemic": float(systemic_df['Systemic'].mean()),
                    "std_systemic": float(systemic_df['Systemic'].std()),
                    "current_systemic": float(systemic_df['Systemic'].iloc[-1]) if len(systemic_df) > 0 else 0.0
                }
            }
        }
        
        return {
            "success": True,
            "data": visualization_data,
            "message": "Systemic risk visualization data generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error generating systemic risk visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/visualization/market-overview")
async def get_market_overview_visualization(force_refresh: bool = False):
    """
    Get market overview visualization data including correlations and volatilities.
    """
    try:
        market_data = await get_full_market_dataset(force_refresh=force_refresh)
        
        if market_data.empty:
            raise HTTPException(status_code=404, detail="No market data available")
        
        # Calculate correlation matrix for major assets
        major_assets = ['SPY', 'HYG', 'LQD', 'XLF', 'XLK']
        available_assets = [asset for asset in major_assets if asset in market_data.columns]
        
        if len(available_assets) >= 2:
            asset_returns = market_data[available_assets].pct_change().dropna()
            correlation_matrix = asset_returns.corr()
            corr_data = visualization_service.generate_correlation_matrix_data(correlation_matrix)
        else:
            corr_data = {"error": "Insufficient assets for correlation matrix"}
        
        volatility_data = {}
        for asset in available_assets:
            returns = market_data[asset].pct_change().dropna()
            vol_21d = returns.rolling(window=21).std()
            volatility_data[asset] = visualization_service._series_to_plotly_data(
                vol_21d, 
                f"{asset} 21d Vol", 
                "orange"
            )
        
        return {
            "success": True,
            "data": {
                "correlation_matrix": corr_data,
                "volatilities": volatility_data,
                "available_assets": available_assets,
                "metadata": {
                    "date_range": {
                        "start": market_data.index[0].strftime('%Y-%m-%d'),
                        "end": market_data.index[-1].strftime('%Y-%m-%d')
                    },
                    "data_points": len(market_data)
                }
            },
            "message": "Market overview visualization data generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error generating market overview visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/debug/signal-generation")
async def debug_signal_generation():
    """Debug endpoint to check why signals are null"""
    try:
        # Get fresh data
        full_df = await get_full_market_dataset(force_refresh=True)
        
        result = {
            "full_dataset": {
                "shape": full_df.shape,
                "columns": list(full_df.columns),
                "date_range": f"{full_df.index[0]} to {full_df.index[-1]}" if not full_df.empty else "No data",
                "sample_dates": [str(d) for d in full_df.index[:3]] if not full_df.empty else []
            },
            "required_columns_check": {}
        }
        
        # Check required columns for each signal
        required_checks = {
            "DCC_Correlation": ['XLK', 'XLF'],
            "HAR_ExcessVol": ['SPY'],
            "Quantile_Signal": ['HYG'],
            "Macro_Oil": ['oil_return'],
            "Macro_FX": ['fx_change']
        }
        
        for signal_name, required_cols in required_checks.items():
            missing = [col for col in required_cols if col not in full_df.columns]
            result["required_columns_check"][signal_name] = {
                "required": required_cols,
                "missing": missing,
                "available": [col for col in required_cols if col in full_df.columns],
                "status": "OK" if len(missing) == 0 else "MISSING_DATA"
            }
        
        # Test specific signal calculations with safe value extraction
        signal_tests = {}
        
        # Test DCC Correlation
        if 'XLK' in full_df.columns and 'XLF' in full_df.columns:
            xlk_returns = full_df['XLK'].pct_change().dropna()
            xlf_returns = full_df['XLF'].pct_change().dropna()
            common_idx = xlk_returns.index.intersection(xlf_returns.index)
            if len(common_idx) > 0:
                rolling_corr = xlk_returns.rolling(window=21).corr(xlf_returns)
                latest_val = rolling_corr.iloc[-1] if not rolling_corr.empty else None
                # Safe value extraction
                if latest_val is not None and not pd.isna(latest_val) and np.isfinite(latest_val):
                    signal_tests["DCC_Correlation"] = {
                        "status": "SUCCESS",
                        "data_points": len(rolling_corr.dropna()),
                        "latest_value": float(latest_val)
                    }
                else:
                    signal_tests["DCC_Correlation"] = {"status": "INVALID_VALUE", "value": str(latest_val)}
            else:
                signal_tests["DCC_Correlation"] = {"status": "NO_COMMON_DATES"}
        else:
            signal_tests["DCC_Correlation"] = {"status": "MISSING_ETFS"}
        
        # Test HAR Excess Vol
        if 'SPY' in full_df.columns:
            spy_returns = full_df['SPY'].pct_change().dropna()
            if len(spy_returns) > 21:
                realized_vol = spy_returns.rolling(window=21).std()
                daily_vol = spy_returns.rolling(window=1).std()
                weekly_vol = spy_returns.rolling(window=5).std()
                monthly_vol = spy_returns.rolling(window=21).std()
                
                har_forecast = (daily_vol + weekly_vol + monthly_vol) / 3
                excess_vol = realized_vol - har_forecast
                
                if not excess_vol.dropna().empty:
                    har_z = (excess_vol - excess_vol.mean()) / excess_vol.std()
                    latest_val = har_z.iloc[-1] if not har_z.empty else None
                    if latest_val is not None and not pd.isna(latest_val) and np.isfinite(latest_val):
                        signal_tests["HAR_ExcessVol"] = {
                            "status": "SUCCESS", 
                            "data_points": len(har_z.dropna()),
                            "latest_value": float(latest_val)
                        }
                    else:
                        signal_tests["HAR_ExcessVol"] = {"status": "INVALID_VALUE", "value": str(latest_val)}
                else:
                    signal_tests["HAR_ExcessVol"] = {"status": "NO_EXCESS_VOL_DATA"}
            else:
                signal_tests["HAR_ExcessVol"] = {"status": "INSUFFICIENT_DATA"}
        else:
            signal_tests["HAR_ExcessVol"] = {"status": "MISSING_SPY"}
        
        # Test Quantile Signal
        if 'HYG' in full_df.columns:
            hyg_returns = full_df['HYG'].pct_change().dropna()
            if len(hyg_returns) > 63:
                quantile_signal = hyg_returns.rolling(window=63).quantile(0.05)
                latest_val = quantile_signal.iloc[-1] if not quantile_signal.empty else None
                if latest_val is not None and not pd.isna(latest_val) and np.isfinite(latest_val):
                    signal_tests["Quantile_Signal"] = {
                        "status": "SUCCESS",
                        "data_points": len(quantile_signal.dropna()),
                        "latest_value": float(latest_val)
                    }
                else:
                    signal_tests["Quantile_Signal"] = {"status": "INVALID_VALUE", "value": str(latest_val)}
            else:
                signal_tests["Quantile_Signal"] = {"status": "INSUFFICIENT_DATA"}
        else:
            signal_tests["Quantile_Signal"] = {"status": "MISSING_HYG"}
        
        # Test Macro Signals
        if 'oil_return' in full_df.columns:
            oil_val = full_df['oil_return'].iloc[-1] if not full_df['oil_return'].empty else None
            if oil_val is not None and not pd.isna(oil_val) and np.isfinite(oil_val):
                signal_tests["Macro_Oil"] = {
                    "status": "PRESENT",
                    "latest_value": float(oil_val)
                }
            else:
                signal_tests["Macro_Oil"] = {"status": "INVALID_VALUE", "value": str(oil_val)}
        else:
            signal_tests["Macro_Oil"] = {"status": "MISSING"}
        
        if 'fx_change' in full_df.columns:
            fx_val = full_df['fx_change'].iloc[-1] if not full_df['fx_change'].empty else None
            if fx_val is not None and not pd.isna(fx_val) and np.isfinite(fx_val):
                signal_tests["Macro_FX"] = {
                    "status": "PRESENT", 
                    "latest_value": float(fx_val)
                }
            else:
                signal_tests["Macro_FX"] = {"status": "INVALID_VALUE", "value": str(fx_val)}
        else:
            signal_tests["Macro_FX"] = {"status": "MISSING"}
        
        result["signal_tests"] = signal_tests
        
        # Use FastAPI's built-in JSON handling with our custom serializer
        from fastapi.encoders import jsonable_encoder
        return jsonable_encoder(result, custom_encoder={
            float: lambda x: x if not np.isnan(x) and np.isfinite(x) else None,
            np.float64: lambda x: float(x) if not np.isnan(x) and np.isfinite(x) else None,
            pd.Timestamp: lambda x: x.isoformat()
        })
        
    except Exception as e:
        return {"error": str(e)}