# hoa-oracle — Phase 2 Technical Implementation Plan

---

## Objective

Extend the single-community compliance MVP into a multi-community platform with
authentication, community-scoped access control, an admin dashboard, email drafting
automation, and a production-grade LLM configuration. Phase 2 ends when a property
manager can log in, query rules for any of their assigned communities, draft a compliant
board notice, and review the system's query history — all without touching the CLI.

**Phase 2 is not a rewrite.** The Phase 1 pipeline (ingestion, retrieval, agents,
accuracy gates) is production-quality and carries forward unchanged. Phase 2 adds
the multi-tenant shell around it.

---

## What Phase 1 Already Delivered (No Duplication Needed)

The following items were originally scoped to Phase 2 but were completed in Phase 1:

- Web UI (query, document management, upload) — running at port 8000
- Both MCP agents fully finalized and production-ready
- Structured logging, query_log wiring, systemd service
- 3-gate accuracy pipeline (retrieval gate, constrained prompts, citation grounding + retry)
- Query decomposition with parallel sub-query execution

Phase 2 builds on top of this. Do not re-implement or refactor any of it.

---

## Phase 2 Goals

1. **Authentication** — JWT-based auth with three roles: `admin`, `board`, `homeowner`
2. **Multi-community** — Dynamic community selection; 2–3 communities fully onboarded
3. **Admin dashboard** — Query log viewer, community management, user management
4. **Email drafting** — New `draft_board_notice` MCP tool + UI panel
5. **Production LLM** — `LLM_PROVIDER=claude` as default; Ollama retained for decomposition and OCR cleanup only
6. **Infrastructure** — Caddy `hoa.lan`, Uptime Kuma monitors, DB backups

---

## New Architecture Components

### Authentication

JWT-based. Tokens include: `{ user_id, role, community_id | null, exp }`.

- `admin`: full access to all communities, all endpoints
- `board`: scoped to one `community_id`; uses `query_source="board"` by default; can use `homeowner` mode
- `homeowner`: scoped to one `community_id`; `query_source="homeowner"` only

API key auth for ingestion scripts: key hashed in DB, scoped to a community.
Tokens expire in 24h. No OAuth in Phase 2 — simple email/password with `bcrypt` hashing.

### Community Selection

Community is derived from the authenticated user's JWT claim (`community_id`), not from
form fields or URL parameters. Admin users pass `community_id` explicitly per request.
The hardcoded `community_id=3` in the Phase 1 UI is replaced by the JWT-bound community.

### Email Drafting

New tool `draft_board_notice` in `customer-service-mcp`. New routing path
`query_source="email_draft"` in the orchestrator: governance search → `draft_board_notice`.
The orchestrator calls `search_community_rules` first, then passes facts to the new tool.
No new MCP server — this is the 6th tool added to the existing `customer-service-mcp`.

---

## Database Schema Additions

All changes via Alembic migrations. Never `CREATE TABLE` directly.

```sql
-- User accounts
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,         -- bcrypt
    role            VARCHAR(20)  NOT NULL,          -- 'admin' | 'board' | 'homeowner'
    community_id    INT REFERENCES knowledge_tiers(id),  -- NULL for admin
    display_name    VARCHAR(255),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    last_login      TIMESTAMP
);

-- API keys for ingestion scripts and automation
CREATE TABLE api_keys (
    id              SERIAL PRIMARY KEY,
    key_hash        VARCHAR(255) UNIQUE NOT NULL,   -- SHA-256 of the raw key
    description     VARCHAR(255),
    community_id    INT REFERENCES knowledge_tiers(id),
    created_by      INT REFERENCES users(id),
    is_active       BOOLEAN DEFAULT TRUE,
    last_used       TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Link query_log entries to authenticated users (additive migration)
ALTER TABLE query_log ADD COLUMN user_id INT REFERENCES users(id);
ALTER TABLE query_log ADD COLUMN gate1_blocked BOOLEAN DEFAULT FALSE;
ALTER TABLE query_log ADD COLUMN gate3_retry_fired BOOLEAN DEFAULT FALSE;
ALTER TABLE query_log ADD COLUMN min_retrieval_score FLOAT;
```

`gate1_blocked`, `gate3_retry_fired`, and `min_retrieval_score` are the accuracy
monitoring fields that enable the admin dashboard to surface hallucination risk signals
without requiring log file access.

