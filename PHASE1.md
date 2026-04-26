# hoa-oracle — Phase 1 Technical Implementation Plan

---

## Current Status — 2026-04-26

### ✅ Completed

**Infrastructure**
- Both VMs provisioned and running (hoa-api: 192.168.169.195, hoa-db: 192.168.169.194)
- PostgreSQL 16 + pgvector installed and migrated on hoa-db
- MinIO running on hoa-db, bucket created, hoa-api connectivity confirmed
- Ollama (`gemma3:4b`) confirmed running on Gaasp (192.168.169.110)
- FastAPI app running as systemd service (`hoa-oracle.service`) on hoa-api, auto-restarts on failure

**Core Pipeline**
- Full ingestion pipeline: PDF/DOCX → OCR → chunk → embed → MinIO + PostgreSQL
- OCR improvements: `image_to_string` preserves document structure; sparse text threshold (200 chars/page avg) forces Tesseract on court-stamp-only PDFs; court stamp regex stripping applied to both text-layer and Tesseract paths
- Embedding model pinned to `nomic-ai/nomic-embed-text-v1.5` v5.4.1 with `local_files_only=True`; version mismatch halts ingestion and logs error
- Batch embedding (16 chunks/batch) prevents OOM on low-RAM VM for large documents
- Hierarchical retrieval with tier boost: community 0.75x, county 0.90x, state 1.0x — ensures local rules rank above equivalent state law; sort direction bug fixed (was reverse=True, should be ascending cosine distance)
- Document versioning: amendment/correction flow implemented; superseded_by_id filter applied in all retrieval paths

**Agents & Orchestration**
- `governance-mcp`: all 3 tools implemented and working as subprocess (search_community_rules, get_section, compare_rules)
- `customer-service-mcp`: both tools implemented (format_homeowner_response, flag_for_escalation)
- Dual response tone: `query_source="homeowner"` (warm, advisory, 800 tokens) vs `query_source="board"` (factual, citation-heavy, 2000 tokens) — both paths go through format_homeowner_response with tone parameter
- MCP subprocess boundary confirmed: `sys.executable` used for subprocess launch (fixes PATH issue under systemd)
- Orchestrator routes both board and homeowner queries through full two-agent pipeline
- Input sanitization: 4 injection patterns blocked, 2000-char truncation

**Query Intelligence** *(added beyond original spec)*
- Query decomposition via Ollama: verbose or multi-part user input is rewritten into 1–6 focused search terms before vector search, improving retrieval on conversational queries
- Parallel sub-query execution via `asyncio.gather` with semaphore-bounded concurrency (`MAX_CONCURRENT_SEARCHES=2`) to prevent OOM on low-RAM VM
- Result merging and deduplication across sub-queries: best relevance score per unique chunk, capped at 20 results; synthesis LLM receives original query + sub-query list for context-aware multi-part answers
- Graceful fallback: if Ollama is unavailable for decomposition, pipeline falls back to original query with zero user impact

**Accuracy Pipeline** *(added beyond original spec)*
- **Gate 1 — Retrieval confidence threshold** (`retrieval_gate_threshold=0.46`): if the best chunk score exceeds the threshold, synthesis is skipped entirely and a canned "couldn't find reliable information" response is returned; no hallucination risk from bad retrieval
- **Gate 2 — Constrained synthesis prompts**: both homeowner and board prompts include explicit citation constraint — "quote verbatim before interpreting; cite only sections present in the Compliance facts"
- **Gate 3 — Citation grounding check + conditional retry**: after synthesis, regex extracts all Section/Article references from the response and verifies each appears in the retrieved chunk corpus; 2+ ungrounded citations triggers one retry with explicit correction instruction; if retry still fails, disclaimer is appended to response
- `app/services/faithfulness.py`: standalone citation extraction and grounding check module — deterministic, no LLM call, instant

**Observability**
- Structured JSON logging to `logs/app.log` (rotating, 10MB × 7 files)
- Per-agent tool logging: inputs (truncated), chunk-level retrieval results (DEBUG), LLM response (INFO)
- `query_log` table wired: every query records text, response, model, latency_ms, success, error
- Stdout logging for journald (`journalctl -u hoa-oracle`)

**Web UI** *(added beyond original spec)*
- 3-panel FastAPI-served HTML UI at port 8000: Ask a Question, Documents, Upload Document
- Document text viewer (modal, click any row)
- Document delete button with confirmation
- Tier slug resolution in upload form (no integer IDs required)
- Mobile-compatible

**Code Quality**
- Agent README.md files completed: governance-mcp and customer-service-mcp both document tool contracts, accuracy pipeline behavior, tone guidelines, and preemption rules
- 67 unit/contract tests passing; integration tests correctly excluded from default run
- Contract test (`test_shared_models.py`) confirms all shared models round-trip through JSON

---

### 🔲 Remaining for Phase 1 Completion

**Documents — still needed**
- Montgomery County relevant ordinances at county tier (not yet ingested)
- Confirm Maryland HOA Act §11B is indexed at state tier (MD Condominium Act ingested; verify HOA Act is separate and present)

**Validation — not yet formally run**
- 10 board-style queries: verify sourced responses, correct section citations, Gate 1/3 behavior observable in logs
- 10 homeowner-style queries: verify warm tone, accurate rules, alternatives suggested where applicable
- `compare_rules` with `potential_conflicts=true` — preemption hierarchy applied correctly in response
- Superseded document filter: re-ingest one document as amendment, confirm old chunks absent from all query results
- Embedding model version mismatch: confirm halts ingestion without crashing server
- OCR cleanup Ollama path: confirm triggers below 0.70 confidence threshold

