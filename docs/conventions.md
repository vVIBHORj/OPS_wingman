# OpsWingman — Coding & Configuration Conventions

This document establishes the foundational engineering and architectural standards for the OpsWingman monorepo.

---

## 1. Core Architectural Constraints

1. **Deterministic Security Perimeter**:
   - The LLM must NEVER be granted direct database write access, secret decryption capability, or unrestricted tool dispatch.
   - All tool calls must be explicitly validated against typed Pydantic models with defined permission scopes before execution.
2. **Deterministic Policies**:
   - Financial refunds, cancellation rules, and SLA limits must be computed in deterministic Python functions (`backend/policies/`), never inferred or decided by LLM prompt outputs.
3. **No Hard External Dependencies**:
   - The primary development workflow must remain 100% zero-cost and executable locally using Docker, Ollama, Mailpit, Valkey, and SQLite/Postgres.

---

## 2. Backend Conventions (Python / FastAPI)

- **Python Version**: 3.12+
- **Type Annotations**: Mandatory across all function signatures, parameters, and return types.
- **Validation**: Use Pydantic v2 schemas for all incoming payloads and outgoing API responses.
- **Async First**: Use `async`/`await` for all I/O operations (database access via asyncpg/SQLAlchemy, HTTP clients with httpx).
- **Error Handling**: Use structured FastAPI `HTTPException` or domain exception handlers with standardized error schemas (`{ "error": { "code": "...", "message": "...", "details": {...} } }`).
- **Imports**: Formatted with standard library first, third-party packages second, local project imports third (enforced by `ruff`).

---

## 3. Frontend Conventions (Next.js / TypeScript)

- **Framework**: Next.js App Router (`src/app/`).
- **Language**: TypeScript with strict mode enabled (`strict: true` in `tsconfig.json`).
- **Styling**: Tailwind CSS with CSS variables for dynamic theming and color palettes.
- **Components**: Functional components with explicit prop interfaces. Avoid `any` types.
- **State & Workflow Visuals**: React Flow for graph-based workflow and agent run visualizations.

---

## 4. Database & Migrations

- **ORM**: SQLAlchemy 2.0 declarative models placed in `database/models/`.
- **Migrations**: Alembic migrations placed in `database/migrations/`.
- **Naming Conventions**:
  - Tables: `snake_case` plural (e.g., `orders`, `customers`, `audit_logs`).
  - Columns: `snake_case` (e.g., `customer_id`, `created_at`).
  - Primary Keys: UUIDs or sequential big integers where appropriate.

---

## 5. Testing & Verification Conventions

- **Unit Tests (`tests/unit/`)**: Fast, pure in-memory tests verifying business logic, schemas, and policy calculations without external network calls.
- **Integration Tests (`tests/integration/`)**: Tests verifying interactions with Postgres, Valkey, Mailpit, and simulated external adapters.
- **E2E Tests (`tests/e2e/`)**: Full workflow verification from event trigger through agent graph to final verified state update.
- **Assertion Principle**: Every agent or tool execution test must assert on post-state mutation diffs, not merely LLM text output.