---

## New MCP Tool — `draft_board_notice`

Sixth tool overall. Lives in `customer-service-mcp`.

**Purpose:** Takes compliance facts and drafts a formal board communication — violation
notice, rule change announcement, meeting notice, or general correspondence. Produces a
ready-to-review draft with a citation checklist so the board can verify accuracy before
sending.

**Shared models (add to `agents/shared/models.py`):**

```python
class DraftBoardNoticeInput(BaseModel):
    query: str               # What the notice is about
    compliance_facts: str    # JSON-serialized GovernanceSearchResult
    notice_type: str         # 'violation_notice' | 'rule_change' | 'meeting_notice' | 'general_notice'
    community_name: str      # Used in the letter header and signature block
    community_id: int        # knowledge_tiers.id

class DraftedNotice(BaseModel):
    subject: str             # Email/letter subject line
    body: str                # Full draft text
    notice_type: str
    citations_included: list[str]   # "Document Title, Section Ref" strings cited in the draft
    review_checklist: list[str]     # Items the board must verify before sending
```

**Token budget:** `max_tokens=1200` — notices are structured and bounded.

**Routing:** `query_source="email_draft"` in `router.py`:
```
decompose_query → search_community_rules (parallel) → merge → draft_board_notice
```

**Tone rules:**
- Formal, professional, first-person plural ("The Board of Directors...")
- State the rule and cite the source before stating the required action
- Include the specific section reference in the body
- No warmth or empathy framing — this is an official communication
- Always include a contact block placeholder for the board to fill in
- `review_checklist` must flag: homeowner name/address placeholders, effective dates,
  signature block, and any cited section that needs board verification

---

## API Additions

All new routes in `app/api/`. Each gets its own module.

### `app/api/auth.py`
```
POST /auth/login              → { access_token, token_type, expires_in }
GET  /auth/me                 → { user_id, email, role, community_id }
POST /auth/logout             → 204 (token invalidation via short expiry; no server-side revocation in Phase 2)
```

### `app/api/admin.py`
All endpoints require `role=admin`.
```
GET  /admin/query-log         → paginated list (filters: community_id, date_range, success, gate1_blocked, gate3_fired)
GET  /admin/communities       → list all knowledge_tiers of type 'community'
POST /admin/communities       → create new community tier record
GET  /admin/users             → list users (paginated)
POST /admin/users             → create user
PATCH /admin/users/{id}       → update user (role, community_id, is_active)
POST /admin/api-keys          → generate new API key (returns raw key once, stores hash)
```

### Updated `app/api/query.py`
- Require auth (board or homeowner JWT, or API key)
- Derive `community_id` from JWT claim rather than form field
- Admin can override `community_id` in request body
- Record `user_id`, `gate1_blocked`, `gate3_retry_fired`, `min_retrieval_score` in query_log

### Updated `app/api/ingest.py`
- Accept API key auth in addition to admin JWT
- API key must be scoped to the same community as the document being ingested

---

## UI Additions

The Phase 1 HTML UI at `app/static/index.html` is extended. No framework change — same
FastAPI-served HTML/CSS/JS.

### Login page
Simple email/password form. POSTs to `/auth/login`. Stores JWT in `localStorage`.
All subsequent API calls include `Authorization: Bearer {token}` header.
Redirect to main app on success; redirect to login on 401.

### Community selector
For `admin` users: dropdown in the header populated from `/admin/communities`.
For `board`/`homeowner`: community name displayed as static label (from JWT claims).
All queries and document views are scoped to the selected/assigned community.

### Tab 4 — Draft Notice
New panel alongside Ask a Question / Documents / Upload.
Fields: notice topic (text), notice type (dropdown: violation / rule change / meeting / general).
On submit: POST to `/query/` with `query_source="email_draft"`.
Response renders subject and body in an editable textarea + review checklist below.
Copy-to-clipboard button. No email sending in Phase 2 — draft only.

### Admin panel (new page `/admin`)
Accessible only to `admin` role users. Separate page, not a tab.
- **Query log viewer:** table with columns: timestamp, community, user, query (truncated),
  latency, gate1_blocked, gate3_fired, min_score, success. Filterable. Click row to expand
  full response and sources.
- **Communities:** list with document count per community. Add new community button.
- **Users:** list with role/community assignment. Add/edit user.

---

## Build Sequence