> **⚠️ MAJOR TODO — Gate 1 threshold calibration**
> `RETRIEVAL_GATE_THRESHOLD` is currently set to `0.46` based on a small initial sample.
> This value must be validated against real query traffic before Phase 2.
> Requires reviewing `query_log` retrieval scores across 20+ representative queries
> and adjusting the threshold so Gate 1 blocks genuinely low-confidence retrievals
> without refusing answerable questions.
> **Blocked on: easy access to `query_log` data from hoa-db.**
> Also review Gate 3 retry rate — if retries are firing frequently, Gate 2 prompt
> constraint may need tightening before the threshold is correct.

**Performance**
- Query latency p50/p95: decomposition adds ~3–5s; parallel search keeps vector time flat; total expected ~25–35s on Ollama
- Benchmark with `LLM_PROVIDER=claude`: switch, run same 10 queries, compare quality and latency
- Gate 3 retry latency: measure how often retry fires and average latency impact

**Infrastructure — pending**
- Caddy reverse proxy on Worker1 (`hoa.lan` site block) — not yet configured
- Uptime Kuma monitors on Worker2 (hoa-api /health, hoa-db PostgreSQL port, MinIO health) — not yet added

**Tests — pending**
- Retrieval regression test (`test_retrieval_regression.py`): 10 fixed query/expected-source pairs against seeded dataset; must pass before Phase 2

---

### ⚠️ Deviations from Original Spec

| Item | Original | Actual |
|------|----------|--------|
| Board query path | Governance only, raw results | Routes through format_homeowner_response with `query_source="board"` for formatted citation-heavy response |
| Retrieval ranking | Raw cosine distance merge | Tier-boosted ranking (community 0.75x, county 0.90x) + sort direction fix |
| Query processing | Single query → vector search | Ollama decomposition → N parallel sub-queries → merged results |
| Accuracy / hallucination | Not specified | 3-gate accuracy pipeline: retrieval threshold, constrained prompts, citation grounding check + retry |
| Web UI | Not in Phase 1 | Added: 3-panel HTML UI for query, document management, upload |
| Logging | Not specified | Added: structured JSON file logging + query_log wiring |
| systemd service | Not specified | Added: auto-start service unit |
| OCR structure | Basic word-join | Upgraded to `image_to_string` + court stamp stripping |
| `format_homeowner_response` signature | 3 params | Added `query_source` + `sub_queries` params |

---

## Objective

Build a working single-community document intelligence system that can ingest governing documents, index them with embeddings, and answer natural language queries against them using Claude. Validate on Wickford HOA documents and a base set of Maryland state HOA statutes.

This phase runs entirely on Proxmox homelab infrastructure. No multi-tenancy. No public-facing deployment. Goal is IOC: a working end-to-end pipeline from document upload to sourced Q&A response.

**Critical architectural note:** Phase 1 focuses on compliance documents, but the architecture must be built data-type agnostic from day one. The same ingestion pipeline, tier hierarchy, vector retrieval, and MCP tools that handle governing documents must be able to absorb emails, invoices, work orders, and financial records in later phases without a structural rewrite. Every design decision should be evaluated against this constraint.

---

## Infrastructure

Phase 1 uses existing homelab hardware. No new machines are required. The original three-VM spec is replaced with a two-VM layout on ARProtect, leveraging Gaasp's GPU for LLM inference and Worker1's existing Caddy instance for reverse proxying.

### Hardware Inventory

| Host | Specs | IP | Current Role |
|------|-------|----|-------------|
| **Gaasp** | Windows Pro, i7-7700K, 32GB RAM, GTX 1070 8GB | 192.168.169.110 | MCP servers, Ollama (`gemma3:4b`) |
| **ARProtect** | Proxmox, i7-6700, 24GB RAM | 192.168.169.24 | Proxmox hypervisor |
| **Worker1** | Pi 4, 8GB RAM | 192.168.169.211 | Caddy reverse proxy for LAN |
| **Worker2** | Pi 4, 8GB RAM | 192.168.169.212 | Uptime Kuma + monitoring |

### Phase 1 Deployment Layout

| Component | Host | Deployment | Specs |
|-----------|------|-----------|-------|
| FastAPI app + both MCP subprocesses | ARProtect → `hoa-api` VM | Debian 13 | 2 vCPU, 4GB RAM |
| PostgreSQL 16 + pgvector + MinIO | ARProtect → `hoa-db` VM | Debian 13 | 2 vCPU, 6GB RAM |
| Ollama (`gemma3:4b`) | Gaasp (bare metal) | Already running | GPU-backed, no change |
| Reverse proxy / LAN access | Worker1 | Caddy (add new site block) | No change to existing setup |
| Endpoint monitoring | Worker2 | Uptime Kuma (add new monitors) | No change to existing setup |

**Why this layout:**

