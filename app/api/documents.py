from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

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


@router.get("/", response_model=list[DocumentSummary])
async def list_documents(
    tier_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentSummary]:
    # TODO: implement — explicit column projection, filter superseded_by_id IS NULL
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{document_id}", response_model=DocumentSummary)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)) -> DocumentSummary:
    # TODO: implement
    raise HTTPException(status_code=501, detail="Not implemented")
