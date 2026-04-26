"""
CLI document ingestion.

Usage: python scripts/ingest_document.py <file_path> --tier-slug wickford --title "Bylaws" --doc-type bylaws
"""
import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def ingest(file_path: str, tier_slug: str, title: str, doc_type: str) -> None:
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.tier import KnowledgeTier
    from app.models.document import Document
    from app.services.ocr import extract_text_from_pdf, extract_text_from_docx
    from app.services.chunker import chunk_text
    from app.services.embedder import embed_batch
    from app.models.chunk import DocumentChunk, ChunkEmbedding
    from storage.minio_client import upload_document
    from app.config import settings

    # Resolve tier slug to integer ID
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeTier).where(KnowledgeTier.slug == tier_slug)
        )
        tier = result.scalar_one_or_none()
        if tier is None:
            print(f"Error: tier slug '{tier_slug}' not found. Run scripts/seed_tiers.py first.")
            sys.exit(1)

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    filename = os.path.basename(file_path)
    mime_type = "application/pdf" if file_path.endswith(".pdf") else "application/octet-stream"

    # Extract text
    if file_path.endswith(".pdf"):
        ocr_result = await extract_text_from_pdf(file_bytes)
    elif file_path.endswith(".docx"):
        ocr_result = await extract_text_from_docx(file_bytes)
    else:
        print(f"Unsupported file type: {file_path}")
        sys.exit(1)

    # Upload to MinIO
    object_path = await upload_document(tier.tier, tier_slug, filename, file_bytes, mime_type)

    async with AsyncSessionLocal() as db:
        # Check for existing document (versioning)
        existing = await db.execute(
            select(Document).where(
                Document.tier_id == tier.id,
                Document.title == title,
                Document.doc_type == doc_type,
                Document.superseded_by_id.is_(None),
            )
        )
        existing_doc = existing.scalar_one_or_none()
        if existing_doc:
            print(f"Document '{title}' already exists (id={existing_doc.id}).")
            action = input("Enter 'amendment' to create new version, 'correction' to overwrite: ").strip()
            if action == "amendment":
                doc = Document(
                    tier_id=tier.id, title=title, doc_type=doc_type,
                    file_path=object_path, original_filename=filename, mime_type=mime_type,
                    ocr_processed=ocr_result.ocr_applied, ocr_confidence=ocr_result.confidence,
                    raw_text=ocr_result.text,
                )
                db.add(doc)
                await db.flush()
                existing_doc.superseded_by_id = doc.id
                print(f"Created new version (id={doc.id}), superseded old (id={existing_doc.id})")
            elif action == "correction":
                existing_doc.raw_text = ocr_result.text
                existing_doc.ocr_processed = ocr_result.ocr_applied
                existing_doc.ocr_confidence = ocr_result.confidence
                doc = existing_doc
                print(f"Updated existing document in place (id={doc.id})")
            else:
                print("Aborted.")
                return
        else:
            doc = Document(
                tier_id=tier.id, title=title, doc_type=doc_type,
                file_path=object_path, original_filename=filename, mime_type=mime_type,
                ocr_processed=ocr_result.ocr_applied, ocr_confidence=ocr_result.confidence,
                raw_text=ocr_result.text,
            )
            db.add(doc)
            await db.flush()
            print(f"Created document (id={doc.id})")

        # Chunk and embed in small batches to avoid OOM on low-RAM VMs
        chunks = chunk_text(ocr_result.text)
        texts = [c.content for c in chunks]
        EMBED_BATCH_SIZE = 16
        vectors = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch_vectors = await embed_batch(texts[i:i + EMBED_BATCH_SIZE])
            vectors.extend(batch_vectors)
            print(f"  Embedded chunks {i + 1}–{min(i + EMBED_BATCH_SIZE, len(texts))} of {len(texts)}")

        for chunk_data, vector in zip(chunks, vectors):
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=chunk_data.chunk_index,
                content=chunk_data.content,
                section_ref=chunk_data.section_ref,
            )
            db.add(chunk)
            await db.flush()
            embedding = ChunkEmbedding(
                chunk_id=chunk.id,
                embedding=vector,
                model_name=settings.embedding_model,
                model_version=settings.embedding_model_version,
            )
            db.add(embedding)

        await db.commit()
        print(f"Ingested {len(chunks)} chunks for document id={doc.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a document into hoa-oracle")
    parser.add_argument("file_path", help="Path to the document file")
    parser.add_argument("--tier-slug", required=True, help="Tier slug (e.g. wickford, montgomery-county, maryland)")
    parser.add_argument("--title", required=True, help="Document title")
    parser.add_argument("--doc-type", required=True, help="Document type (e.g. bylaws, declaration, statute)")
    args = parser.parse_args()
    asyncio.run(ingest(args.file_path, args.tier_slug, args.title, args.doc_type))