- **Ollama stays on Gaasp.** The GTX 1070 (8GB VRAM) runs `gemma3:4b` comfortably. Running LLM inference on CPU inside an ARProtect VM would be 5–10x slower for no reason. The `hoa-api` VM calls Ollama over the LAN at `http://192.168.169.110:11434` — straightforward network call, no GPU needed on ARProtect.
- **`hoa-dev` VM eliminated.** Its original jobs were Ollama (→ Gaasp), MinIO (→ collocated with DB), and dev tools (→ your workstation). A third VM was pure overhead.
- **MinIO collocated with PostgreSQL on `hoa-db`.** The I/O contention concern only materializes under concurrent heavy ingestion + search load — not realistic in Phase 1 with one community's documents. Revisit separation in Phase 2 if ingestion volume grows. `hoa-db` gets 6GB RAM (vs. the original 4GB) to give PostgreSQL and MinIO comfortable headroom.
- **Debian 13 for both VMs.** Proxmox itself runs on Debian, so the hypervisor and both VMs share the same package ecosystem, `apt` tooling, and kernel lineage. No context switching between host and guest environments when debugging. Debian's conservative release model also means less unprompted environmental drift — things don't break between updates, which matters when agent-assisted tooling is your primary debug path.
- **Use VirtIO drivers.** When creating each VM in Proxmox, select VirtIO for both the disk controller and the network adapter. The default emulated drivers (IDE, E1000) are significantly slower. This is easy to miss in the creation wizard.
- **Worker1/Caddy handles LAN access.** Add a single site block to the existing Caddy config pointing to `hoa-api`'s internal IP. No new reverse proxy infrastructure needed.
- **Worker2/Kuma monitors health.** Add `hoa-api` (`/health`) and `hoa-db` (PostgreSQL port check) as monitored endpoints. No new monitoring infrastructure needed.

### ARProtect VM Specs

Both VMs provisioned on ARProtect (24GB RAM, i7-6700). Total allocation leaves ~14GB RAM free for the host and any other existing VMs.

```
hoa-api:  2 vCPU, 4GB RAM, 20GB disk, Debian 13, VirtIO disk + network, static IP: 192.168.169.x
hoa-db:   2 vCPU, 6GB RAM, 60GB disk, Debian 13, VirtIO disk + network, static IP: 192.168.169.x
```

Disk sizing: `hoa-db` gets 60GB to accommodate PostgreSQL data, pgvector indexes, and MinIO document storage for Phase 1 document volume. Expand if ingesting large scanned PDFs at scale.

SSH key auth only. Both VMs on the same Proxmox bridge (vmbr0), same subnet as Gaasp and Worker nodes.

### Ollama Model Alignment

The existing Ollama installation on Gaasp runs `gemma3:4b`. The original spec referenced `llama3.2` — align all references to `gemma3:4b` as the primary dev/OCR-cleanup model. If `llama3.2` is also installed and preferred for specific tasks, document it explicitly in `OLLAMA_MODEL` env var. Do not assume a model is available without confirming it is pulled on Gaasp.

### Worker1 Caddy Configuration (addition only)

Add to the existing Caddyfile on Worker1:

```
hoa.lan {
    reverse_proxy 192.168.169.x:8000   # hoa-api internal IP
}
```

This gives LAN access to the FastAPI API at `https://hoa.lan` with automatic TLS via Caddy's internal CA — consistent with how other LAN services are already fronted.

### Worker2 Monitoring (addition only)

Add to Uptime Kuma on Worker2:
- HTTP monitor: `http://192.168.169.x:8000/health` (hoa-api FastAPI health endpoint)
- TCP monitor: `192.168.169.x:5432` (hoa-db PostgreSQL port)
- HTTP monitor: `http://192.168.169.x:9000/minio/health/live` (MinIO health endpoint)



---

## Tech Stack

```
Python 3.12
FastAPI              — REST API layer
MCP Python SDK       — MCP servers (governance-mcp, customer-service-mcp) + MCP client (orchestrator)
PostgreSQL 16        — Structured metadata and community records
pgvector             — Vector embeddings for semantic search
MinIO                — Document blob storage (S3-compatible)
SQLAlchemy           — Async ORM (asyncpg driver)
Alembic              — DB migrations
Tesseract            — OCR for scanned documents
PyMuPDF (fitz)       — PDF processing
python-docx          — DOCX processing
Anthropic SDK        — Claude API integration
Ollama               — Local LLM for dev/testing + OCR cleanup
sentence-transformers — Embedding generation (nomic-embed-text, pinned version)
```

---

## Database Schema

### PostgreSQL Tables

