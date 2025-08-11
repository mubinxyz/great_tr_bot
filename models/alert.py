# models/alert.py
import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from services.db_service import Base

class AlertDirection(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String, nullable=False)         # store normalized symbol (e.g. "EUR/USD")
    target_price = Column(Float, nullable=False)
    direction = Column(SAEnum(AlertDirection), nullable=False)  # "above" / "below"
    timeframes = Column(String, nullable=False)     # comma-separated canonical timeframes
    triggered = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    triggered_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="alerts")
