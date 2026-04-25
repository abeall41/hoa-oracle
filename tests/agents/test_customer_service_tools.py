import json
import pytest
from unittest.mock import AsyncMock

from agents.shared.models import GovernanceSearchResult, HomeownerResponse, EscalationResult

import app.services.llm  # noqa: F401 — must be imported before mocker.patch resolves it


def _make_facts(results=None) -> str:
    return GovernanceSearchResult(
        results=results or [],
        query="test",
        community_id=3,
        tiers_searched=["community"],
    ).model_dump_json()


class TestFormatHomeownerResponse:
    async def test_empty_facts_returns_contact_board_message(self, mocker):
        """When compliance_facts has no results, suggest contacting the board."""
        mocker.patch("app.services.llm.LLMClient")

        from format_homeowner_response import format_homeowner_response_impl
        result = await format_homeowner_response_impl(
            query="Can I add a deck?",
            compliance_facts=_make_facts([]),
            community_id=3,
        )

        assert isinstance(result, HomeownerResponse)
        assert result.escalation_recommended is True
        assert "board" in result.response_text.lower() or "contact" in result.response_text.lower()

    async def test_response_cites_sources(self, mocker):
        """Sources from compliance_facts should appear in sources_cited."""
        from agents.shared.models import SearchResultItem

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="Here is your answer about parking.")
        mocker.patch(
            "app.services.llm.LLMClient",
            return_value=mock_llm,
        )

        facts_with_results = _make_facts([
            SearchResultItem(
                chunk_text="No more than two vehicles.",
                document_title="Declaration",
                section_ref="Article VIII",
                tier="community",
                relevance_score=0.9,
                document_id=1,
            )
        ])

        from format_homeowner_response import format_homeowner_response_impl
        result = await format_homeowner_response_impl(
            query="parking?", compliance_facts=facts_with_results, community_id=3
        )

        assert "Declaration" in " ".join(result.sources_cited)


class TestFlagForEscalation:
    async def test_invalid_reason_raises(self):
        from flag_for_escalation import flag_for_escalation_impl
        with pytest.raises(ValueError, match="Invalid escalation reason"):
            await flag_for_escalation_impl(
                query="test", compliance_facts=_make_facts(), reason="invalid_reason"
            )

    async def test_dispute_sets_urgency_urgent(self, mocker):
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="Board review needed.")
        mocker.patch(
            "app.services.llm.LLMClient",
            return_value=mock_llm,
        )

        from flag_for_escalation import flag_for_escalation_impl
        result = await flag_for_escalation_impl(
            query="dispute query", compliance_facts=_make_facts(), reason="dispute"
        )

        assert result.urgency == "urgent"

    async def test_variance_request_sets_normal_urgency(self, mocker):
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="Variance review needed.")
        mocker.patch(
            "app.services.llm.LLMClient",
            return_value=mock_llm,
        )

        from flag_for_escalation import flag_for_escalation_impl
        result = await flag_for_escalation_impl(
            query="variance request", compliance_facts=_make_facts(), reason="variance_request"
        )

        assert result.urgency == "normal"
        assert result.escalation_recommended if hasattr(result, "escalation_recommended") else True
