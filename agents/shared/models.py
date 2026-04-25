"""
Single source of truth for all MCP tool input/output schemas.
All agents and the orchestrator import from here — never define tool schemas locally.
Contract test (tests/test_shared_models.py) asserts all models round-trip through JSON.
"""
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# governance-mcp — Tool 1: search_community_rules
# ---------------------------------------------------------------------------

class SearchCommunityRulesInput(BaseModel):
    query: str
    community_id: int   # knowledge_tiers.id — always an integer
    top_k: int = 8


class SearchResultItem(BaseModel):
    chunk_text: str
    document_title: str
    section_ref: str
    tier: str           # 'community' | 'county' | 'state'
    relevance_score: float
    document_id: int
    effective_date: str | None = None


class GovernanceSearchResult(BaseModel):
    results: list[SearchResultItem]
    query: str
    community_id: int
    tiers_searched: list[str]


# ---------------------------------------------------------------------------
# governance-mcp — Tool 2: get_section
# ---------------------------------------------------------------------------

class GetSectionInput(BaseModel):
    document_id: int    # documents.id — always an integer
    section_ref: str    # e.g. "Article VIII, Section 3"


class SectionResult(BaseModel):
    document_title: str
    section_ref: str
    full_text: str
    preceding_section: str | None = None
    following_section: str | None = None
    document_id: int


# ---------------------------------------------------------------------------
# governance-mcp — Tool 3: compare_rules
# ---------------------------------------------------------------------------

class CompareRulesInput(BaseModel):
    query: str
    community_id: int   # knowledge_tiers.id — always an integer


class RuleItem(BaseModel):
    document_title: str
    section_ref: str
    text: str
    document_id: int


class RulesByTier(BaseModel):
    community: list[RuleItem] = []
    county: list[RuleItem] = []
    state: list[RuleItem] = []


class CompareResult(BaseModel):
    topic: str
    rules_by_tier: RulesByTier
    potential_conflicts: bool
    preemption_note: str | None = None


# ---------------------------------------------------------------------------
# customer-service-mcp — Tool 4: format_homeowner_response
# ---------------------------------------------------------------------------

class FormatHomeownerResponseInput(BaseModel):
    query: str
    compliance_facts: str   # JSON-serialized GovernanceSearchResult
    community_id: int       # knowledge_tiers.id — for community name/context only


class HomeownerResponse(BaseModel):
    response_text: str
    sources_cited: list[str]
    alternatives_suggested: bool
    escalation_recommended: bool


# ---------------------------------------------------------------------------
# customer-service-mcp — Tool 5: flag_for_escalation
# ---------------------------------------------------------------------------

class FlagForEscalationInput(BaseModel):
    query: str
    compliance_facts: str   # JSON-serialized GovernanceSearchResult
    reason: str             # 'ambiguous_rule' | 'conflict' | 'variance_request' | 'dispute'


class EscalationResult(BaseModel):
    escalation_summary: str
    reason: str
    relevant_rules: list[str]
    recommended_action: str
    urgency: str            # 'normal' | 'urgent'
