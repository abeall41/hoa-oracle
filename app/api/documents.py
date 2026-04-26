from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Document

router = APIRouter()


class DocumentSummary(BaseModel):
    """Projection model — never includes raw_text."""
    id: int
    tier_id: int
    title: str
    doc_type: str | None
    data_category: str
    ocr_processed: bool
    ocr_confidence: float | None
    page_count: int | None
    superseded_by_id: int | None


# Explicit column list — raw_text is deliberately excluded
_SUMMARY_COLS = [
    Document.id,
    Document.tier_id,
    Document.title,
    Document.doc_type,
    Document.data_category,
    Document.ocr_processed,
    Document.ocr_confidence,
    Document.page_count,
    Document.superseded_by_id,
]


@router.get("/", response_model=list[DocumentSummary])
async def list_documents(
    tier_id: int | None = None,
    include_superseded: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentSummary]:
    stmt = select(*_SUMMARY_COLS)
    if not include_superseded:
        stmt = stmt.where(Document.superseded_by_id.is_(None))
    if tier_id is not None:
        stmt = stmt.where(Document.tier_id == tier_id)
    stmt = stmt.order_by(Document.tier_id, Document.title)

    result = await db.execute(stmt)
    rows = result.mappings().all()
    return [DocumentSummary(**dict(row)) for row in rows]


@router.get("/{document_id}", response_model=DocumentSummary)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> DocumentSummary:
    result = await db.execute(
        select(*_SUMMARY_COLS).where(Document.id == document_id)
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return DocumentSummary(**dict(row))


@router.get("/{document_id}/text")
async def get_document_text(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the raw extracted text for a document. Used by the UI text viewer."""
    result = await db.execute(
        select(Document.id, Document.title, Document.raw_text)
        .where(Document.id == document_id)
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return {"id": row["id"], "title": row["title"], "raw_text": row["raw_text"] or ""}
