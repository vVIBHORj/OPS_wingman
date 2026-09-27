# OpsWingman — Architecture Foundation

This document outlines the core architectural boundaries, design principles, and subsystem structure for **OpsWingman**.

---

## 1. System Vision & Paradigm

OpsWingman is built around a **deterministic control perimeter** where non-deterministic AI capabilities (LLM generation, semantic classification, summarization) are isolated from critical operational actions (database writes, financial payments, external API side effects).

```
                      [ External Channels / Synthetic Simulator ]
                                         │
                                         ▼
                      ┌─────────────────────────────────────────┐
                      │             FastAPI Backend             │
                      │  - Event Ingestion & Request Validation │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │    Deterministic Policy & Auth Guard    │
                      │  - Policy Verification (Non-LLM)        │
                      │  - Role / Tenant Permission Checks      │
                      └────────────────────┬────────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
      ┌─────────────────────────────────┐   ┌─────────────────────────────────┐
      │         Agent / LLM Layer       │   │     Deterministic Workflows     │
      │  - Intent Understanding         │   │  - State Machine Transitions    │
      │  - Tool Parameter Formulation   │   │  - Database Truth (PostgreSQL)  │
      │  - Draft Generation             │   │  - Valkey Queue / Checkpoints   │
      └─────────────────┬───────────────┘   └─────────────────┬───────────────┘
                        │                                     │
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │        Execution & Tool Registry        │
                      │  - Human Approval Gateway (if required) │
                      │  - Idempotent API Execution             │
                      │  - Post-action State Verification       │
                      │  - Append-Only Audit Logging            │
                      └─────────────────────────────────────────┘
```

---

## 2. Core Architectural Pillars

### Pillar I: LLMs Are Not Decision Authorities
- The LLM **proposes** actions and drafts content.
- The **deterministic backend code validates** whether the proposed action complies with business rules, account permissions, and risk thresholds.
- Sensitive actions (e.g., refunds exceeding ₹500, address modifications after shipment dispatch, account status changes) **must require human approval** via the approval queue.

### Pillar II: Ground Truth Resides in PostgreSQL
- The database is the single source of operational truth.
- Vector embeddings in `pgvector` index verified documentation and historical tickets, preserving citations and provenance.
- State machines in Valkey / PostgreSQL maintain checkpointed run states for resumability and audit trails.

### Pillar III: Complete Observability & Traceability
- Every agent invocation, tool call, and policy evaluation is traced via OpenTelemetry and logged to self-hosted Langfuse.
- An immutable audit trail records timestamps, user IDs, agent run IDs, tool parameters, and post-action verification diffs.

---

## 3. Subsystem Breakdown

### 3.1 Backend Modules (`backend/`)
- **`api/`**: RESTful endpoints with Pydantic validation, CORS, and standard error handling.
- **`agents/`**: Stateful workflow agents constructed with deterministic graph transitions.
- **`workflows/`**: Business process state machines and checkpointing.
- **`tools/`**: Strongly-typed tool interfaces with strict schema enforcement and permission tags.
- **`policies/`**: Deterministic rule engines calculating risk, refund eligibility, and SLA constraints.
- **`rag/`**: Retrieval-augmented generation with document chunking, embeddings, and provenance tracking.
- **`ml/`**: Machine learning models for risk scoring and anomaly detection.
- **`approvals/`**: Human-in-the-loop review queue and resume triggers.
- **`audit/`**: Structured audit logger ensuring complete compliance and replayability.
- **`security/`**: Input sanitization, token management, and secret boundaries.
- **`evaluation/`**: Live assertion checks and runtime quality monitors.

### 3.2 Simulator (`simulator/`)
- Standalone seed generator producing synthetic customers, orders, payments, shipments, and customer service tickets with known ground truth for deterministic verification.

### 3.3 Integrations (`integrations/`)
- Adapters for external APIs (Gmail, Razorpay, Shopify, WhatsApp) with high-fidelity local mock equivalents.

### 3.4 Evals & Regression (`evals/`)
- Golden benchmark datasets and automated evaluators testing accuracy, policy compliance, safety, and tool calling fidelity.

---

## 4. Phase Roadmap Alignment

| Phase | Title | Focus Area |
| :--- | :--- | :--- |
| **Phase 0** | **Foundation** *(Current)* | Monorepo structure, Docker orchestration, base configuration, documentation. |
| **Phase 1** | **Simulator & Operational API** | Synthetic data generator, CRUD endpoints, database schema & migrations. |
| **Phase 2** | **Agent & Workflow Engine** | Tool registry, LangGraph workflow state machine, checkpointing. |
| **Phase 3** | **RAG & Policy Governance** | pgvector indexing, deterministic policy engine, human approval workflow. |
| **Phase 4** | **ML, Verification & Resilience** | Risk scoring model, post-action verification, idempotency & retries. |
| **Phase 5** | **Evaluation & Hardening** | Golden dataset benchmarks, automated regression suites, e2e test verification. |
