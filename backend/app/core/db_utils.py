from app.core.db import AsyncSessionLocal
from app.models.risk import CreditSignalSnapshot, PCASnapshot, SystemicRiskSnapshot, QuantileRegressionSnapshot, RiskSnapshot
import numpy as np
from sqlalchemy import and_, select
from datetime import datetime, timedelta


async def save_credit_snapshot(df, start_date=None, end_date=None):
    async with AsyncSessionLocal() as session:
        # Extract dates from DataFrame if not provided
        if start_date is None and not df.empty:
            start_date = df.index[0].to_pydatetime() if hasattr(df.index[0], 'to_pydatetime') else df.index[0]
        if end_date is None and not df.empty:
            end_date = df.index[-1].to_pydatetime() if hasattr(df.index[-1], 'to_pydatetime') else df.index[-1]
            
        snapshot = CreditSignalSnapshot(
            start_date=start_date,
            end_date=end_date,
            rows=df.shape[0],
            columns=df.shape[1],
            mean_hyg=float(df['HYG'].mean()) if 'HYG' in df.columns else np.nan,
            mean_spy=float(df['SPY'].mean()) if 'SPY' in df.columns else np.nan,
            snapshot_metadata={
                "columns": list(df.columns),
                "date_range": {
                    "start": str(start_date) if start_date else None,
                    "end": str(end_date) if end_date else None
                }
            }
        )
        session.add(snapshot)
        await session.commit()


async def save_pca_snapshot(evr, scores, loadings, window, n_components, tickers, start_date=None, end_date=None):
    async with AsyncSessionLocal() as session:
        # Extract dates from scores if not provided
        if start_date is None and scores is not None and not scores.empty:
            start_date = scores.index[0].to_pydatetime() if hasattr(scores.index[0], 'to_pydatetime') else scores.index[0]
        if end_date is None and scores is not None and not scores.empty:
            end_date = scores.index[-1].to_pydatetime() if hasattr(scores.index[-1], 'to_pydatetime') else scores.index[-1]
            
        snapshot = PCASnapshot(
            start_date=start_date,
            end_date=end_date,
            window=window,
            n_components=n_components,
            explained_variance=evr.iloc[-1].to_dict() if evr is not None and not evr.empty else {},
            pca_metadata={
                "tickers": tickers, 
                "latest_scores": scores.iloc[-1].to_dict() if scores is not None and not scores.empty else {},
                "date_range": {
                    "start": str(start_date) if start_date else None,
                    "end": str(end_date) if end_date else None
                }
            }
        )
        session.add(snapshot)
        await session.commit()


async def save_systemic_snapshot(series, start_date=None, end_date=None):
    async with AsyncSessionLocal() as session:
        # Extract dates from series if not provided
        if start_date is None and not series.empty:
            start_date = series.index[0].to_pydatetime() if hasattr(series.index[0], 'to_pydatetime') else series.index[0]
        if end_date is None and not series.empty:
            end_date = series.index[-1].to_pydatetime() if hasattr(series.index[-1], 'to_pydatetime') else series.index[-1]
            
        snapshot = SystemicRiskSnapshot(
            start_date=start_date,
            end_date=end_date,
            mean_value=float(series["Systemic"].mean()),
            std_value=float(series["Systemic"].std()),
            systemic_metadata={
                "start": str(series.index[0]) if not series.empty else None,
                "end": str(series.index[-1]) if not series.empty else None,
                "date_range": {
                    "start": str(start_date) if start_date else None,
                    "end": str(end_date) if end_date else None
                }
            }
        )
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)
        return snapshot


async def save_quantile_results(summary_dict, results=None, start_date=None, end_date=None):
    async with AsyncSessionLocal() as session:
        snapshot = QuantileRegressionSnapshot(
            start_date=start_date,
            end_date=end_date,
            var_95=summary_dict.get("VaR_95"),
            var_normal=summary_dict.get("VaR_Normal"),
            capital_buffer=summary_dict.get("Capital_Buffer"),
            corr_mean=summary_dict["Correlation_Risk"].get("mean_corr") if "Correlation_Risk" in summary_dict else None,
            corr_vol=summary_dict["Correlation_Risk"].get("vol_corr") if "Correlation_Risk" in summary_dict else None,
            corr_beta=summary_dict["Correlation_Risk"].get("corr_beta") if "Correlation_Risk" in summary_dict else None,
            corr_contrib_to_loss=summary_dict["Correlation_Risk"].get("corr_contrib_to_loss") if "Correlation_Risk" in summary_dict else None,
            quantile_metadata={
                "quantiles": list(results.keys()) if results else None,
                "date_range": {
                    "start": str(start_date) if start_date else None,
                    "end": str(end_date) if end_date else None
                }
            }
        )
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)
        return snapshot
    
