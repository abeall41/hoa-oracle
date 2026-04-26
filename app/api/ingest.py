import logging
from datetime import date

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.chunk import ChunkEmbedding, DocumentChunk
from app.models.document import Document
from app.models.tier import KnowledgeTier
from app.services.chunker import chunk_text
from app.services.embedder import embed_batch
from app.services.ocr import OCRResult, extract_text_from_docx, extract_text_from_pdf
from storage.minio_client import upload_document

logger = logging.getLogger(__name__)

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
    title: str = Form(...),
    doc_type: str = Form(...),
    tier_id: int | None = Form(None),
    tier_slug: str | None = Form(None),
    effective_date: str | None = Form(None),   # ISO date string YYYY-MM-DD
    data_category: str = Form("compliance"),
    # 'amendment' creates a new version row; 'correction' overwrites the existing record.
    # Required only when a non-superseded document with the same tier+title+doc_type exists.
    action: str | None = Form(None),
) -> IngestResponse:
    if tier_id is None and tier_slug is None:
        raise HTTPException(status_code=422, detail="Provide either tier_id or tier_slug")

    file_bytes = await file.read()
    filename = file.filename or "upload"
    content_type = file.content_type or "application/octet-stream"

    async with AsyncSessionLocal() as db:
        # Resolve tier by slug or ID
        if tier_slug:
            tier_result = await db.execute(
                select(KnowledgeTier).where(KnowledgeTier.slug == tier_slug)
            )
        else:
            tier_result = await db.execute(
                select(KnowledgeTier).where(KnowledgeTier.id == tier_id)
            )
        tier = tier_result.scalar_one_or_none()
        if tier is None:
            identifier = tier_slug or str(tier_id)
            raise HTTPException(status_code=404, detail=f"Tier '{identifier}' not found")

        # Check for existing non-superseded document with same identity
        existing_result = await db.execute(
            select(Document).where(
                Document.tier_id == tier_id,
                Document.title == title,
                Document.doc_type == doc_type,
                Document.superseded_by_id.is_(None),
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None and action is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A current document '{title}' (type={doc_type}) already exists in tier "
                    f"{tier_id} (id={existing.id}). "
                    "Re-submit with action='amendment' to create a new version or "
                    "action='correction' to overwrite the existing record."
                ),
            )

        # Extract text
        mime = content_type.lower()
        if "pdf" in mime or filename.lower().endswith(".pdf"):
            ocr_result = await extract_text_from_pdf(file_bytes)
        elif "word" in mime or filename.lower().endswith(".docx"):
            ocr_result = await extract_text_from_docx(file_bytes)
        else:
            # Plain text or unknown — treat content as-is
            ocr_result = OCRResult(
                text=file_bytes.decode("utf-8", errors="replace"),
                confidence=1.0,
                ocr_applied=False,
            )

        # Upload raw file to MinIO
        object_path = await upload_document(
            tier_type=tier.tier,
            tier_slug=tier.slug,
            filename=filename,
            data=file_bytes,
            content_type=content_type,
        )

        eff_date: date | None = None
        if effective_date:
            try:
                eff_date = date.fromisoformat(effective_date)
            except ValueError:
                raise HTTPException(
                    status_code=422, detail=f"Invalid effective_date format: {effective_date!r}"
                )

        # Handle amendment vs correction vs new
        if existing is not None and action == "amendment":
            # Create new document row; mark the old one as superseded after we have the new ID
            doc = Document(
                tier_id=tier_id,
                title=title,
                doc_type=doc_type,
                data_category=data_category,
                file_path=object_path,
                original_filename=filename,
                mime_type=content_type,
                ocr_processed=ocr_result.ocr_applied,
                ocr_confidence=ocr_result.confidence if ocr_result.ocr_applied else None,
                raw_text=ocr_result.text,
                effective_date=eff_date,
                version_note=f"Amendment superseding document {existing.id}",
            )
            db.add(doc)
            await db.flush()  # get doc.id before updating existing
            existing.superseded_by_id = doc.id
            logger.info(
                "Amendment: new document id=%d supersedes id=%d", doc.id, existing.id
            )

        elif existing is not None and action == "correction":
            # Overwrite the existing record in place
            existing.file_path = object_path
            existing.original_filename = filename
            existing.mime_type = content_type
            existing.ocr_processed = ocr_result.ocr_applied
            existing.ocr_confidence = ocr_result.confidence if ocr_result.ocr_applied else None
            existing.raw_text = ocr_result.text
            existing.effective_date = eff_date
            # Delete old chunks so they are re-generated cleanly
            old_chunks = await db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == existing.id)
            )
            for chunk_row in old_chunks.scalars():
                await db.delete(chunk_row)
            doc = existing
            logger.info("Correction: overwriting document id=%d", doc.id)

        else:
            # New document
            doc = Document(
                tier_id=tier_id,
                title=title,
                doc_type=doc_type,
                data_category=data_category,
                file_path=object_path,
                original_filename=filename,
                mime_type=content_type,
                ocr_processed=ocr_result.ocr_applied,
                ocr_confidence=ocr_result.confidence if ocr_result.ocr_applied else None,
                raw_text=ocr_result.text,
                effective_date=eff_date,
            )
            db.add(doc)
            await db.flush()

        # Chunk the extracted text
        chunks = chunk_text(ocr_result.text)
        if not chunks:
            raise HTTPException(
                status_code=422, detail="No text could be extracted from the uploaded file."
            )

        # Generate embeddings for all chunks in one batch call
        try:
            vectors = await embed_batch([c.content for c in chunks])
        except RuntimeError as exc:
            # embed_batch raises RuntimeError on model version mismatch — halt this ingest
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        chunk_rows = []
        for chunk, vector in zip(chunks, vectors):
            dc = DocumentChunk(
                document_id=doc.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                section_ref=chunk.section_ref,
                page_number=chunk.page_number,
            )
            db.add(dc)
            await db.flush()  # get dc.id

            ce = ChunkEmbedding(
                chunk_id=dc.id,
                embedding=vector,
                model_name=settings.embedding_model,
                model_version=settings.embedding_model_version,
            )
            db.add(ce)
            chunk_rows.append(dc)

        await db.commit()

    return IngestResponse(
        document_id=doc.id,
        title=title,
        tier_id=tier_id,
        chunks_created=len(chunk_rows),
        ocr_processed=ocr_result.ocr_applied,
        ocr_confidence=ocr_result.confidence if ocr_result.ocr_applied else None,
    )