```sql
-- Tier classification for all document sources
CREATE TABLE knowledge_tiers (
    id          SERIAL PRIMARY KEY,
    tier        VARCHAR(10) NOT NULL,  -- 'state', 'county', 'community'
    name        VARCHAR(255) NOT NULL, -- 'Maryland', 'Montgomery County', 'Wickford HOA'
    slug        VARCHAR(100) NOT NULL UNIQUE, -- 'maryland', 'montgomery-county', 'wickford'
    parent_id   INT REFERENCES knowledge_tiers(id),
    metadata    JSONB,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Seed data:
-- tier=state,    name='Maryland',             slug='maryland'
-- tier=county,   name='Montgomery County',    slug='montgomery-county',  parent_id -> Maryland
-- tier=community,name='Crest of Wickford HOA',slug='wickford',           parent_id -> Montgomery County

-- Raw document registry
CREATE TABLE documents (
    id                  SERIAL PRIMARY KEY,
    tier_id             INT NOT NULL REFERENCES knowledge_tiers(id),
    title               VARCHAR(500) NOT NULL,
    doc_type            VARCHAR(100), -- Phase 1: 'declaration', 'bylaws', 'statute', 'ordinance', 'resolution', 'minutes'
                                      -- Phase 3+: 'email', 'invoice', 'work_order', 'financial_record', 'communication'
    data_category       VARCHAR(50) DEFAULT 'compliance', -- 'compliance' | 'operational' | 'financial' | 'communication'
    file_path           VARCHAR(1000), -- MinIO object path
    original_filename   VARCHAR(500),
    mime_type           VARCHAR(100),
    ocr_processed       BOOLEAN DEFAULT FALSE,
    ocr_confidence      FLOAT,        -- Tesseract mean confidence score (0.0-1.0); NULL if not OCR'd
    -- NOTE: raw_text is intentionally excluded from SELECT * patterns.
    -- Only fetch raw_text during chunk generation. Use explicit column projections everywhere else.
    raw_text            TEXT,
    page_count          INT,
    effective_date      DATE,
    superseded_by_id    INT REFERENCES documents(id),  -- NULL = current; set when document is amended
    version_note        VARCHAR(500),  -- e.g. "2024 amendment to Section 6.3"
    pii_notes           TEXT,          -- documents any PII present; required for Phase 2 compliance
    metadata            JSONB,        -- extensible: email headers, invoice numbers, work order IDs, etc.
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- Index to make "current documents only" queries fast
CREATE INDEX idx_documents_current ON documents (tier_id, doc_type)
    WHERE superseded_by_id IS NULL;

-- Chunked document segments for embedding/retrieval
CREATE TABLE document_chunks (
    id          SERIAL PRIMARY KEY,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content     TEXT NOT NULL,
    page_number INT,
    section_ref VARCHAR(255),  -- e.g. "Article IV, Section 2"
    metadata    JSONB,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- pgvector extension + embeddings table
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunk_embeddings (
    id              SERIAL PRIMARY KEY,
    chunk_id        INT NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    embedding       vector(768),   -- nomic-embed-text dimension — do not change without migration
    model_name      VARCHAR(100) NOT NULL DEFAULT 'nomic-embed-text',
    model_version   VARCHAR(50)  NOT NULL,  -- pinned version string from settings.EMBEDDING_MODEL_VERSION
    created_at      TIMESTAMP DEFAULT NOW()
);

-- HNSW index: performs correctly at any dataset size, including small Phase 1 datasets.
-- Do NOT use ivfflat — it requires ~2000+ rows before the planner uses it and actively
-- degrades performance on small tables.
CREATE INDEX ON chunk_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Query and response audit log
CREATE TABLE query_log (
    id               SERIAL PRIMARY KEY,
    session_id       VARCHAR(64),         -- client-generated session token for grouping related queries
    tier_id          INT REFERENCES knowledge_tiers(id),
    query_source     VARCHAR(20) NOT NULL, -- 'board' | 'homeowner' | 'cli'
    query_text       TEXT NOT NULL,
    retrieved_chunks JSONB,               -- chunk IDs and scores used
    response_text    TEXT,
    model_used       VARCHAR(100),
    latency_ms       INT,
    success          BOOLEAN DEFAULT TRUE,
    error            TEXT,                -- populated if success=FALSE
    pii_redacted     BOOLEAN DEFAULT FALSE, -- FALSE in Phase 1 (homelab); must be TRUE before Phase 2
    created_at       TIMESTAMP DEFAULT NOW()
);
```

---

## Project Directory Structure

```
hoa-oracle/
├── CLAUDE.md
├── PROJECT.md
├── PHASE1.md
├── .env.example
├── requirements.txt
│
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings via pydantic-settings
│   ├── database.py              # SQLAlchemy async engine + session
│   │
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── tier.py
│   │   ├── document.py          # Includes superseded_by_id, version_note, pii_notes
│   │   └── chunk.py
│   │
│   ├── api/                     # FastAPI routers
│   │   ├── __init__.py
│   │   ├── ingest.py            # Document upload and processing
│   │   ├── query.py             # Public query endpoint — applies input sanitization before orchestrator
│   │   └── documents.py         # Document management CRUD (excludes raw_text from list responses)
│   │
│   ├── orchestrator/            # Agent coordination layer
│   │   ├── __init__.py
│   │   ├── router.py            # Decides which agents to invoke per query type
│   │   ├── mcp_client.py        # MCP stdio client — ONLY path to all agent tools
│   │   └── context.py           # Builds context packages passed between agents
│   │
│   └── services/
│       ├── __init__.py
│       ├── ocr.py               # Tesseract + Ollama cleanup (never Claude API)
│       ├── chunker.py           # Text splitting strategy (data-type agnostic)
│       ├── embedder.py          # Embedding generation (version-locked nomic-embed-text)
│       ├── retriever.py         # Hierarchical async vector retrieval
│       └── llm.py               # Claude/Ollama abstraction layer
│
├── agents/
│   ├── shared/                  # Single source of truth for all tool schemas
│   │   ├── __init__.py
│   │   └── models.py            # All Pydantic input/output models for all tools
│   │
│   ├── governance-mcp/          # Compliance fact-finding agent (out-of-process MCP server)
│   │   ├── server.py            # MCP server entry point (stdio transport)
│   │   ├── README.md            # Agent contract, tool definitions, preemption hierarchy rules
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── search_community_rules.py
│   │       ├── get_section.py
│   │       └── compare_rules.py
│   │
│   └── customer-service-mcp/    # Homeowner-facing agent (out-of-process MCP server)
│       ├── server.py            # MCP server entry point (stdio transport)
│       ├── README.md            # Agent contract, tone guidelines, escalation rules, preemption handling
│       └── tools/
│           ├── __init__.py
│           ├── format_homeowner_response.py
│           └── flag_for_escalation.py
│
├── storage/
│   ├── __init__.py
│   └── minio_client.py          # MinIO operations
│
├── scripts/
│   ├── seed_tiers.py            # Seed state/county/community tier data
│   ├── ingest_document.py       # CLI document ingestion
│   └── test_query.py            # CLI query tester (invokes orchestrator)
│
├── migrations/                  # Alembic migrations
│   └── versions/
│
└── tests/
    ├── agents/
    │   ├── test_governance_tools.py
    │   └── test_customer_service_tools.py
    ├── test_orchestrator.py
    ├── test_ocr.py
    ├── test_chunker.py
    ├── test_retrieval.py
    ├── test_shared_models.py         # CONTRACT TEST — runs in CI; catches schema drift
    ├── test_retrieval_regression.py  # Fixed query/source pairs against seeded Wickford data
    └── integration/
        └── test_end_to_end.py        # @pytest.mark.integration — skipped in CI
```

