import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.core.analytics.pca_analysis import compute_rolling_pca
from app.services.data_pipeline import get_full_market_dataset, get_credit_signals
import logging

logger = logging.getLogger(__name__)

async def compute_systemic_risk(
    force_refresh: bool = False, 
    window: int = 20, 
    _internal_call: bool = False,
    days: int = None,
    start_date: str = None, 
    end_date: str = None
):
    """
    Enhanced systemic risk computation including ALL risk signals from analytics.
    Returns: (systemic_df, meta)
      - systemic_df: pd.DataFrame with all risk signals including HAR, DCC, Quantile, etc.
      - meta: dict with PCA metadata and computation details
    """
    try:
        # Apply _internal_call logic to prevent nested refreshes
        if _internal_call:
            force_refresh = False

        # 1) Get full market dataset
        try:
            full_df = await get_full_market_dataset(force_refresh=force_refresh, _internal_call=_internal_call)
        except Exception as e:
            logger.warning(f"Failed to get full market dataset, falling back to credit signals: {e}")
            full_df = await get_credit_signals(force_refresh=force_refresh, _internal_call=_internal_call)

        # 2) PCA result
        pca_result = await compute_rolling_pca(window=window, force_refresh=force_refresh)
        pca_signal = pca_result["signal"]
        if isinstance(pca_signal, pd.DataFrame):
            pca_signal = pca_signal.iloc[:, 0]

        pca_signal = pd.Series(pca_signal, name="PCA")
        
        # 3) Extract PCA metadata
        pca_meta = {
            "explained_variance": pca_result.get("explained_variance", {}),
            "components": pca_result.get("components", {}),
            "last_update": datetime.now().isoformat()
        }
        
        if isinstance(pca_meta["explained_variance"], pd.DataFrame):
            pca_meta["explained_variance"] = pca_meta["explained_variance"].iloc[-1].to_dict() if not pca_meta["explained_variance"].empty else {}

        # 4) Credit factor
        credit_series = _extract_credit_series(full_df, pca_signal)

        # 5) Create base systemic risk DataFrame with all components
        systemic_df = _create_comprehensive_systemic_df(pca_signal, credit_series, full_df)

        # 6) Add all additional risk signals from analytics router
        systemic_df = await _add_all_risk_signals(systemic_df, full_df)

        # 7) Apply date range filtering
        if days or start_date or end_date:
            systemic_df = _filter_by_date_range(systemic_df, days, start_date, end_date)

        # 8) Final validation
        systemic_df = _validate_output_format(systemic_df)

        logger.info(f"Computed comprehensive systemic risk with {len(systemic_df.columns)} signals")
        return systemic_df, pca_meta

    except Exception as e:
        logger.error(f"Error in compute_systemic_risk: {e}")
        empty_df = pd.DataFrame(columns=[
            "Systemic", "PCA", "Credit", "Quantile_Signal", "DCC_Corr", 
            "Corr_Exceeds_Bootstrap", "HAR_ExcessVol_Z", "Credit_Spread_Change",
            "IG_Spread_Change", "VIX_Change", "is_warning", "Composite_Risk_Score"
        ])
        empty_meta = {"explained_variance": {}, "error": str(e)}
        return empty_df, empty_meta


def _extract_credit_series(full_df, pca_signal):
    """Extract credit series from the full dataset"""
    credit_series = None
    
    # Priority 1: Use HYG returns
    if "HYG" in full_df.columns and not full_df["HYG"].empty:
        try:
            credit_series = full_df["HYG"].pct_change().rolling(5).mean().dropna()
            credit_series.name = "Credit"
        except Exception as e:
            logger.warning(f"Error processing HYG data: {e}")
    
    # Priority 2: Use credit_ratio if available
    if credit_series is None and "credit_ratio" in full_df.columns and not full_df["credit_ratio"].empty:
        try:
            credit_series = full_df["credit_ratio"].rolling(20).mean().dropna()
            credit_series.name = "Credit"
        except Exception as e:
            logger.warning(f"Error processing credit_ratio data: {e}")
    
    # Fallback: Create a zero series
    if credit_series is None:
        logger.warning("No suitable credit data found, using zero series as fallback")
        credit_series = pd.Series(0, index=pca_signal.index, name="Credit")
    
    return credit_series


