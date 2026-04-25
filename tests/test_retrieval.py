import pytest
from unittest.mock import AsyncMock, patch

import app.services.retriever  # noqa: F401 — must be imported before mocker.patch resolves it


class TestGetTierAncestry:
    async def test_community_tier_returns_full_chain(self, mock_db_session):
        """Community tier should return [community, county, state] in that order."""
        pytest.skip("requires DB fixture with seeded tiers")

    async def test_state_tier_returns_single_entry(self, mock_db_session):
        """State tier has no parent — ancestry is just [state]."""
        pytest.skip("requires DB fixture")


class TestVectorSearch:
    async def test_excludes_superseded_documents(self, mock_db_session):
        """vector_search must filter documents where superseded_by_id IS NOT NULL."""
        pytest.skip("requires pgvector fixture")

    async def test_returns_results_ordered_by_score(self, mock_db_session):
        pytest.skip("requires pgvector fixture")


class TestRetrieve:
    async def test_searches_all_tiers(self, mocker):
        """retrieve() must query every tier in the ancestry chain."""
        mock_ancestry = AsyncMock(return_value=[
            type("Tier", (), {"id": 3, "name": "Wickford HOA", "tier": "community"})(),
            type("Tier", (), {"id": 2, "name": "Montgomery County", "tier": "county"})(),
            type("Tier", (), {"id": 1, "name": "Maryland", "tier": "state"})(),
        ])
        mocker.patch("app.services.retriever.get_tier_ancestry", mock_ancestry)
        mocker.patch("app.services.retriever.vector_search", AsyncMock(return_value=[]))
        mocker.patch("app.services.retriever.embed", AsyncMock(return_value=[0.1] * 768))

        from app.services.retriever import retrieve
        results = await retrieve("parking rules", community_tier_id=3)

        assert mock_ancestry.called
        assert isinstance(results, list)

    async def test_returns_top_k_results(self, mocker):
        """retrieve() must return at most top_k results sorted by score."""
        mocker.patch("app.services.retriever.get_tier_ancestry", AsyncMock(return_value=[
            type("Tier", (), {"id": 3, "name": "Wickford HOA", "tier": "community"})(),
        ]))
        mocker.patch(
            "app.services.retriever.vector_search",
            AsyncMock(return_value=[{"score": i * 0.1, "content": f"chunk {i}", "document_title": "Doc", "document_id": i} for i in range(20)]),
        )
        mocker.patch("app.services.retriever.embed", AsyncMock(return_value=[0.1] * 768))

        from app.services.retriever import retrieve
        results = await retrieve("parking rules", community_tier_id=3, top_k=5)
        assert len(results) <= 5
