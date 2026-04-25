import os
import sys

# Add project root to sys.path for shared models and app imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from mcp.server.fastmcp import FastMCP

import search_community_rules as scr_mod
import get_section as gs_mod
import compare_rules as cr_mod

mcp = FastMCP("governance-mcp")


@mcp.tool()
async def search_community_rules(query: str, community_id: int, top_k: int = 8) -> dict:
    """
    Semantic vector search across the full tier hierarchy for a community.
    Embeds the query, searches pgvector using HNSW cosine similarity across
    community -> county -> state tiers, and returns ranked results.

    Only returns chunks from non-superseded documents (superseded_by_id IS NULL).
    Use as the first tool call for any compliance question.
    Returns ranked chunks — not a synthesized answer. Claude synthesizes.

    Args:
        query: Natural language query from the user or orchestrator.
        community_id: knowledge_tiers.id for the community — always an integer.
        top_k: Number of results to return (default 8, max 20).
    """
    result = await scr_mod.search_community_rules_impl(query, community_id, top_k)
    return result.model_dump()


@mcp.tool()
async def get_section(document_id: int, section_ref: str) -> dict:
    """
    Retrieve the full text of a specific section given a document ID and section reference.
    Use when search_community_rules returns a chunk that needs more surrounding context.
    Do not call on every result — only when the returned chunk is clearly incomplete.
    Returns a not-found error if document_id refers to a superseded document.

    Args:
        document_id: documents.id — always an integer.
        section_ref: Section reference string (e.g. 'Article VIII, Section 3').
    """
    result = await gs_mod.get_section_impl(document_id, section_ref)
    return result.model_dump()


@mcp.tool()
async def compare_rules(query: str, community_id: int) -> dict:
    """
    Surface all relevant rules touching the same topic across all tiers
    (community, county, state), formatted for comparison.
    Use when a question may have different answers at different governance levels
    (e.g. noise rules governed by both bylaws and county ordinance).

    Returns structured comparison data — Claude synthesizes.
    When potential_conflicts is true, Claude must apply the preemption hierarchy:
    state law overrides county ordinance, county ordinance overrides community rules.
    Only returns chunks from non-superseded documents.

    Args:
        query: The topic to compare across tiers.
        community_id: knowledge_tiers.id — always an integer.
    """
    result = await cr_mod.compare_rules_impl(query, community_id)
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
