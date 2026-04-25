import pytest
from unittest.mock import AsyncMock, patch

from agents.shared.models import GovernanceSearchResult, SectionResult, CompareResult


class TestSearchCommunityRules:
    async def test_returns_governance_search_result(self, mocker):
        mock_retrieve = AsyncMock(return_value=[
            {
                "chunk": {
                    "content": "No more than two vehicles per unit.",
                    "document_title": "Declaration of Covenants",
                    "section_ref": "Article VIII, Section 3",
                    "document_id": 42,
                    "effective_date": None,
                },
                "tier": "Wickford HOA",
                "tier_type": "community",
                "score": 0.91,
            }
        ])
        mocker.patch("app.services.retriever.retrieve", mock_retrieve)

        from search_community_rules import search_community_rules_impl
        result = await search_community_rules_impl("parking rules", community_id=3)

        assert isinstance(result, GovernanceSearchResult)
        assert len(result.results) == 1
        assert result.results[0].relevance_score == 0.91
        assert result.community_id == 3

    async def test_community_id_is_always_int(self, mocker):
        """community_id must be an integer, never a string slug."""
        mocker.patch("app.services.retriever.retrieve", AsyncMock(return_value=[]))
        from search_community_rules import search_community_rules_impl
        result = await search_community_rules_impl("test", community_id=3)
        assert isinstance(result.community_id, int)


class TestGetSection:
    async def test_raises_for_superseded_document(self, mock_db_session):
        pytest.skip("requires DB fixture")

    async def test_raises_for_missing_section(self, mock_db_session):
        pytest.skip("requires DB fixture")


class TestCompareRules:
    async def test_sets_potential_conflicts_when_multiple_tiers(self, mocker):
        pytest.skip("requires vector search fixture")

    async def test_no_conflicts_when_single_tier(self, mocker):
        pytest.skip("requires vector search fixture")