---

## Core Service Implementations

### Document Ingestion Pipeline (`services/ocr.py` + `services/chunker.py`)

```
1. Receive file upload (PDF, DOCX, TXT, image)
2. Check for existing document with same tier_id + title + doc_type.
   If found and not superseded: require operator confirmation —
     'amendment' → create new version row, set superseded_by_id on old
     'correction' → update existing row in place
   If not found: proceed with new ingestion.
3. Store raw file in MinIO under tier path:
      state/maryland/[filename]
      county/montgomery/[filename]
      community/wickford/[filename]
4. Extract text:
      PDF → PyMuPDF for text-layer PDFs
      PDF (scanned) → Tesseract OCR → capture mean confidence score
        If confidence < 0.70: attempt Ollama (gemma3:4b) cleanup pass
        If Ollama unavailable: log WARNING, store raw Tesseract output, continue
      DOCX → python-docx
      (Future: .eml → email parser; .csv/.xlsx → tabular extractor)
5. Chunk text:
      Target ~500 tokens per chunk, 50-token overlap
      Attempt section-aware splitting (detect "Article", "Section", numbered paragraphs)
      Store chunk with section_ref metadata where detectable
6. Assert embedding model version matches settings.EMBEDDING_MODEL_VERSION.
   If mismatch: log ERROR and halt ingestion for this document (do not halt server).
7. Generate embeddings with nomic-embed-text (sentence-transformers, pinned version).
   Store in chunk_embeddings with model_name AND model_version fields populated.
8. Update document record: ocr_processed=True, ocr_confidence, page_count, raw_text
```

### Hierarchical Retrieval (`services/retriever.py`)

```python
async def retrieve(query: str, community_tier_id: int, top_k: int = 8) -> list[dict]:
    """
    Retrieve relevant chunks across the tier hierarchy.
    Always search community first, then county, then state.
    Merge and deduplicate results, preserving tier source metadata.
    Filters out chunks belonging to superseded documents automatically.

    NOTE: This function is async. All DB calls must use await.
    """
    query_embedding = await embed(query)

    # Get tier ancestry: community -> county -> state
    tiers = await get_tier_ancestry(community_tier_id)

    results = []
    for tier in tiers:
        # Only retrieve chunks from non-superseded documents
        chunks = await vector_search(
            query_embedding,
            tier_id=tier.id,
            top_k=top_k,
            exclude_superseded=True,   # filter: WHERE documents.superseded_by_id IS NULL
        )
        for chunk in chunks:
            results.append({
                "chunk": chunk,
                "tier": tier.name,
                "tier_type": tier.tier,
                "score": chunk.score,
            })

    # Return top_k overall, ranked by score, with tier attribution
    return sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
```

### LLM Abstraction Layer (`services/llm.py`)

```python
class LLMClient:
    """
    Unified interface for Claude API and Ollama.
    Controlled by LLM_PROVIDER env var: 'claude' or 'ollama'

    Prompt quality is validated against Claude. Ollama output is acceptable
    for infrastructure testing but is not the quality baseline.

    All calls enforce explicit max_tokens budgets — never omit max_tokens.
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER  # 'ollama' for dev, 'claude' for prod

    async def complete(
        self,
        system: str,
        messages: list,
        max_tokens: int,          # Required. No default — callers must set this explicitly.
    ) -> str:
        if self.provider == "claude":
            return await self._claude_complete(system, messages, max_tokens)
        return await self._ollama_complete(system, messages, max_tokens)

    async def complete_ocr_cleanup(self, raw_text: str) -> str:
        """
        OCR cleanup always uses Ollama regardless of LLM_PROVIDER.
        Keeps ingestion cost at zero. Never calls Claude API.
        Raises OllamaUnavailableError if Ollama is unreachable — callers must handle.
        """
        return await self._ollama_complete(
            system="You are a document cleanup assistant. Fix OCR errors in the text below. Return only the corrected text.",
            messages=[{"role": "user", "content": raw_text}],
            max_tokens=500,
        )
        # Uses gemma3:4b on Gaasp (http://192.168.169.110:11434)

    async def _claude_complete(self, system, messages, max_tokens):
        # Anthropic SDK call
        ...

    async def _ollama_complete(self, system, messages, max_tokens):
        # Ollama local API call
        ...
```