def _create_comprehensive_systemic_df(pca_signal, credit_series, full_df):
    """Create the base systemic risk DataFrame with core components"""
    # Align PCA and Credit series
    pca_aligned = pca_signal.dropna()
    credit_aligned = credit_series.dropna()
    
    # Find common index for alignment
    common_idx = pca_aligned.index.intersection(credit_aligned.index)
    
    if len(common_idx) == 0:
        logger.warning("No overlapping dates between PCA and credit series, using PCA only")
        systemic_series = pca_aligned
        systemic_df = pd.DataFrame({
            "Systemic": systemic_series,
            "PCA": pca_aligned,
            "Credit": pd.Series(0, index=pca_aligned.index, name="Credit")
        })
    else:
        # Align both series to common index
        pca_aligned = pca_aligned.loc[common_idx]
        credit_aligned = credit_aligned.loc[common_idx]
        
        # Create systemic score as weighted combination
        systemic_series = (pca_aligned + credit_aligned) / 2
        
        systemic_df = pd.DataFrame({
            "Systemic": systemic_series,
            "PCA": pca_aligned,
            "Credit": credit_aligned
        })
    
    return systemic_df.dropna()


async def _add_all_risk_signals(systemic_df: pd.DataFrame, market_data: pd.DataFrame) -> pd.DataFrame:
    """Add ALL risk signals with proper NaN handling"""
    risk_signals = systemic_df.copy()
    
    # 1. Quantile Signal (5th percentile of HYG returns) - FIXED
    if 'HYG' in market_data.columns:
        hyg_returns = market_data['HYG']
        if len(hyg_returns.dropna()) >= 63:  # Check for enough non-NaN data
            # Use min_periods to avoid initial NaN values
            quantile_signal = hyg_returns.rolling(window=63, min_periods=50).quantile(0.05)
            # Forward fill to handle any remaining gaps
            risk_signals['Quantile_Signal'] = quantile_signal.ffill()
            logger.info(f"Quantile signal generated: {len(quantile_signal.dropna())} non-NaN points")
        else:
            logger.warning(f"Insufficient HYG data for quantile signal: {len(hyg_returns.dropna())} points")
    
    # 2. DCC Correlation Signal (XLK vs XLF) - FIXED
    if 'XLK' in market_data.columns and 'XLF' in market_data.columns:
        xlk_returns = market_data['XLK']
        xlf_returns = market_data['XLF']
        
        # Only proceed if we have enough non-NaN data
        xlk_clean = xlk_returns.dropna()
        xlf_clean = xlf_returns.dropna()
        
        if len(xlk_clean) >= 21 and len(xlf_clean) >= 21:
            # Align the clean series
            common_idx = xlk_clean.index.intersection(xlf_clean.index)
            if len(common_idx) >= 21:
                xlk_aligned = xlk_clean.loc[common_idx]
                xlf_aligned = xlf_clean.loc[common_idx]
                
                # Rolling correlation with min_periods
                rolling_corr = xlk_aligned.rolling(window=21, min_periods=15).corr(xlf_aligned)
                
                # Reindex back to original index and forward fill
                rolling_corr_full = rolling_corr.reindex(market_data.index).ffill()
                risk_signals['DCC_Corr'] = rolling_corr_full
                
                # Bootstrap exceedance
                if not rolling_corr.dropna().empty:
                    corr_threshold = rolling_corr.quantile(0.95)
                    risk_signals['Corr_Exceeds_Bootstrap'] = (rolling_corr_full > corr_threshold).astype(int)
                
                logger.info(f"DCC correlation generated: {len(rolling_corr.dropna())} non-NaN points")
            else:
                logger.warning("Insufficient common dates for DCC correlation")
        else:
            logger.warning(f"Insufficient data for DCC: XLK={len(xlk_clean)}, XLF={len(xlf_clean)}")
    
    # 3. HAR Excess Volatility (SPY-based) - FIXED
    if 'SPY' in market_data.columns:
        spy_returns = market_data['SPY']
        spy_clean = spy_returns.dropna()
        
        if len(spy_clean) >= 21:
            # Realized volatility (21-day)
            realized_vol = spy_clean.rolling(window=21, min_periods=15).std()
            
            # HAR model components - ensure we have enough data for each
            daily_vol = spy_clean.rolling(window=1).std()
            weekly_vol = spy_clean.rolling(window=5, min_periods=3).std()
            monthly_vol = spy_clean.rolling(window=21, min_periods=15).std()
            
            # HAR forecast - only where all components are available
            har_forecast = (daily_vol + weekly_vol + monthly_vol) / 3
            
            # Calculate excess vol only where we have both realized and forecast
            excess_vol_mask = realized_vol.notna() & har_forecast.notna()
            if excess_vol_mask.any():
                excess_vol = realized_vol - har_forecast
                excess_vol_clean = excess_vol.dropna()
                
                if len(excess_vol_clean) >= 10:
                    # Calculate Z-score using only clean data
                    har_z = (excess_vol - excess_vol_clean.mean()) / excess_vol_clean.std()
                    # Reindex and forward fill
                    har_z_full = har_z.reindex(market_data.index).ffill()
                    risk_signals['HAR_ExcessVol_Z'] = har_z_full
                    logger.info(f"HAR excess vol generated: {len(excess_vol_clean)} non-NaN points")
                else:
                    logger.warning("Insufficient excess vol data for Z-score")
            else:
                logger.warning("No overlapping data for HAR excess vol calculation")
        else:
            logger.warning(f"Insufficient SPY data for HAR: {len(spy_clean)} points")
    
    # 4. Credit Spread Signals
    if 'HY_Spread_Change' in market_data.columns:
        risk_signals['Credit_Spread_Change'] = market_data['HY_Spread_Change'].ffill()
    
    if 'IG_Spread_Change' in market_data.columns:
        risk_signals['IG_Spread_Change'] = market_data['IG_Spread_Change'].ffill()
    
    # 5. Volatility Signals
    if 'VIX_Change' in market_data.columns:
        risk_signals['VIX_Change'] = market_data['VIX_Change'].ffill()
    
    # 6. Macro signals (already working)
    if 'oil_return' in market_data.columns:
        risk_signals['oil_return'] = market_data['oil_return'].ffill()
    
    if 'fx_change' in market_data.columns:
        risk_signals['fx_change'] = market_data['fx_change'].ffill()
    
    # 7. Composite Warning Signal
    risk_signals = _add_composite_warning_signal(risk_signals)
    
    # 8. Composite Risk Score
    risk_signals = _add_composite_risk_score(risk_signals)
    
    # Final cleanup: Fill any remaining NaN values in numeric columns
    numeric_cols = risk_signals.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if col in risk_signals.columns:
            # Count NaN values for logging
            nan_count = risk_signals[col].isna().sum()
            if nan_count > 0:
                logger.info(f"Filling {nan_count} NaN values in {col}")
            risk_signals[col] = risk_signals[col].ffill().bfill().fillna(0)
    
    logger.info(f"Final risk signals: {len(risk_signals)} rows, {len(risk_signals.columns)} columns")
    logger.info(f"Signals with data: {[col for col in risk_signals.columns if risk_signals[col].notna().any()]}")
    
    return risk_signals


