# governance-mcp

Compliance fact-finding MCP server. Retrieves and surfaces rules from governing documents,
Maryland statutes, and county ordinances via hierarchical vector search.

**Domain:** Facts only. No tone, no recommendations, no synthesis.
**Transport:** stdio (out-of-process subprocess launched by the orchestrator)
**Entry point:** `server.py`

---

## Tools

### `search_community_rules`
Semantic search across the tier hierarchy (community → county → state).
Returns ranked chunks with source citations. Only non-superseded documents.

### `get_section`
Retrieve full text of a specific section by document ID and section reference.
Use when a search result chunk needs more context.

### `compare_rules`
Surface all rules on a topic across all tiers for side-by-side comparison.
Sets `potential_conflicts: true` when multiple tiers have rules on the same topic.

---

## Invariants

- Every response includes `source_documents` (document title + section reference). No exceptions.
- `community_id` is always `int` (FK from `knowledge_tiers.id`). Never a string slug.
- All queries filter `superseded_by_id IS NULL` — superseded documents never appear in results.
- Tools return structured data only. Claude synthesizes. No reasoning logic inside tools.

## Preemption Hierarchy (for `compare_rules`)

State law → County ordinance → Community rules.
When `potential_conflicts: true`, the calling model must identify the controlling rule
and communicate the conflict clearly to the user.