### MCP Client (`app/orchestrator/mcp_client.py`)

```python
"""
The ONLY path from the orchestrator to any agent tool.
Never import and call agent tool functions directly — always go through here.
This preserves the subprocess boundary that makes agents independently
deployable, testable, and replaceable without touching orchestrator code.
"""
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession
import json

GOVERNANCE_MCP_SCRIPT   = "agents/governance-mcp/server.py"
CUSTOMER_SERVICE_SCRIPT = "agents/customer-service-mcp/server.py"

async def _invoke_tool(server_script: str, tool_name: str, arguments: dict) -> dict:
    """
    Internal: launch an MCP server subprocess and invoke one tool.
    Returns the parsed tool result dict.
    Raises MCPToolError on failure — callers must handle.
    """
    server_params = StdioServerParameters(
        command="python",
        args=[server_script],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return json.loads(result.content[0].text)

async def invoke_governance_tool(tool_name: str, arguments: dict) -> dict:
    return await _invoke_tool(GOVERNANCE_MCP_SCRIPT, tool_name, arguments)

async def invoke_customer_service_tool(tool_name: str, arguments: dict) -> dict:
    return await _invoke_tool(CUSTOMER_SERVICE_SCRIPT, tool_name, arguments)
```

### Orchestrator Routing Logic (`app/orchestrator/router.py`)

```python
# Phase 1: Rule-based routing (no LLM in the orchestrator)
# Phase 3+: Evolves toward LLM-assisted routing as agent count grows

async def route_query(
    query: str,
    query_source: str,        # 'board' | 'homeowner'
    community_tier_id: int,   # Integer FK — never a string slug
    session_id: str,          # Client-provided session token for query_log grouping
) -> dict:

    if query_source == "homeowner":
        # Step 1: Get compliance facts from governance-mcp
        facts = await invoke_governance_tool("search_community_rules", {
            "query": query,
            "community_id": community_tier_id,
        })
        # Step 2: Shape response for homeowner via customer-service-mcp
        response = await invoke_customer_service_tool("format_homeowner_response", {
            "query": query,
            "compliance_facts": facts,
            "community_id": community_tier_id,
        })
        return response

    elif query_source == "board":
        # Board queries go direct to governance — no shaping layer
        return await invoke_governance_tool("search_community_rules", {
            "query": query,
            "community_id": community_tier_id,
        })
```

---

## Phase 1 Tool Registry — LOCKED

**This is the immovable tool contract for Phase 1. Five tools across two MCP servers. No additions without explicit sign-off.**

Both `governance-mcp` and `customer-service-mcp` are full out-of-process MCP servers in Phase 1. This is a deliberate architectural choice: it validates the complete multi-agent orchestration pattern end-to-end before Phase 3 adds more agents, and the subprocess boundary enforces domain separation that would otherwise erode over time.

The goal is agent-first design, not endpoint-first. Claude does the reasoning. Tools do retrieval and shaping only. Any complexity that tempts a new tool should first be solved by improving Claude's prompt or the existing tool's output.

---

### `governance-mcp` — 3 Tools

All tool parameters that reference a community use `community_id: int` — the integer PK from `knowledge_tiers.id`. Slug-to-ID resolution happens at the API boundary, never inside a tool.

---

#### Tool 1: `search_community_rules`
```python
async def search_community_rules(
    query: str,           # Natural language query from the user or orchestrator
    community_id: int,    # knowledge_tiers.id for the community — always an integer
    top_k: int = 8        # Number of results to return (default 8, max 20)
) -> GovernanceSearchResult:
    """
    Semantic vector search across the full tier hierarchy for a community.
    Embeds the query, searches pgvector using HNSW cosine similarity across
    community → county → state tiers, and returns ranked results.

    Only returns chunks from non-superseded documents (superseded_by_id IS NULL).

    Use this as the first tool call for any compliance question.
    Returns ranked chunks — not a synthesized answer. Claude synthesizes.
    """
```
**Returns:**
```json
{
  "results": [
    {
      "chunk_text": "No more than two vehicles per unit...",
      "document_title": "Crest of Wickford Declaration of Covenants",
      "section_ref": "Article VIII, Section 3",
      "tier": "community",
      "relevance_score": 0.91,
      "document_id": 42,
      "effective_date": "2019-03-15"
    }
  ],
  "query": "parking limit per household",
  "community_id": 3,
  "tiers_searched": ["community", "county", "state"]
}
```

---

#### Tool 2: `get_section`
```python
async def get_section(
    document_id: int,    # documents.id — always an integer
    section_ref: str     # Section reference (e.g. "Article VIII, Section 3")
) -> SectionResult:
    """
    Retrieve the full text of a specific section given a document ID
    and section reference. Use when search_community_rules returns a
    chunk that needs more surrounding context — e.g. the full clause
    rather than just the matching chunk.

    Do not call this on every search result. Only call it when the
    chunk returned by search_community_rules is clearly incomplete.

    Will return a not-found error if the document_id refers to a
    superseded document. Always use IDs from search_community_rules
    results, which already filter superseded documents.
    """
```
**Returns:**
```json
{
  "document_title": "Crest of Wickford Declaration of Covenants",
  "section_ref": "Article VIII, Section 3",
  "full_text": "Section 3. Parking. No more than two (2) vehicles...",
  "preceding_section": "Article VIII, Section 2",
  "following_section": "Article VIII, Section 4",
  "document_id": 42
}
```

---

