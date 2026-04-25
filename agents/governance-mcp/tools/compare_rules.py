import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from agents.shared.models import CompareResult, RuleItem, RulesByTier


async def compare_rules_impl(query: str, community_id: int) -> CompareResult:
    """
    Retrieve rules touching the same topic across all tiers for comparison.
    Runs separate vector searches per tier and surfaces potential conflicts.
    Only returns chunks from non-superseded documents.
    """
    from app.services.retriever import get_tier_ancestry, vector_search
    from app.services.embedder import embed

    query_embedding = await embed(query)
    tiers = await get_tier_ancestry(community_id)

    rules_by_tier = RulesByTier()
    tier_map: dict[str, list[RuleItem]] = {"community": [], "county": [], "state": []}

    for tier in tiers:
        chunks = await vector_search(
            query_embedding,
            tier_id=tier.id,
            top_k=5,
            exclude_superseded=True,
        )
        for chunk in chunks:
            item = RuleItem(
                document_title=chunk["document_title"],
                section_ref=chunk.get("section_ref", ""),
                text=chunk["content"],
                document_id=chunk["document_id"],
            )
            if tier.tier in tier_map:
                tier_map[tier.tier].append(item)

    rules_by_tier.community = tier_map["community"]
    rules_by_tier.county = tier_map["county"]
    rules_by_tier.state = tier_map["state"]

    # Flag potential conflicts when multiple tiers have rules on the same topic
    tiers_with_rules = sum(
        1 for items in [rules_by_tier.community, rules_by_tier.county, rules_by_tier.state]
        if items
    )
    potential_conflicts = tiers_with_rules > 1

    preemption_note = None
    if potential_conflicts:
        preemption_note = (
            "Where rules conflict across tiers, the preemption hierarchy applies: "
            "state law overrides county ordinance, county ordinance overrides community rules, "
            "unless the community rule is more restrictive than the county or state rule."
        )

    return CompareResult(
        topic=query,
        rules_by_tier=rules_by_tier,
        potential_conflicts=potential_conflicts,
        preemption_note=preemption_note,
    )
