import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from mcp.server.fastmcp import FastMCP

import format_homeowner_response as fhr_mod
import flag_for_escalation as ffe_mod

mcp = FastMCP("customer-service-mcp")


@mcp.tool()
async def format_homeowner_response(
    query: str, compliance_facts: str, community_id: int
) -> dict:
    """
    Takes raw compliance facts from governance-mcp and shapes them into a warm,
    clear, homeowner-appropriate response.

    Tone: respectful, helpful, never condescending. Acknowledge the homeowner's
    intent before delivering any constraint. Where a rule says 'no', suggest
    compliant alternatives where possible.

    When compliance_facts contains potential_conflicts=true, apply the preemption
    hierarchy: state law overrides county ordinance, county ordinance overrides
    community rules. Identify the controlling rule and communicate the conflict
    clearly without confusing the homeowner.

    Never fabricate rules. If compliance_facts are empty or insufficient, say so
    clearly and suggest contacting the board.

    Args:
        query: Original homeowner question.
        compliance_facts: JSON-serialized GovernanceSearchResult from governance-mcp.
        community_id: knowledge_tiers.id — for community name/context only.
    """
    result = await fhr_mod.format_homeowner_response_impl(query, compliance_facts, community_id)
    return result.model_dump()


@mcp.tool()
async def flag_for_escalation(
    query: str, compliance_facts: str, reason: str
) -> dict:
    """
    Marks a query as needing board or manager review. Use when compliance_facts
    are contradictory, when the situation requires a variance, or when the query
    involves a dispute.

    Returns a structured escalation summary suitable for forwarding to a board
    member or property manager.

    Args:
        query: Original homeowner question.
        compliance_facts: JSON-serialized GovernanceSearchResult.
        reason: One of 'ambiguous_rule' | 'conflict' | 'variance_request' | 'dispute'.
    """
    result = await ffe_mod.flag_for_escalation_impl(query, compliance_facts, reason)
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
