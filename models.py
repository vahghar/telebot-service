# models.py
from sqlalchemy import Column, BigInteger, DateTime, Integer, String
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RebalanceEvent(Base):
    """
    Stores a record of rebalance events for which notifications have been sent.
    """
    __tablename__ = "rebalance_events"

    id = Column(Integer, primary_key=True, index=True)
    rebalance_id = Column(String, unique=True, index=True, nullable=False)
    transaction_hash = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())