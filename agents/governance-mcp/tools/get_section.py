import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from agents.shared.models import SectionResult


async def get_section_impl(document_id: int, section_ref: str) -> SectionResult:
    """
    Retrieve the full text of a specific section by document ID and section reference.
    Raises ValueError if the document is superseded.
    """
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.document import Document
    from app.models.chunk import DocumentChunk

    async with AsyncSessionLocal() as db:
        # Verify document exists and is not superseded
        doc_result = await db.execute(
            select(Document.id, Document.title, Document.superseded_by_id)
            .where(Document.id == document_id)
        )
        doc = doc_result.one_or_none()
        if doc is None:
            raise ValueError(f"Document {document_id} not found")
        if doc.superseded_by_id is not None:
            raise ValueError(
                f"Document {document_id} has been superseded by document {doc.superseded_by_id}"
            )

        # Find chunks matching the section_ref
        chunks_result = await db.execute(
            select(DocumentChunk.content, DocumentChunk.chunk_index, DocumentChunk.section_ref)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.section_ref == section_ref,
            )
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = chunks_result.all()

        if not chunks:
            raise ValueError(f"Section '{section_ref}' not found in document {document_id}")

        full_text = "\n\n".join(c.content for c in chunks)

        return SectionResult(
            document_title=doc.title,
            section_ref=section_ref,
            full_text=full_text,
            document_id=document_id,
        )
