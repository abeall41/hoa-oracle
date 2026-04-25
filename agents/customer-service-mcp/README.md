# customer-service-mcp

Homeowner-facing MCP server. Receives compliance facts from the orchestrator and shapes
them into warm, accurate, contextually appropriate responses.

**Domain:** Response formatting and escalation only. Never retrieves documents or queries the DB.
**Transport:** stdio (out-of-process subprocess launched by the orchestrator)
**Entry point:** `server.py`

---

## Tools

### `format_homeowner_response`
Takes a `GovernanceSearchResult` (JSON) from governance-mcp and formats a homeowner response.
Handles preemption hierarchy when `potential_conflicts: true`.

### `flag_for_escalation`
Generates a structured escalation summary for board or manager review.
Use when facts are contradictory, a variance is needed, or a dispute is involved.

---

## Invariants

- Never queries documents or the database. Receives facts as input parameters only.
- Never fabricates rules. If facts are insufficient, says so and recommends contacting the board.
- Tone: warm, respectful, never condescending.
- Always acknowledge the homeowner's intent before stating a constraint.
- Suggest compliant alternatives where possible when a rule says "no."
- When `potential_conflicts: true`: identify the controlling rule via preemption hierarchy
  (state > county > community) and communicate clearly.

## Preemption Hierarchy

State law overrides county ordinance. County ordinance overrides community rules.
Exception: community rules that are *more* restrictive than the county/state rule still apply.
