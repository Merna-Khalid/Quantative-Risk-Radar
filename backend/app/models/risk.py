from sqlalchemy import Column, Integer, Float, Boolean, DateTime, JSON, String, Text
from sqlalchemy.sql import func
from app.core.db import Base


class CreditSignalSnapshot(Base):
    __tablename__ = "credit_signal_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    # Add date range fields
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    
    rows = Column(Integer)
    columns = Column(Integer)
    mean_hyg = Column(Float)
    mean_spy = Column(Float)
    snapshot_metadata = Column(JSON)


class PCASnapshot(Base):
    __tablename__ = "pca_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    # Add date range fields
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    
    window = Column(Integer)
    n_components = Column(Integer)
    explained_variance = Column(JSON)
    pca_metadata = Column(JSON)


class SystemicRiskSnapshot(Base):
    __tablename__ = "systemic_risk_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    # Add date range fields
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    
    mean_value = Column(Float)
    std_value = Column(Float)
    systemic_metadata = Column(JSON)


class QuantileRegressionSnapshot(Base):
    __tablename__ = "quantile_regression_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    # Add date range fields
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))

    var_95 = Column(Float)
    var_normal = Column(Float)
    capital_buffer = Column(Float)

    corr_mean = Column(Float)
    corr_vol = Column(Float)
    corr_beta = Column(Float)
    corr_contrib_to_loss = Column(Float)

    quantile_metadata = Column(JSON)


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    
    # Core systemic risk metrics
    systemic_risk = Column(Float)
    systemic_mean = Column(Float)
    systemic_std = Column(Float)
    risk_level = Column(String)  # "low", "medium", "high"
    
    # Core component breakdown
    pca_component = Column(Float)
    credit_component = Column(Float)
    
    # All risk signals from compute_systemic_risk
    quantile_signal = Column(Float)
    dcc_correlation = Column(Float)
    har_excess_vol_z = Column(Float)
    credit_spread_change = Column(Float)
    vix_change = Column(Float)
    is_warning = Column(Boolean)
    composite_risk_score = Column(Float)
    
    credit_spread = Column(Float)
    market_volatility = Column(Float)
    macro_oil = Column(Float)
    macro_fx = Column(Float)
    forecast_next_risk = Column(Float)
    
    # Computation metadata
    data_points = Column(Integer)
    computation_time = Column(String)
    computation_duration = Column(Float)  # seconds
    source = Column(String)
    
    quantile_summary = Column(JSON)
    pca_variance = Column(JSON)
    pca_metadata = Column(JSON)
    
    # Enhanced regime and analysis data
    regime_details = Column(JSON)  
    signal_analysis = Column(JSON)
    component_analysis = Column(JSON)
    
    # DCC-specific analysis
    dcc_regime_analysis = Column(JSON)
    dcc_pair_correlations = Column(JSON)
    
    # Date range metadata
    date_range_metadata = Column(JSON)  # days, start_date, end_date, actual_start, actual_end
    

    available_signals = Column(JSON)
    extra_metadata = Column(JSON)
