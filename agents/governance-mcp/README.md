# governance-mcp

Compliance fact-finding MCP server. Retrieves and surfaces rules from governing documents,
Maryland statutes, and county ordinances via hierarchical vector search.

**Domain:** Facts only. No tone, no recommendations, no synthesis.
**Transport:** stdio (out-of-process subprocess launched by the orchestrator)
**Entry point:** `server.py`

---

## Tools

### `search_community_rules`

Semantic vector search across the full tier hierarchy for a community.
Embeds the query, runs cosine similarity search via pgvector HNSW index across
community → county → state tiers, and returns ranked chunks.

Tier boost applied to cosine distance before ranking:
- community: 0.75× (preferred)
- county: 0.90×
- state: 1.00×

```
Args:
  query        str   Natural language question from the orchestrator.
  community_id int   knowledge_tiers.id for the community — always an integer.
  top_k        int   Results to return (default 8, max 20).

Returns: GovernanceSearchResult
  results          list[ChunkResult]  Ranked chunks with source citations.
  potential_conflicts bool            True when results span multiple governance tiers on the same topic.
```

### `get_section`

Retrieve the full text of a specific section given a document ID and section reference.
Use when `search_community_rules` returns a chunk that is clearly incomplete.
Do not call on every result — only fetch when surrounding context is needed.

```
Args:
  document_id  int   documents.id — always an integer.
  section_ref  str   Section string as returned by search (e.g. "Article VIII, Section 3").

Returns: SectionResult
  document_title str
  section_ref    str
  full_text      str   Full section text or not-found message.
```

### `compare_rules`

Surface all relevant rules on a topic across all tiers for side-by-side comparison.
Use when a question may have different answers at different governance levels
(e.g. noise limits governed by both bylaws and county ordinance).

```
Args:
  query        str   Topic to compare across tiers.
  community_id int   knowledge_tiers.id — always an integer.

Returns: CompareRulesResult
  tiers        dict[str, list[ChunkResult]]  Results keyed by tier name.
  potential_conflicts bool                   True when tiers have conflicting rules.
```

---

## Invariants

- Every response includes `source_documents` (document title + section reference). No exceptions.
- `community_id` is always `int` (FK from `knowledge_tiers.id`). Never a string slug.
- All queries filter `superseded_by_id IS NULL` — superseded documents never appear in results.
- Tools return structured data only. Claude synthesizes. No reasoning logic inside tools.
- Token budget: governance synthesis calls use `max_tokens=1500`.

---

## Preemption Hierarchy (for `compare_rules`)

State law → County ordinance → Community rules.

When `potential_conflicts: true`, the **calling model** (not this tool) must identify the
controlling rule and communicate the conflict clearly to the user.
Community rules that are *more restrictive* than county/state still apply — more restrictive
wins in either direction for community rules vs. a permissive higher-level law.

---

## Query Decomposition Context

The orchestrator decomposes verbose or multi-part user queries into focused search terms
before calling this tool. Each sub-query is a short (3–8 word) phrase optimized for
semantic search against legal documents.

This means `search_community_rules` may be called multiple times per user request —
once per sub-query — with results merged and deduplicated in the orchestrator before
being passed to `customer-service-mcp`. This tool has no awareness of the decomposition;
it processes each call independently.

Concurrency is bounded by `MAX_CONCURRENT_SEARCHES` (default 2) in the orchestrator to
prevent simultaneous subprocess memory pressure on low-RAM VMs.

---

## Shared Models

All input/output schemas live in `agents/shared/models.py`. Never define schemas locally.
The contract test (`tests/test_shared_models.py`) asserts all models round-trip through JSON.
