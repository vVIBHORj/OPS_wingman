# Test Suite

OpsWingman utilizes a multi-tier testing strategy:
- `unit/`: Fast, isolated tests for deterministic algorithms, policy engines, and data contracts.
- `integration/`: Tests verifying database, cache, mock adapter, and container behavior.
- `e2e/`: Full workflow agent tests against the business simulator.
- `security/`: Tests validating authorization boundaries, secret protections, and prompt injection defense.
- `resilience/`: Failure recovery, timeout, and idempotency tests.
