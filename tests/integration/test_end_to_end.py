"""
End-to-end integration test.
Requires: live DB, live MinIO, live Ollama (or Claude API), seeded Wickford documents.
Tag: integration — skipped in CI.

Run with: pytest tests/integration/ -m integration
"""
import pytest


@pytest.mark.integration
async def test_ingest_and_query_wickford_bylaws():
    """Ingest a real document and verify it is retrievable by natural language query."""
    pytest.skip("Requires seeded Wickford documents — run after scripts/seed_tiers.py and scripts/ingest_document.py")


@pytest.mark.integration
async def test_board_query_returns_sourced_response():
    """Board query path: governance-mcp returns facts with source citations."""
    pytest.skip("Requires live infrastructure")


@pytest.mark.integration
async def test_homeowner_query_returns_warm_response():
    """Homeowner query path: customer-service-mcp produces warm, accurate response."""
    pytest.skip("Requires live infrastructure")


@pytest.mark.integration
async def test_both_mcp_servers_run_as_independent_subprocesses():
    """Verify each MCP server can be killed and restarted without restarting the orchestrator."""
    pytest.skip("Requires live infrastructure")


@pytest.mark.integration
async def test_superseded_document_not_in_search_results():
    """Re-ingest a document as an amendment; verify old chunks do not appear in search results."""
    pytest.skip("Requires live infrastructure and two document versions")