async def save_risk_snapshot(metrics: dict, start_date: datetime = None, end_date: datetime = None):
    async with AsyncSessionLocal() as session:
        safe_metrics = metrics.copy()
        
        unsupported_fields = [
            'pca_component', 'credit_component', 'quantile_signal', 
            'dcc_correlation', 'corr_exceeds_bootstrap', 'har_excess_vol_z',
            'credit_spread_change', 'ig_spread_change', 'vix_change',
            'is_warning', 'composite_risk_score', 'regime_details',
            'signal_analysis', 'component_analysis'
        ]
        
        for field in unsupported_fields:
            safe_metrics.pop(field, None)
        
        snapshot = RiskSnapshot(
            # Date range
            start_date=start_date or datetime.utcnow() - timedelta(days=1),
            end_date=end_date or datetime.utcnow(),
            
            # Risk metrics (only include fields that exist in the schema)
            systemic_risk=safe_metrics.get("systemic_risk"),
            systemic_mean=safe_metrics.get("systemic_mean"),
            systemic_std=safe_metrics.get("systemic_std"),
            credit_spread=safe_metrics.get("credit_spread"),
            market_volatility=safe_metrics.get("market_volatility"),
            risk_level=safe_metrics.get("risk_level"),
            dcc_correlation=safe_metrics.get("dcc_correlation"),
            macro_oil=safe_metrics.get("macro_oil"),
            macro_fx=safe_metrics.get("macro_fx"),
            forecast_next_risk=safe_metrics.get("forecast_next_risk"),
            data_points=safe_metrics.get("data_points"),
            computation_time=safe_metrics.get("computation_time"),
            source=safe_metrics.get("source", "risk_engine"),
            
            # Rich metadata - store new signals in JSON fields
            quantile_summary=safe_metrics.get("quantile_summary", {}),
            pca_variance=safe_metrics.get("pca_variance", {}),
            extra_metadata={
                "pca_metadata": safe_metrics.get("pca_metadata", {}),
                "computation_duration": safe_metrics.get("computation_duration"),
                "timestamp": safe_metrics.get("timestamp"),
                # Store new signals in the extra_metadata JSON field
                "enhanced_signals": {
                    "quantile_signal": metrics.get("quantile_signal"),
                    "dcc_correlation": metrics.get("dcc_correlation"),
                    "har_excess_vol": metrics.get("har_excess_vol"),
                    "credit_spread_change": metrics.get("credit_spread_change"),
                    "vix_change": metrics.get("vix_change"),
                    "composite_warning": metrics.get("composite_warning"),
                    "composite_risk_score": metrics.get("composite_risk_score"),
                    "regime_details": metrics.get("regime_details"),
                    "signal_analysis": metrics.get("signal_analysis"),
                    "component_analysis": metrics.get("component_analysis")
                }
            }
        )
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)
        return snapshot


async def get_risk_snapshots_by_date_range(start_date: str = None, end_date: str = None, days: int = None):
    async with AsyncSessionLocal() as session:
        query = select(RiskSnapshot)

        if days:
            end_date_filter = datetime.now()
            start_date_filter = end_date_filter - timedelta(days=days)
            query = query.where(
                and_(
                    RiskSnapshot.start_date >= start_date_filter,
                    RiskSnapshot.end_date <= end_date_filter
                )
            )
        elif start_date and end_date:
            start_date_filter = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_date_filter = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.where(
                and_(
                    RiskSnapshot.start_date >= start_date_filter,
                    RiskSnapshot.end_date <= end_date_filter
                )
            )
        elif start_date:
            start_date_filter = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.where(RiskSnapshot.start_date >= start_date_filter)
        elif end_date:
            end_date_filter = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.where(RiskSnapshot.end_date <= end_date_filter)
        
        query = query.order_by(RiskSnapshot.start_date.asc())
        result = await session.execute(query)
        snapshots = result.scalars().all()
        
        return snapshots

async def get_risk_snapshots_with_signals(
    start_date: str = None, 
    end_date: str = None,
    min_composite_score: float = None,
    has_warning: bool = None,
    risk_level: str = None
):
    async with AsyncSessionLocal() as session:
        query = select(RiskSnapshot)
        
        if start_date:
            start_date_filter = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.where(RiskSnapshot.start_date >= start_date_filter)
        if end_date:
            end_date_filter = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.where(RiskSnapshot.end_date <= end_date_filter)
        
        if min_composite_score is not None:
            query = query.where(RiskSnapshot.composite_risk_score >= min_composite_score)
        
        if has_warning is not None:
            query = query.where(RiskSnapshot.is_warning == has_warning)
        
        if risk_level:
            query = query.where(RiskSnapshot.risk_level == risk_level)
        
        query = query.order_by(RiskSnapshot.start_date.asc())
        result = await session.execute(query)
        snapshots = result.scalars().all()
        
        return snapshots