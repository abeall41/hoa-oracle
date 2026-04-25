import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from agents.shared.models import GovernanceSearchResult, SearchResultItem


async def search_community_rules_impl(
    query: str,
    community_id: int,
    top_k: int = 8,
) -> GovernanceSearchResult:
    """
    Perform hierarchical vector search for a community query.
    Searches community -> county -> state tiers.
    Filters superseded documents (superseded_by_id IS NULL).
    """
    from app.services.retriever import retrieve

    raw_results = await retrieve(query, community_tier_id=community_id, top_k=top_k)

    items = [
        SearchResultItem(
            chunk_text=r["chunk"]["content"],
            document_title=r["chunk"]["document_title"],
            section_ref=r["chunk"].get("section_ref", ""),
            tier=r["tier_type"],
            relevance_score=r["score"],
            document_id=r["chunk"]["document_id"],
            effective_date=r["chunk"].get("effective_date"),
        )
        for r in raw_results
    ]

    tiers_searched = list(dict.fromkeys(r["tier_type"] for r in raw_results))

    return GovernanceSearchResult(
        results=items,
        query=query,
        community_id=community_id,
        tiers_searched=tiers_searched or ["community", "county", "state"],
    )