def _add_composite_warning_signal(risk_signals: pd.DataFrame) -> pd.DataFrame:
    """Add composite warning signal based on multiple risk indicators"""
    warning_components = []
    
    if 'Systemic_Score' in risk_signals.columns:
        systemic_warning = risk_signals['Systemic_Score'] > risk_signals['Systemic_Score'].quantile(0.95)
        warning_components.append(systemic_warning)
    elif 'Systemic' in risk_signals.columns:
        systemic_warning = risk_signals['Systemic'] > risk_signals['Systemic'].quantile(0.95)
        warning_components.append(systemic_warning)
    
    if 'DCC_Corr' in risk_signals.columns:
        dcc_warning = risk_signals['DCC_Corr'] > risk_signals['DCC_Corr'].quantile(0.95)
        warning_components.append(dcc_warning)
    
    if 'HAR_ExcessVol_Z' in risk_signals.columns:
        har_warning = risk_signals['HAR_ExcessVol_Z'] > 2.0
        warning_components.append(har_warning)
    
    if warning_components:
        # Align all warning components to the same index
        aligned_warnings = []
        for warning in warning_components:
            aligned_warning = warning.reindex(risk_signals.index).fillna(False)
            aligned_warnings.append(aligned_warning)
        
        # Combine warnings
        if aligned_warnings:
            combined_warnings = pd.concat(aligned_warnings, axis=1)
            risk_signals['is_warning'] = combined_warnings.any(axis=1).astype(int)
    
    return risk_signals


