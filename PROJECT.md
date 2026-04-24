# hoa-oracle — Project Overview

> **Repository:** `hoa-oracle`

## Vision

An AI-powered operational intelligence platform for Maryland HOA and COA communities — starting with compliance and expanding to become the reasoning brain across every aspect of how communities operate.

**Compliance is the entry wedge, not the ceiling.** Phase one proves the core value by reasoning over governing documents, state statutes, and county ordinances. But the long-term vision is far broader: the same architecture that ingests and reasons over legal documents scales naturally to emails, work orders, invoices, vendor communications, financial records, and meeting notes. Every data source a management company touches becomes an input to the platform's intelligence layer.

**Architecture:** The platform is built on a multi-agent MCP model. Each domain has a dedicated, specialized MCP server. A central orchestrator routes queries to the appropriate agents, passes context between them, and assembles Claude's final reasoning over their combined outputs. No single monolithic server — each agent does one thing well and is independently deployable, testable, and replaceable.

---

## Problem Statement

HOA and COA management involves two distinct but equally painful data challenges:

**Compliance data** — layered, constantly changing rules that communities must follow:
- Maryland state statutes (HOA Act, Condo Act, HOA Ombudsman rules)
- County-specific ordinances (Montgomery, Frederick, Anne Arundel, Prince George's, etc.)
- Community-specific governing documents: declarations, bylaws, rules and regulations, resolutions, meeting minutes
- Insurance and lending policy changes affecting community eligibility

**Operational data** — the daily volume of communications, transactions, and work that management companies must track:
- Emails and owner communications across dozens of communities
- Work orders, vendor invoices, and maintenance histories
- Financial records, assessment collections, budget tracking
- Board meeting notes, action items, decisions

These two categories of data are currently siloed, largely unstructured, and managed manually. Documents range from clean Word files to 50-year-old scanned PDFs. Management companies handle dozens of communities simultaneously. Mistakes — missed compliance windows, incorrect rule interpretations, duplicate invoices, inconsistent enforcement — create legal exposure and operational waste. The more localized the rules, the more consequential the errors.

---

## Target Market

**Primary:** Maryland HOA and COA communities managed by professional management companies or self-managed boards.

**Secondary:** Property management companies managing multiple Maryland communities (highest leverage).

**Initial beachhead:** Montgomery County and surrounding counties — the densest HOA market in Maryland.

---

## Core Use Cases

**Phase 1 — Compliance Intelligence (Documents)**
1. **Document Q&A** — "Can a homeowner park a commercial vehicle in their driveway?" → Platform retrieves and interprets community rules, cross-referencing county ordinances and state law.
2. **Compliance Checking** — Board wants to pass a new rule. Platform checks it against the declaration, Maryland HOA Act, and county zoning.
3. **Email Drafting** — Board needs to notify owners of a policy change. Platform drafts a compliant, accurate notice based on governing documents.
4. **Policy Monitoring** — Maryland General Assembly passes a new HOA-related bill. Platform flags affected communities and summarizes impact.
5. **Document Interpretation** — New board member uploads a 1978 scanned declaration. Platform OCRs, indexes, and makes it queryable.
6. **Owner-Facing Portal** — Homeowners can query their community rules directly, reducing board email volume.

**Phase 3+ — Operational Intelligence (Communications, Financials, Work Orders)**
7. **Management Report Generation** — Platform synthesizes emails, financials, and work orders into board-ready monthly reports automatically.
8. **Invoice Anomaly Detection** — Flags duplicate vendor invoices, billing pattern irregularities, or charges inconsistent with approved contracts.
9. **Maintenance Pattern Analysis** — Surfaces recurring issues across work order history, predicting future maintenance needs.
10. **Communication Intelligence** — Indexes owner and vendor email history per community, enabling instant retrieval of prior decisions, commitments, and disputes.
11. **Financial Forecasting** — Reasons over assessment history, reserve fund data, and pending work orders to surface cash flow risks.
12. **Enforcement Consistency** — Flags cases where similar violations were handled differently across the community, reducing board liability.

---

## Data Architecture

The platform is designed to ingest and reason over two categories of data, organized in a three-tier community hierarchy.

### Tier Hierarchy (applies to all data types)

```
TIER 1 — State Level (Shared across all communities)
  └── Maryland HOA Act (MD Code, Real Property § 11B)
  └── Maryland Condo Act (MD Code, Real Property § 11)
  └── MD HOA Ombudsman guidance
  └── Relevant case law and AG opinions

TIER 2 — County Level (Shared across communities in that county)
  └── Montgomery County zoning and noise ordinances
  └── Frederick County property codes
  └── Anne Arundel County regulations
  └── [Additional counties as onboarded]

TIER 3 — Community Level (Isolated per community)
  └── [See data types below]
```

### Data Types by Phase

**Phase 1 — Compliance Documents**
- Declaration of Covenants, Conditions & Restrictions
- Bylaws, Rules and Regulations, Board Resolutions
- Meeting Minutes, Amendment history

**Phase 3+ — Operational Data**
- Email and owner communications
- Work orders and maintenance histories
- Vendor invoices and contracts
- Financial records and budget data
- Assessment and collections history

When a query comes in, the platform retrieves from the relevant community store first, then bubbles up to county and state as needed. State-level data is never duplicated per community. The architecture is data-type agnostic — the same ingestion, indexing, and retrieval patterns that handle governing documents handle operational records.

---

## Multi-Agent Architecture

The platform is deliberately not a monolithic system. Each domain is handled by a dedicated MCP server (agent), coordinated by a central orchestrator. This keeps each agent focused, independently testable, and scalable without coupling.

### Phase 1 Agents

Both agents are fully operational out-of-process MCP servers in Phase 1. This is a deliberate decision: standing up both agents from the start validates the complete multi-agent orchestration pattern end-to-end, enforces domain separation at the subprocess boundary, and means Phase 3 adds capability to established agents rather than introducing new architectural patterns under pressure.

**`governance-mcp`** — The compliance fact engine. Retrieves and reasons over governing documents, Maryland statutes, and county ordinances. Cold, precise, always source-cited. This is the foundational agent that all others may draw from.

**`customer-service-mcp`** — The homeowner-facing agent. Receives compliance facts from the orchestrator and shapes them into warm, helpful, contextually appropriate responses. Knows how to say "no" without alienating residents. Suggests compliant alternatives. Never fabricates rules. Does not call `governance-mcp` directly — all coordination flows through the orchestrator.

### Phase 3+ Agents (Planned)

**`financial-mcp`** — Invoice processing, budget analysis, anomaly detection, assessment history.

**`communications-mcp`** — Email threads, board notices, correspondence history, pattern analysis across owner communications.

**`maintenance-mcp`** — Work orders, vendor history, recurring issue detection, predictive maintenance signals.

### Orchestrator

The orchestrator is the routing brain. For a homeowner query like "Can I install a shed?", it invokes `governance-mcp` for the rules, passes the result to `customer-service-mcp` to shape the response, and returns the final answer. For a board query about vendor billing patterns, it routes to `financial-mcp` and `maintenance-mcp`, correlates results, and passes context to Claude. Agents never call each other directly — all coordination flows through the orchestrator.

---

## Roadmap

### Phase 1 — Compliance MVP (Months 1–3)
Single community proof of concept. Governing document ingestion, OCR, Claude integration, basic compliance Q&A via CLI. Validated against one real community (Crest of Wickford HOA). Architecture deliberately built to be data-type agnostic for future operational data expansion. Runs on existing homelab infrastructure — two Debian 13 KVM VMs on Proxmox, with LLM inference on an existing GPU-equipped desktop (Gaasp). No greenfield hardware required.

### Phase 2 — Platform Foundation (Months 3–6)
Multi-tenant architecture. Basic web UI. Segmented community databases. MCP server layer finalized. Email drafting automation. Begin onboarding 2–3 beta communities.

### Phase 3 — Operational Data Layer (Months 6–9)
Expand beyond documents into operational data: email ingestion, work order indexing, invoice processing. Policy scraping and monitoring for law changes. Management report generation from operational data. County-level database buildout.

### Phase 4 — Commercial Launch (Months 9–12)
Pricing model live ($5,000–$10,000/community/year). Management company partnerships. Owner-facing portal. Financial anomaly detection and enforcement consistency tools. Maryland-wide county coverage.

### Phase 5 — Scale & Acquisition Readiness (Year 2+)
Multi-state expansion (Virginia, DC). API integrations with AppFolio, Buildium, and other platforms. Full operational intelligence suite. White-labeling for management companies. Positioned as acquisition target for major HOA platform players.

---

## Revenue Model

- **Community subscription:** $5,000–$10,000/year per community depending on size and document complexity
- **Management company bundle:** Volume pricing for companies managing 10+ communities
- **Setup/onboarding fee:** $500–$1,500 for document ingestion and initial configuration

---

## Competitive Moat

- Deep Maryland-specific domain knowledge baked into the platform
- Hierarchical knowledge architecture that scales cleanly across data types
- Compliance as entry wedge: low-risk, high-value proof point that opens the door to full operational intelligence
- Switching cost: once a community's documents, emails, financials, and work orders are ingested and indexed, migration is extremely painful
- Network effects from management company partnerships — each new community enriches county and state-level reasoning
- Proprietary OCR and document normalization pipeline for legacy documents
- Data-type agnostic architecture: the same system that reasons over bylaws reasons over invoices and emails without a redesign

---

## Technology Stack (Summary)

- **Backend:** Python (FastAPI)
- **LLM Layer:** Anthropic Claude API (Claude Sonnet for production); Ollama on existing homelab GPU hardware for development and OCR cleanup — no dedicated LLM infrastructure required
- **MCP Framework:** Python MCP SDK
- **Database:** PostgreSQL (structured metadata) + pgvector (embeddings)
- **Document Storage:** MinIO (S3-compatible, self-hosted)
- **OCR:** Tesseract + Ollama-assisted cleanup
- **Infrastructure:** Proxmox homelab (Debian 13 KVM VMs) → AWS migration path when scaling
- **Frontend:** React (Phase 2+)

---

## IOC (Initial Operating Capability) Definition

IOC is reached when:
1. A single community's governing documents are fully ingested and queryable
2. A board member can ask a natural language question and receive a sourced, accurate answer
3. The system correctly routes queries through the tier hierarchy (community → county → state)
4. At least one email draft is generated from a real governance scenario

IOC target: **end of Phase 1 (Month 3)**