### Block 1 — Phase 1 Closeout (prerequisite, complete before any Block 2 work)

**1.1** Write `tests/test_retrieval_regression.py`
- 10 fixed (query, expected_document_title, expected_section_ref) tuples from Crest of Wickford dataset
- Each assertion: the expected document appears in top-3 results for that query
- Tagged `@pytest.mark.regression` — runs in CI, must pass before Phase 2 merge

**1.2** Ingest county and state content
- Montgomery County noise and zoning ordinances at county tier
- Verify Maryland HOA Act §11B is indexed at state tier (separate from Condo Act)

**1.3** Gate 1 threshold calibration
- Review `query_log.min_retrieval_score` across 30+ real queries
- Identify queries Gate 1 blocked that were actually answerable (false positives)
- Identify queries Gate 1 passed that produced hallucinations (false negatives)
- Adjust `RETRIEVAL_GATE_THRESHOLD` in `.env`; document the chosen value and rationale in PHASE2.md

**1.4** Infrastructure
- Caddy `hoa.lan` site block pointing to hoa-api
- Uptime Kuma: hoa-api `/health`, hoa-db port 5432, MinIO health endpoint

### Block 2 — Authentication

**2.1** Alembic migration: `users` and `api_keys` tables + `query_log` additions

**2.2** `app/services/auth.py`
- `hash_password(plain: str) -> str` (bcrypt)
- `verify_password(plain: str, hashed: str) -> bool`
- `create_access_token(user_id, role, community_id, expires_delta) -> str` (PyJWT)
- `decode_token(token: str) -> TokenClaims`
- `get_current_user(token) -> User` (FastAPI dependency)
- `require_role(*roles)` — dependency factory for role-gating endpoints
- `get_api_key_community(key: str) -> int | None` — validates API key, returns community_id

**2.3** `app/api/auth.py` — login, me, logout endpoints

**2.4** Auth middleware wired into existing endpoints:
- `/query/` — requires board/homeowner JWT or valid API key
- `/ingest/` — requires admin JWT or API key scoped to matching community
- `/documents/` — requires any valid JWT; filters by JWT community_id

**2.5** Login page in UI; token stored in `localStorage`; 401 interceptor redirects to login

**2.6** Tests: `tests/test_auth.py`
- Password hashing round-trip
- Token create/decode round-trip
- Role requirement enforced (403 on wrong role)
- Community scope enforced (board user cannot query another community)
- API key validation

### Block 3 — Admin API and Dashboard

**3.1** `app/api/admin.py` — all endpoints listed above

**3.2** Update `app/api/query.py` to populate new `query_log` columns on every request:
`gate1_blocked`, `gate3_retry_fired` (pass flags up from router), `min_retrieval_score`,
`user_id`

**3.3** Update `app/orchestrator/router.py` to return accuracy metadata alongside the
response so `query.py` can record it in `query_log`

**3.4** Admin panel UI at `/admin`

**3.5** Tests: `tests/test_admin.py` — query-log filtering, community CRUD, user management

### Block 4 — Multi-Community

**4.1** Community selector in query UI (admin dropdown; board/homeowner label from claims)

**4.2** Community onboarding script `scripts/onboard_community.py`
- Creates knowledge_tier record (community, with parent = county)
- Prints tier ID for use in ingestion commands
- Verifies the tier is reachable from the state tier via parent chain

**4.3** Onboard second beta community
- Run `onboard_community.py`
- Ingest governing documents with improved OCR pipeline
- Run 10 validation queries; verify retrieval regression test passes for this community

**4.4** Data isolation verification
- Integration test: user scoped to community A cannot retrieve chunks from community B
- Integration test: admin can query both communities

**4.5** Retrieval regression test extended for second community

### Block 5 — Email Drafting

**5.1** Add `DraftBoardNoticeInput` and `DraftedNotice` to `agents/shared/models.py`

**5.2** `agents/customer-service-mcp/tools/draft_board_notice.py`
- System prompt: formal, citation-required, professional board communication
- Apply Gate 2 citation constraint (same pattern as `format_homeowner_response`)
- Apply Gate 3 grounding check (same `check_citation_grounding` call)
- `review_checklist` auto-populated with placeholder flags
- Token budget: `max_tokens=1200`

**5.3** Register tool in `agents/customer-service-mcp/server.py`

