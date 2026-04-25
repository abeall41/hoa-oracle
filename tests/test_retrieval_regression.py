"""
Retrieval regression test.
Fixed set of 10 query/expected-source pairs against the seeded Wickford dataset.
If a retrieval change causes a known query to stop returning the correct source
document, this test fails.

Requires: seeded Wickford documents + live DB.
Tag: integration (skipped in CI until dataset is seeded).
"""
import pytest

# Each entry: (query, expected_document_title_substring, expected_section_ref_substring)
REGRESSION_FIXTURES = [
    ("parking commercial vehicle driveway", "Declaration", "Article VIII"),
    ("pet leash requirement", "Rules and Regulations", ""),
    ("fence height limit", "Rules and Regulations", ""),
    ("landscaping approval process", "Rules and Regulations", ""),
    ("short term rental airbnb", "Declaration", ""),
    ("satellite dish antenna installation", "Rules and Regulations", ""),
    ("holiday decoration removal deadline", "Rules and Regulations", ""),
    ("homeowner association dues assessment", "Declaration", ""),
    ("board election procedures", "Bylaws", ""),
    ("Maryland HOA Act homeowner rights", "Maryland", ""),
]


@pytest.mark.integration
@pytest.mark.parametrize("query,expected_title,expected_section", REGRESSION_FIXTURES)
async def test_retrieval_returns_expected_source(
    query: str, expected_title: str, expected_section: str
) -> None:
    """Verify each known query returns a result from the expected document."""
    from app.services.retriever import retrieve

    results = await retrieve(query, community_tier_id=3, top_k=8)
    assert results, f"No results returned for query: {query!r}"

    titles = [r["chunk"].get("document_title", "") for r in results]
    assert any(expected_title.lower() in t.lower() for t in titles), (
        f"Expected document containing '{expected_title}' not found for query: {query!r}\n"
        f"Got titles: {titles}"
    )
