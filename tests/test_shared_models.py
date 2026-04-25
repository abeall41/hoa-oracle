"""
Contract test — runs in CI.
Asserts all tool input/output models in agents/shared/models.py round-trip
through JSON serialization. Catches schema drift between agents.
"""
from agents.shared.models import (
    CompareResult,
    CompareRulesInput,
    EscalationResult,
    FlagForEscalationInput,
    FormatHomeownerResponseInput,
    GetSectionInput,
    GovernanceSearchResult,
    HomeownerResponse,
    RuleItem,
    RulesByTier,
    SearchCommunityRulesInput,
    SearchResultItem,
    SectionResult,
)


def round_trip(model_instance):
    serialized = model_instance.model_dump_json()
    return type(model_instance).model_validate_json(serialized)


# --- Output models ---

def test_search_result_item_round_trip():
    item = SearchResultItem(
        chunk_text="No more than two vehicles per unit.",
        document_title="Crest of Wickford Declaration",
        section_ref="Article VIII, Section 3",
        tier="community",
        relevance_score=0.91,
        document_id=42,
    )
    assert round_trip(item) == item


def test_governance_search_result_round_trip():
    result = GovernanceSearchResult(
        results=[],
        query="parking limit",
        community_id=3,
        tiers_searched=["community", "county", "state"],
    )
    assert round_trip(result) == result


def test_governance_search_result_with_items_round_trip():
    result = GovernanceSearchResult(
        results=[
            SearchResultItem(
                chunk_text="Pets must be leashed.",
                document_title="Rules and Regulations",
                section_ref="Section 4.1",
                tier="community",
                relevance_score=0.85,
                document_id=7,
                effective_date="2021-01-01",
            )
        ],
        query="pet policy",
        community_id=3,
        tiers_searched=["community"],
    )
    assert round_trip(result) == result


def test_section_result_round_trip():
    result = SectionResult(
        document_title="Bylaws",
        section_ref="Article IV, Section 2",
        full_text="The board shall consist of five members...",
        preceding_section="Article IV, Section 1",
        following_section="Article IV, Section 3",
        document_id=1,
    )
    assert round_trip(result) == result


def test_section_result_optional_fields_round_trip():
    result = SectionResult(
        document_title="Declaration",
        section_ref="Article I",
        full_text="Definitions...",
        document_id=2,
    )
    assert round_trip(result) == result


def test_compare_result_round_trip():
    result = CompareResult(
        topic="noise restrictions",
        rules_by_tier=RulesByTier(
            community=[
                RuleItem(
                    document_title="Rules and Regulations",
                    section_ref="Section 7",
                    text="No loud noise after 10pm.",
                    document_id=3,
                )
            ],
            county=[],
            state=[],
        ),
        potential_conflicts=False,
    )
    assert round_trip(result) == result


def test_compare_result_with_conflicts_round_trip():
    result = CompareResult(
        topic="fence height",
        rules_by_tier=RulesByTier(),
        potential_conflicts=True,
        preemption_note="County ordinance controls where conflict exists.",
    )
    assert round_trip(result) == result


def test_homeowner_response_round_trip():
    response = HomeownerResponse(
        response_text="Great question about your landscaping plans!",
        sources_cited=["Rules and Regulations, Section 5.2"],
        alternatives_suggested=True,
        escalation_recommended=False,
    )
    assert round_trip(response) == response


def test_escalation_result_round_trip():
    result = EscalationResult(
        escalation_summary="Homeowner requesting variance for 6-foot fence.",
        reason="variance_request",
        relevant_rules=["Section 6.3", "Section 6.4"],
        recommended_action="Board variance review required",
        urgency="normal",
    )
    assert round_trip(result) == result


# --- Input models ---

def test_search_community_rules_input_round_trip():
    inp = SearchCommunityRulesInput(query="parking rules", community_id=3)
    assert round_trip(inp) == inp


def test_search_community_rules_input_custom_top_k():
    inp = SearchCommunityRulesInput(query="parking", community_id=3, top_k=15)
    assert round_trip(inp) == inp
    assert inp.top_k == 15


def test_get_section_input_round_trip():
    inp = GetSectionInput(document_id=42, section_ref="Article VIII, Section 3")
    assert round_trip(inp) == inp


def test_compare_rules_input_round_trip():
    inp = CompareRulesInput(query="noise after 10pm", community_id=3)
    assert round_trip(inp) == inp


def test_format_homeowner_response_input_round_trip():
    inp = FormatHomeownerResponseInput(
        query="Can I park a commercial vehicle in my driveway?",
        compliance_facts='{"results": [], "query": "parking", "community_id": 3, "tiers_searched": []}',
        community_id=3,
    )
    assert round_trip(inp) == inp


def test_flag_for_escalation_input_round_trip():
    inp = FlagForEscalationInput(
        query="I want to build a fence taller than allowed.",
        compliance_facts='{"results": [], "query": "fence", "community_id": 3, "tiers_searched": []}',
        reason="variance_request",
    )
    assert round_trip(inp) == inp
