import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.chunk import ChunkEmbedding, DocumentChunk
from app.models.document import Document
from app.models.tier import KnowledgeTier
from app.services.embedder import embed

logger = logging.getLogger(__name__)


async def get_tier_ancestry(community_tier_id: int) -> list[KnowledgeTier]:
    """
    Return the tier chain from community up through county to state.
    Result is ordered community-first so retrieval searches local rules before state law.
    """
    async with AsyncSessionLocal() as db:
        tiers = []
        current_id: int | None = community_tier_id
        while current_id is not None:
            result = await db.execute(
                select(KnowledgeTier).where(KnowledgeTier.id == current_id)
            )
            tier = result.scalar_one_or_none()
            if tier is None:
                break
            tiers.append(tier)
            current_id = tier.parent_id
        return tiers


async def vector_search(
    query_embedding: list[float],
    tier_id: int,
    top_k: int,
    exclude_superseded: bool = True,
    db: AsyncSession | None = None,
) -> list[dict]:
    """
    Cosine similarity search against chunk_embeddings for a given tier.
    Always filters chunks from superseded documents when exclude_superseded=True.
    Uses HNSW index on chunk_embeddings.embedding.
    """
    # Format the embedding as a PostgreSQL vector literal. The values are
    # internally generated floats from the embedding model (not user input),
    # so inline formatting is safe and avoids asyncpg codec registration for
    # the vector type.
    vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
    superseded_clause = "AND d.superseded_by_id IS NULL" if exclude_superseded else ""

    sql = text(f"""
        SELECT
            dc.id,
            dc.content,
            dc.section_ref,
            dc.page_number,
            d.title        AS document_title,
            d.id           AS document_id,
            d.effective_date::text AS effective_date,
            (ce.embedding <=> '{vec_literal}'::vector) AS score
        FROM document_chunks dc
        JOIN chunk_embeddings ce ON ce.chunk_id = dc.id
        JOIN documents d ON d.id = dc.document_id
        WHERE d.tier_id = :tier_id
          {superseded_clause}
        ORDER BY score ASC
        LIMIT :top_k
    """)

    own_session = db is None
    session = AsyncSessionLocal() if own_session else db
    try:
        result = await session.execute(sql, {"tier_id": tier_id, "top_k": top_k})
        rows = result.mappings().all()
        return [dict(row) for row in rows]
    finally:
        if own_session:
            await session.close()


async def retrieve(query: str, community_tier_id: int, top_k: int = 8) -> list[dict]:
    """
    Retrieve relevant chunks across the tier hierarchy.
    Searches community → county → state, merges and deduplicates results,
    returns top_k overall ranked by relevance score.
    Filters out chunks from superseded documents automatically.
    """
    query_embedding = await embed(query)
    tiers = await get_tier_ancestry(community_tier_id)

    results = []
    for tier in tiers:
        chunks = await vector_search(
            query_embedding,
            tier_id=tier.id,
            top_k=top_k,
            exclude_superseded=True,
        )
        for chunk in chunks:
            results.append({
                "chunk": chunk,
                "tier": tier.name,
                "tier_type": tier.tier,
                "score": chunk["score"],
            })

    return sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
