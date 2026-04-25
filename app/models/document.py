from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tier_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_tiers.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Phase 1: 'declaration'|'bylaws'|'statute'|'ordinance'|'resolution'|'minutes'
    # Phase 3+: 'email'|'invoice'|'work_order'|'financial_record'|'communication'
    doc_type: Mapped[str | None] = mapped_column(String(100))
    # 'compliance' | 'operational' | 'financial' | 'communication'
    data_category: Mapped[str] = mapped_column(String(50), default="compliance")
    file_path: Mapped[str | None] = mapped_column(String(1000))
    original_filename: Mapped[str | None] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    ocr_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    # Never SELECT * on this table — raw_text is excluded from all list/search queries
    raw_text: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    effective_date: Mapped[date | None] = mapped_column(Date)
    superseded_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("documents.id"))
    version_note: Mapped[str | None] = mapped_column(String(500))
    pii_notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tier: Mapped["KnowledgeTier"] = relationship("KnowledgeTier", back_populates="documents")
    superseded_by: Mapped["Document | None"] = relationship(
        "Document", remote_side="Document.id"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