#### Tool 3: `compare_rules`
```python
async def compare_rules(
    query: str,           # The topic to compare across tiers
    community_id: int     # knowledge_tiers.id — always an integer
) -> CompareResult:
    """
    Surface all relevant rules that touch the same topic across all
    tiers (community, county, state), formatted for comparison.

    Use when a question might have different answers at different
    governance levels — e.g. noise rules governed by both bylaws
    and county ordinance.

    Returns structured comparison data, not a synthesized answer.
    Claude synthesizes. When potential_conflicts is true, Claude must
    apply the preemption hierarchy: state law overrides county ordinance,
    county ordinance overrides community rules. The controlling rule
    should be identified in the response.

    Only returns chunks from non-superseded documents.
    """
```
**Returns:**
```json
{
  "topic": "noise restrictions",
  "rules_by_tier": {
    "community": [{ "document_title": "...", "section_ref": "...", "text": "...", "document_id": 42 }],
    "county":    [{ "document_title": "...", "section_ref": "...", "text": "...", "document_id": 7  }],
    "state":     []
  },
  "potential_conflicts": true,
  "preemption_note": "Where community and county rules conflict, the county ordinance controls unless the community rule is more restrictive."
}
```

---

### `customer-service-mcp` — 2 Tools

`customer-service-mcp` never queries documents or the database directly. It receives compliance facts from the orchestrator as input parameters. All domain knowledge about tone, escalation, and preemption handling lives here and nowhere else.

---

#### Tool 4: `format_homeowner_response`
```python
async def format_homeowner_response(
    query: str,               # Original homeowner question
    compliance_facts: str,    # JSON-serialized GovernanceSearchResult from governance-mcp
    community_id: int         # knowledge_tiers.id — for community name/context only
) -> HomeownerResponse:
    """
    Takes raw compliance facts returned by governance-mcp and shapes
    them into a warm, clear, homeowner-appropriate response.

    Tone: respectful, helpful, never condescending. Acknowledge the
    homeowner's intent before delivering any constraint. Where a rule
    says 'no', suggest compliant alternatives where possible.

    When compliance_facts contains potential_conflicts=true, apply the
    preemption hierarchy: state law overrides county ordinance, county
    ordinance overrides community rules. Identify the controlling rule
    and communicate the conflict clearly without confusing the homeowner.

    Never fabricate rules. If compliance_facts are empty or insufficient,
    say so clearly and suggest contacting the board.
    max_tokens=800.
    """
```
**Returns:**
```json
{
  "response_text": "Great question about your landscaping plans! Your community guidelines do allow tree planting, with a few considerations...",
  "sources_cited": ["Crest of Wickford Rules & Regulations, Section 5.2"],
  "alternatives_suggested": true,
  "escalation_recommended": false
}
```

---

#### Tool 5: `flag_for_escalation`
```python
async def flag_for_escalation(
    query: str,            # Original homeowner question
    compliance_facts: str, # JSON-serialized GovernanceSearchResult
    reason: str            # 'ambiguous_rule' | 'conflict' | 'variance_request' | 'dispute'
) -> EscalationResult:
    """
    Marks a query as needing board or manager review. Use when
    compliance_facts are contradictory, when the situation requires
    a variance, or when the query involves a dispute.

    Returns a structured escalation summary suitable for forwarding
    to a board member or property manager.
    max_tokens=600.
    """
```
**Returns:**
```json
{
  "escalation_summary": "Homeowner is requesting approval for a 6-foot privacy fence on the east side of their property. Community rules cap fences at 4 feet, but Section 6.4 allows board-approved variances...",
  "reason": "variance_request",
  "relevant_rules": ["Section 6.3", "Section 6.4"],
  "recommended_action": "Board variance review required",
  "urgency": "normal"
}
```

---

### Tool Registry Rules

- **No new tools in Phase 1 without explicit sign-off.** If a new requirement emerges, first ask: can this be solved by improving Claude's reasoning prompt? Can an existing tool's output be enriched? Only add a tool if neither answer works.
- **Tools retrieve and shape. Claude reasons.** Never add reasoning logic inside a tool. Return structured data and let Claude synthesize.
- **All Pydantic models** for tool inputs and outputs live in `agents/shared/models.py`. All agents and the orchestrator import from this shared location. Never define tool schemas locally.
- **`community_id` is always `int`** in all tool signatures. Slug-to-ID resolution is the API boundary's job.
- **`customer-service-mcp` tools never query documents or the database directly.** They receive facts as input parameters from the orchestrator only.
- **`governance-mcp` tools always return `source_documents`.** No exceptions.
- **Only non-superseded documents** are returned by any governance tool. Apply `superseded_by_id IS NULL` filter in every query.
- **Contract test** (`tests/test_shared_models.py`) must pass in CI. If you change any model in `agents/shared/models.py`, the contract test catches drift immediately.

---

## Environment Configuration (`.env.example`)

