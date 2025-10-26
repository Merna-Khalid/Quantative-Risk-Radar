from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, func
from app.core.db import Base

class SignalResult(Base):
    __tablename__ = "signal_results"

    id = Column(Integer, primary_key=True, index=True)
    signal_hash = Column(String, unique=True, index=True)
    strategy = Column(String)
    filter_type = Column(String)
    risk_score = Column(Float)
    result_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
