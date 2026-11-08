# OPSwingman Automated Test Suite

OPSwingman utilizes a deterministic, multi-tier automated test strategy designed to guarantee production safety, state consistency, resilient failure recovery, and zero data leakage.

---

## 1. Directory Structure & Classification

The test suite is organized into distinct directories by purpose and execution scope:

| Directory | Marker | Purpose & Scope |
| :--- | :--- | :--- |
| `tests/unit/` | `unit` | Fast, isolated tests for deterministic algorithms, policy engines, domain models, schemas, and scoring heuristics. |
| `tests/integration/` | `integration` | Tests verifying API request-to-database persistence, router boundaries, approval lifecycles, and service interactions. |
| `tests/resilience/` | `resilience` | Tests validating retries with exponential backoff, timeout budget enforcement, idempotency caching/deduplication, and state divergence detection. |
| `tests/security/` | `security` | Tests enforcing authorization boundaries, approval token verification, sensitive credential masking/sanitization, and prompt injection defense. |
| `tests/e2e/` | `e2e` | End-to-end customer journey tests simulating multi-step interactions through the full system stack (API, DB, approvals, state verification). |

---

## 2. Test Isolation & Safety Principles

1. **In-Memory Isolated Databases:**
   All database-backed tests use SQLite in-memory with `StaticPool` (`sqlite:///:memory:`) configured in `tests/conftest.py`. This ensures test isolation while allowing multi-threaded FastAPI `TestClient` workers to share the deterministic in-memory session.
2. **Deterministic Fixtures:**
   Fixtures generate non-colliding UUIDs, deterministic timestamps, and synthetic test credentials without contacting external systems.
3. **No Production or Staging Dependencies:**
   Tests never connect to production or staging databases, external endpoints, or external message queues.
4. **External Service Isolation:**
   Any test requiring external live networks or credentials must be explicitly decorated with `@pytest.mark.external`. These tests are never silently run in standard CI/CD test gates.
5. **No Data Leakage:**
   Sensitive payloads (passwords, API tokens, card numbers) are masked before persistence, logging, or API output.

---

## 3. Running the Tests

### Run the entire test suite
```bash
python -m pytest -v
```

### Run by tier / marker
```bash
# Run unit tests only
python -m pytest -m unit

# Run integration tests only
python -m pytest -m integration

# Run resilience tests only
python -m pytest -m resilience

# Run security tests only
python -m pytest -m security

# Run end-to-end tests only
python -m pytest -m e2e
```

### Run by directory path
```bash
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/resilience -q
python -m pytest tests/security -q
python -m pytest tests/e2e -q
```

### Run fast without external tests
```bash
python -m pytest -m "not external" -q
```

---

## 4. Code Quality & Linting

All test files must strictly conform to Ruff formatting and linting rules (no unused imports, sorted imports, line length <= 100):

```bash
# Check code and tests
python -m ruff check .

# Check specific test directory
python -m ruff check tests
```