```
# LLM Provider: 'ollama' for dev, 'claude' for prod
LLM_PROVIDER=ollama

# Ollama runs on Gaasp (GPU-backed, bare metal Windows host)
OLLAMA_BASE_URL=http://192.168.169.110:11434
OLLAMA_MODEL=gemma3:4b

ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514

# Database — hoa-db VM on ARProtect
DATABASE_URL=postgresql+asyncpg://hoa:password@192.168.169.x:5432/hoa_intelligence

# MinIO — collocated on hoa-db VM (same host as PostgreSQL, Phase 1 only)
MINIO_ENDPOINT=192.168.169.x:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET=hoa-documents

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000

# Embedding model — must match what was used at ingest time
# Changing this value requires re-embedding all chunks (new Alembic migration)
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_MODEL_VERSION=1.5

# Token budgets — do not remove; all LLM calls enforce these
MAX_TOKENS_GOVERNANCE=1500
MAX_TOKENS_CUSTOMER_SERVICE=800
MAX_TOKENS_OCR_CLEANUP=500

# OCR confidence threshold: Tesseract scores below this trigger Ollama cleanup
OCR_CONFIDENCE_THRESHOLD=0.70
```

---

## Phase 1 Build Sequence

1. **Infrastructure provisioning** — provision two VMs on ARProtect (`hoa-api`: 2vCPU/4GB/20GB, `hoa-db`: 2vCPU/6GB/60GB), both Debian 13, VirtIO disk and network drivers, static IPs, SSH key auth. Add Caddy site block on Worker1. Add health monitors on Worker2/Kuma. Confirm `hoa-api` can reach Ollama at `http://192.168.169.110:11434` and `gemma3:4b` responds.
2. **Database init** — PostgreSQL + pgvector on `hoa-db`, confirm pgvector extension present, run schema migrations (with `superseded_by_id`, `pii_redacted`, `ocr_confidence`, `query_source`, `session_id`, `model_version` columns), seed tier data
3. **MinIO setup** — install and start MinIO on `hoa-db`, create bucket, configure access, confirm `hoa-api` can reach it
4. **`agents/shared/models.py`** — define all Pydantic models for all five tool inputs/outputs before writing any agent or orchestrator code. Run contract test to confirm round-trip serialization passes.
5. **Ingestion pipeline** — OCR, chunking, embedding with version lock, MinIO storage. Test with 2–3 real documents. Verify `ocr_confidence` captured and Ollama cleanup path triggers correctly below threshold.
6. **Retrieval service** — async hierarchical vector search against HNSW index, validated with unit tests. Confirm superseded-document filter is applied. Run retrieval regression test with seeded fixtures.
7. **LLM layer** — Ollama integration first; Claude API wired but gated behind env var. Confirm `max_tokens` enforced on all calls. Confirm OCR cleanup hardwired to Ollama regardless of `LLM_PROVIDER`.
8. **`governance-mcp` server** — three tools wrapping retrieval + LLM, returns facts + citations with `source_documents`. Confirm `community_id` is always `int`. Confirm superseded filter applied in all three tools.
9. **MCP client** (`app/orchestrator/mcp_client.py`) — stdio transport, subprocess launch, `invoke_governance_tool` and `invoke_customer_service_tool` helpers. Verify the subprocess boundary works end-to-end with a single `search_community_rules` call before proceeding.
10. **`customer-service-mcp` server** — two tools that receive compliance facts and shape homeowner responses. Implement preemption hierarchy logic in `format_homeowner_response`. Unit test both tools against mocked governance facts.
11. **Orchestrator router** — rule-based routing, board vs homeowner paths. Input sanitization applied before routing. `session_id` threaded through to query log. Board path: governance only. Homeowner path: governance → customer-service.
12. **FastAPI routes** — `/ingest`, `/query` (with `query_source` and `session_id` params), `/documents` (explicit column projections, no `raw_text` in list responses)
13. **End-to-end CLI test** — ingest Wickford bylaws + Maryland HOA Act + one Montgomery County ordinance, run 10 real queries split between board and homeowner perspectives, validate both response types, confirm sources cited correctly and tone differences between board/homeowner paths are correct
14. **Flip to Claude** — set `LLM_PROVIDER=claude`, rerun same 10 queries, compare output quality, adjust prompts as needed (expect differences from Ollama baseline)

---

## Phase 1 Success Criteria

- [ ] At least 5 Wickford governing documents fully ingested and indexed
- [ ] Maryland HOA Act (key sections) ingested at state tier
- [ ] Montgomery County relevant ordinances ingested at county tier
- [ ] `governance-mcp` answers 10 board-style queries with sourced responses (document title + section cited)
- [ ] `customer-service-mcp` produces 10 homeowner-style responses: warm, accurate, compliant, sources cited
- [ ] Orchestrator correctly routes board queries to governance-only and homeowner queries through governance → customer-service
- [ ] Both MCP servers confirmed as true subprocesses: each can be killed and restarted independently without restarting the orchestrator
- [ ] Superseded document filter confirmed: re-ingest one document as amendment, verify old chunks do not appear in search results
- [ ] Embedding model version mismatch triggers halt-and-log (not server crash) — confirmed via test
- [ ] Ollama → Claude API switch works cleanly via `LLM_PROVIDER` env var only
- [ ] OCR cleanup uses Ollama regardless of `LLM_PROVIDER` — confirmed via test with `LLM_PROVIDER=claude`
- [ ] Query latency benchmarked (not assumed): measure p50 and p95 for single-agent and two-agent paths against both Ollama and Claude
- [ ] Contract test passes in CI: all models in `agents/shared/models.py` round-trip through JSON
- [ ] Retrieval regression test passes: 10 fixed query/source pairs all return correct source documents
- [ ] `compare_rules` with `potential_conflicts=true` produces response that correctly identifies the controlling rule via preemption hierarchy
- [ ] Each agent has a `README.md` documenting contract, tools, tone guidelines, and preemption rules
