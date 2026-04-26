import asyncio
import json
import logging

from app.config import settings
from app.orchestrator.mcp_client import invoke_customer_service_tool, invoke_governance_tool
from app.services.llm import LLMClient

logger = logging.getLogger(__name__)


def _merge_search_results(all_results: list[dict], sub_queries: list[str]) -> dict:
    """
    Merge results from multiple search_community_rules calls.
    Deduplicates by (document_id, section_ref, first 80 chars of chunk text).
    When the same chunk appears in multiple sub-query results, keeps the best
    (lowest) relevance_score. Caps at 20 chunks sorted ascending by score.
    """
    seen: dict[tuple, dict] = {}
    tiers: set[str] = set()
    community_id = 0

    for result in all_results:
        community_id = result.get("community_id", community_id)
        for chunk in result.get("results", []):
            key = (
                chunk.get("document_id"),
                chunk.get("section_ref"),
                chunk.get("chunk_text", "")[:80],
            )
            existing = seen.get(key)
            if existing is None or chunk["relevance_score"] < existing["relevance_score"]:
                seen[key] = chunk
            tiers.add(chunk.get("tier", ""))

    merged = sorted(seen.values(), key=lambda c: c["relevance_score"])[:20]
    logger.info(
        "Merged %d unique chunks from %d sub-queries (tiers: %s)",
        len(merged), len(all_results), sorted(tiers),
    )
    return {
        "results": merged,
        "query": sub_queries[0] if sub_queries else "",
        "community_id": community_id,
        "tiers_searched": sorted(tiers),
    }


async def route_query(
    query: str,
    query_source: str,       # 'board' | 'homeowner'
    community_tier_id: int,  # knowledge_tiers.id — always an integer
    session_id: str,
) -> dict:
    if query_source not in ("homeowner", "board"):
        raise ValueError(f"Unknown query_source: {query_source!r}")

    # Decompose into focused sub-queries for better vector retrieval
    llm = LLMClient()
    sub_queries = await llm.decompose_query(query)

    # Run sub-query searches with a concurrency cap to bound subprocess memory usage.
    # Each subprocess loads the embedding model (~500MB RAM); limit simultaneous loads.
    semaphore = asyncio.Semaphore(settings.max_concurrent_searches)

    async def _bounded_search(sq: str) -> dict:
        async with semaphore:
            return await invoke_governance_tool("search_community_rules", {
                "query": sq,
                "community_id": community_tier_id,
            })

    raw_results = await asyncio.gather(
        *[_bounded_search(sq) for sq in sub_queries],
        return_exceptions=True,
    )

    # Filter out any failed sub-queries, log warnings
    valid_results: list[dict] = []
    for sq, result in zip(sub_queries, raw_results):
        if isinstance(result, Exception):
            logger.warning("Sub-query search failed for %r: %s", sq, result)
        else:
            valid_results.append(result)

    if not valid_results:
        # All sub-queries failed — return empty-facts response
        logger.error("All %d sub-query searches failed for query: %r", len(sub_queries), query)
        valid_results = [{"results": [], "query": query, "community_id": community_tier_id, "tiers_searched": []}]

    merged = _merge_search_results(valid_results, sub_queries)

    # Gate 1: retrieval confidence check.
    # merged["results"] is sorted ascending by score; index 0 is the best match.
    # If even the best chunk is above the threshold, retrieval found nothing reliable.
    if merged["results"]:
        best_score = merged["results"][0]["relevance_score"]
        if best_score > settings.retrieval_gate_threshold:
            logger.warning(
                "Gate 1 blocked: best retrieval score %.3f > threshold %.3f — "
                "skipping synthesis for query: %r",
                best_score, settings.retrieval_gate_threshold, query,
            )
            canned_text = (
                f"No reliable source material was found for this query "
                f"(best retrieval score: {best_score:.3f}, threshold: {settings.retrieval_gate_threshold}). "
                "Recommend rephrasing or consulting the governing documents directly."
                if query_source == "board" else
                "I wasn't able to find specific rules addressing this in the governing documents. "
                "The question may use phrasing that differs from the governing documents — "
                "try rephrasing, or contact your board or property manager for a definitive answer."
            )
            return {
                "response_text": canned_text,
                "sources_cited": [],
                "alternatives_suggested": False,
                "escalation_recommended": True,
            }

    return await invoke_customer_service_tool("format_homeowner_response", {
        "query": query,
        "compliance_facts": json.dumps(merged),
        "community_id": community_tier_id,
        "query_source": query_source,
        "sub_queries": sub_queries,
    })
