from fastapi import APIRouter, UploadFile, Form, HTTPException
from pydantic import BaseModel

router = APIRouter()


class IngestResponse(BaseModel):
    document_id: int
    title: str
    tier_id: int
    chunks_created: int
    ocr_processed: bool
    ocr_confidence: float | None


@router.post("/", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile,
    tier_id: int = Form(...),
    title: str = Form(...),
    doc_type: str = Form(...),
) -> IngestResponse:
    # TODO: implement — call services/ocr.py, chunker.py, embedder.py, store in MinIO + DB
    raise HTTPException(status_code=501, detail="Not implemented")
