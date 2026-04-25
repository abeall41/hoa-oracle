import json

from app.orchestrator.mcp_client import invoke_customer_service_tool, invoke_governance_tool


async def route_query(
    query: str,
    query_source: str,       # 'board' | 'homeowner'
    community_tier_id: int,  # knowledge_tiers.id — always an integer
    session_id: str,
) -> dict:
    if query_source == "homeowner":
        facts = await invoke_governance_tool("search_community_rules", {
            "query": query,
            "community_id": community_tier_id,
        })
        return await invoke_customer_service_tool("format_homeowner_response", {
            "query": query,
            "compliance_facts": json.dumps(facts),
            "community_id": community_tier_id,
        })

    elif query_source == "board":
        return await invoke_governance_tool("search_community_rules", {
            "query": query,
            "community_id": community_tier_id,
        })

    else:
        raise ValueError(f"Unknown query_source: {query_source!r}")
