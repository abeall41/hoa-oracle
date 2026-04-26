# customer-service-mcp

Homeowner-facing MCP server. Receives compliance facts from the orchestrator and shapes
them into warm, accurate, contextually appropriate responses.

**Domain:** Response formatting and escalation only. Never retrieves documents or queries the DB.
**Transport:** stdio (out-of-process subprocess launched by the orchestrator)
**Entry point:** `server.py`

---

## Tools

### `format_homeowner_response`

Takes a serialized `GovernanceSearchResult` (JSON string from `governance-mcp`) and
formats a response for delivery to the user. Implements Gates 2 and 3 of the accuracy
pipeline — see Accuracy Pipeline section below.

```
Args:
  query            str         Original user question (may be multi-part).
  compliance_facts str         JSON-serialized GovernanceSearchResult from governance-mcp.
  community_id     int         knowledge_tiers.id — always an integer.
  query_source     str         "homeowner" (default) or "board".
  sub_queries      list[str]   Focused search queries derived from the original query
                               by the orchestrator's decomposition step. When present,
                               the LLM is instructed to address all parts of the original
                               question and explicitly flag any part with no supporting facts.

Returns: HomeownerResponse
  response_text          str        Formatted LLM response for the user.
  sources_cited          list[str]  Deduplicated "Document Title, Section Ref" strings.
  alternatives_suggested bool       True when compliant alternatives were offered.
  escalation_recommended bool       True when board contact is advised.
```

**Tone by `query_source`:**

| Mode | Tone | Detail level | Token budget |
|------|------|-------------|--------------|
| `homeowner` | Warm, advisory, empathetic | Summarized, alternatives offered | 800 |
| `board` | Factual, citation-heavy, no personality | Exact article/section citations | 2000 |

**Empty facts behavior:** When `compliance_facts` contains no results:
- `homeowner`: apologetic message, recommends contacting the board.
- `board`: direct "no relevant rules found" statement.

### `flag_for_escalation`

Generates a structured escalation summary for board or manager review.
Use when facts are contradictory, a variance is needed, a dispute is involved,
or governance facts are insufficient to resolve the question.

```
Args:
  query        str   Original user question.
  reason       str   Why escalation is needed.
  community_id int   knowledge_tiers.id — always an integer.

Returns: EscalationFlag
  summary      str   Structured escalation note.
  priority     str   "low" | "medium" | "high"
```

---

## Accuracy Pipeline

This tool implements Gates 2 and 3. Gate 1 fires in the orchestrator before this tool
is ever called — if retrieval confidence is too low, synthesis is skipped entirely.

**Gate 1 — Retrieval confidence threshold** *(orchestrator, `router.py`)*
If the best retrieved chunk score exceeds `RETRIEVAL_GATE_THRESHOLD` (default 0.46),
the orchestrator returns a canned "could not find reliable information" response and
this tool is never invoked.

**Gate 2 — Constrained synthesis prompts** *(this tool)*
Both system prompts append an explicit citation constraint:
- "Quote the relevant passage verbatim from the Compliance facts before interpreting it."
- "Cite only section references that appear in the Compliance facts provided."
- "Do not reference any section, article, or rule not present in the sources."

This is preventive — reduces hallucination at generation time with zero latency cost.

**Gate 3 — Citation grounding check + conditional retry** *(this tool)*
After synthesis, `app.services.faithfulness.check_citation_grounding` extracts all
Section/Article references from the response and verifies each appears in the retrieved
chunk corpus. Two or more ungrounded citations triggers a single retry using a multi-turn
correction message. If the retry still fails the check, `UNVERIFIED_DISCLAIMER` is
appended to the response before returning.

```
Flow:
  synthesize response
    → check_citation_grounding(response, compliance_facts)
    → if 2+ ungrounded citations:
        retry with correction message (multi-turn)
        → if still suspect: append disclaimer
    → return response
```

---

## Invariants

- Never queries documents or the database. Receives facts as input parameters only.
- Never fabricates rules. If facts are insufficient, says so explicitly.
- `homeowner` tone: warm, respectful, never condescending; acknowledge intent before constraint.
- `board` tone: factual, no softening; exact citations from document title + article + section.
- Suggest compliant alternatives when a rule says "no" (`homeowner` mode only).
- When `potential_conflicts: true` in the facts: identify the controlling rule via preemption
  hierarchy and communicate it clearly to the user in both modes.

---

## Preemption Hierarchy

State law overrides county ordinance. County ordinance overrides community rules.

Exception: community rules that are *more restrictive* than a higher-level permissive rule
still apply — residents must comply with the stricter requirement.

When communicating conflicts:
- `homeowner`: explain which rule applies and why in plain language.
- `board`: cite the controlling authority with its statutory or document reference.

---

## Shared Models

All input/output schemas live in `agents/shared/models.py`. Never define schemas locally.
The contract test (`tests/test_shared_models.py`) asserts all models round-trip through JSON.

---

## LLM Configuration

- Uses `LLMClient` from `app/services/llm.py` — the only place LLM calls are made.
- Provider controlled by `LLM_PROVIDER` env var (`ollama` for dev, `claude` for prod).
- Prompts developed and validated against Claude. Ollama output quality is not the baseline.
- OCR cleanup (in `ocr.py`) always uses Ollama regardless of `LLM_PROVIDER` — this tool does not.
- Query decomposition (in `router.py`) always uses Ollama regardless of `LLM_PROVIDER`.