**5.4** `query_source="email_draft"` routing in `app/orchestrator/router.py`
- Same decompose → parallel search → merge pipeline
- Calls `draft_board_notice` instead of `format_homeowner_response`

**5.5** Draft Notice UI tab (topic input + notice type dropdown + rendered draft + checklist)

**5.6** Contract tests: `DraftBoardNoticeInput` and `DraftedNotice` in `test_shared_models.py`

**5.7** Unit tests: `tests/agents/test_draft_board_notice.py`

### Block 6 — Production LLM

**6.1** Set `LLM_PROVIDER=claude` in `.env` on hoa-api

**6.2** Validate all query paths against Claude:
- 10 board queries, 10 homeowner queries, 5 email draft requests
- Confirm Gate 3 retry rate drops vs. Ollama baseline
- Confirm Gate 1 threshold is still correctly calibrated for Claude's response style

**6.3** Update `app/services/llm.py` to document clearly:
- `complete()` uses `LLM_PROVIDER` setting
- `decompose_query()` always uses Ollama regardless of provider
- `complete_ocr_cleanup()` always uses Ollama regardless of provider

**6.4** Benchmark: record p50/p95 for Claude path vs. Ollama path

### Block 7 — Infrastructure Hardening

**7.1** HTTPS for `hoa.lan` via Caddy internal CA (should be automatic)

**7.2** PostgreSQL backup: `pg_dump` cron job on hoa-db, retain 7 days

**7.3** MinIO backup strategy: document sync policy or periodic snapshot

**7.4** Confirm log rotation is functioning after extended operation

---

## Testing Requirements

All Phase 1 test requirements carry forward. Phase 2 additions:

- `tests/test_retrieval_regression.py` — must pass before any Phase 2 feature merge
- `tests/test_auth.py` — auth service unit tests; no live DB calls
- `tests/test_admin.py` — admin API tests with mocked DB
- `tests/agents/test_draft_board_notice.py` — unit tests for the new tool
- `tests/test_shared_models.py` — extended to cover `DraftBoardNoticeInput` and `DraftedNotice`
- Integration tests in `tests/integration/` for community data isolation (tagged, skipped in CI)
- All new services in `app/services/` require unit tests before merge

---

## Success Criteria — Phase 2 Exit Gate

Phase 2 is complete when all of the following are true:

1. Two or more communities are ingested, queryable, and data-isolated
2. Authentication is live: admin, board, and homeowner roles all functional
3. A board user can log in, select their community, and receive scoped responses without admin involvement
4. Email drafting: 5+ real board notice drafts reviewed and rated accurate by a board member
5. `LLM_PROVIDER=claude` is the running production configuration
6. Admin dashboard: query log is visible with Gate 1/3 events; no log file access required
7. Retrieval regression test (`test_retrieval_regression.py`) passes for all onboarded communities
8. Gate 1 threshold has been formally calibrated and documented with rationale

---

## Phase 2 Tool Registry (6 tools total)

| Agent | Tool | Description |
|-------|------|-------------|
| governance-mcp | `search_community_rules` | Semantic search across tier hierarchy |
| governance-mcp | `get_section` | Full text of a specific section |
| governance-mcp | `compare_rules` | Cross-tier comparison with conflict detection |
| customer-service-mcp | `format_homeowner_response` | Homeowner or board-mode response formatting |
| customer-service-mcp | `flag_for_escalation` | Structured escalation for board/manager review |
| customer-service-mcp | `draft_board_notice` | *(new)* Formal board communication draft |

Before adding any tool beyond these 6: ask "can this be solved by improving an existing
tool's prompt or output?" If yes, do that instead.

---

## Key New Files

| File | Purpose |
|------|---------|
| `app/services/auth.py` | JWT creation/validation, password hashing, role dependencies |
| `app/api/auth.py` | Login, me, logout endpoints |
| `app/api/admin.py` | Admin-only query log, community, user management endpoints |
| `agents/customer-service-mcp/tools/draft_board_notice.py` | Email drafting tool |
| `agents/shared/models.py` | Extended with DraftBoardNoticeInput, DraftedNotice |
| `scripts/onboard_community.py` | Community tier creation + validation script |
| `tests/test_retrieval_regression.py` | Fixed query/source regression suite |
| `tests/test_auth.py` | Auth service unit tests |
| `migrations/` | users, api_keys tables; query_log additions |
