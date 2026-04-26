from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class QueryLog(Base):
    __tablename__ = "query_log"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), nullable=True)
    tier_id = Column(Integer, ForeignKey("knowledge_tiers.id"), nullable=True)
    query_source = Column(String(20), nullable=False)
    query_text = Column(Text, nullable=False)
    retrieved_chunks = Column(JSONB, nullable=True)
    response_text = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, server_default="true", nullable=False)
    error = Column(Text, nullable=True)
    pii_redacted = Column(Boolean, server_default="false", nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