def _add_composite_risk_score(risk_signals: pd.DataFrame) -> pd.DataFrame:
    """Add composite risk score as weighted combination of all signals"""
    risk_components = []
    component_weights = {}
    
    # Systemic Score (highest weight)
    if 'Systemic_Score' in risk_signals.columns:
        normalized_systemic = (risk_signals['Systemic_Score'] - risk_signals['Systemic_Score'].mean()) / risk_signals['Systemic_Score'].std()
        risk_components.append(normalized_systemic)
        component_weights['systemic'] = 0.4
    elif 'Systemic' in risk_signals.columns:
        normalized_systemic = (risk_signals['Systemic'] - risk_signals['Systemic'].mean()) / risk_signals['Systemic'].std()
        risk_components.append(normalized_systemic)
        component_weights['systemic'] = 0.4
    
    # Quantile Signal
    if 'Quantile_Signal' in risk_signals.columns:
        normalized_quantile = (risk_signals['Quantile_Signal'] - risk_signals['Quantile_Signal'].mean()) / risk_signals['Quantile_Signal'].std()
        risk_components.append(normalized_quantile)
        component_weights['quantile'] = 0.2
    
    # DCC Correlation
    if 'DCC_Corr' in risk_signals.columns:
        normalized_dcc = (risk_signals['DCC_Corr'] - risk_signals['DCC_Corr'].mean()) / risk_signals['DCC_Corr'].std()
        risk_components.append(normalized_dcc)
        component_weights['dcc'] = 0.2
    
    # HAR Excess Volatility
    if 'HAR_ExcessVol_Z' in risk_signals.columns:
        risk_components.append(risk_signals['HAR_ExcessVol_Z'])
        component_weights['har'] = 0.2
    
    # Credit Spread Change
    if 'Credit_Spread_Change' in risk_signals.columns:
        normalized_credit = (risk_signals['Credit_Spread_Change'] - risk_signals['Credit_Spread_Change'].mean()) / risk_signals['Credit_Spread_Change'].std()
        risk_components.append(normalized_credit)
        component_weights['credit_spread'] = 0.1
    
    # VIX Change
    if 'VIX_Change' in risk_signals.columns:
        normalized_vix = (risk_signals['VIX_Change'] - risk_signals['VIX_Change'].mean()) / risk_signals['VIX_Change'].std()
        risk_components.append(normalized_vix)
        component_weights['vix'] = 0.1
    
    if risk_components:
        # Align all components to the same index
        aligned_components = []
        for component in risk_components:
            aligned_component = component.reindex(risk_signals.index).fillna(0)
            aligned_components.append(aligned_component)
        
        # Weighted combination
        total_weight = sum(component_weights.values())
        weighted_components = []
        
        for i, component in enumerate(aligned_components):
            weight_key = list(component_weights.keys())[i]
            weight = component_weights[weight_key] / total_weight
            weighted_components.append(component * weight)
        
        if weighted_components:
            composite_score = pd.concat(weighted_components, axis=1).sum(axis=1)
            risk_signals['Composite_Risk_Score'] = composite_score
    
    return risk_signals


def _filter_by_date_range(df, days=None, start_date=None, end_date=None):
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
        # Last N days from most recent date in data
        if df.index.empty:
            return df
        end_date_real = df.index.max()
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


def _validate_output_format(systemic_df):
    """Ensure the output DataFrame has the expected format and columns"""
    # Ensure we have at least the core columns
    core_columns = ["Systemic", "PCA", "Credit"]
    for col in core_columns:
        if col not in systemic_df.columns:
            systemic_df[col] = 0.0
    
    # Ensure index is proper datetime
    if not pd.api.types.is_datetime64_any_dtype(systemic_df.index):
        try:
            systemic_df.index = pd.to_datetime(systemic_df.index)
        except:
            logger.error("Could not convert index to datetime")
    
    # Sort by date
    systemic_df = systemic_df.sort_index()
    
    return systemic_df