"""
Builds context packages passed between agents.
Phase 1 context is simple — governance facts are passed directly as JSON.
This module is the extension point for richer cross-agent context in Phase 3+.
"""
from agents.shared.models import GovernanceSearchResult


def build_governance_context(facts: GovernanceSearchResult) -> str:
    """Serialize governance facts for passing to customer-service-mcp."""
    return facts.model_dump_json()
