from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeTier(Base):
    __tablename__ = "knowledge_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)   # 'state' | 'county' | 'community'
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("knowledge_tiers.id"))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)

    parent: Mapped["KnowledgeTier | None"] = relationship(
        "KnowledgeTier", remote_side="KnowledgeTier.id", back_populates="children"
    )
    children: Mapped[list["KnowledgeTier"]] = relationship(
        "KnowledgeTier", back_populates="parent"
    )
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="tier")
