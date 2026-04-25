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
    # TODO: implement pgvector cosine search with SQLAlchemy
    # Query pattern:
    #   SELECT dc.*, ce.embedding <=> :query_vec AS score
    #   FROM document_chunks dc
    #   JOIN chunk_embeddings ce ON ce.chunk_id = dc.id
    #   JOIN documents d ON d.id = dc.document_id
    #   WHERE d.tier_id = :tier_id
    #     AND (:exclude_superseded = false OR d.superseded_by_id IS NULL)
    #   ORDER BY score ASC
    #   LIMIT :top_k
    raise NotImplementedError("vector_search not yet implemented")


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
