# Architecture Overview

For the complete architectural design and perimeter boundaries, refer to the [Architecture Foundation Specification](file:///architecture/foundation.md) and the [Project Master Blueprint](file:///OpsWingman_Project_Master_Blueprint.docx).

### Key Architectural Tenets
1. **Separation of Concerns**: Non-deterministic LLM drafting is strictly decoupled from deterministic policy evaluation and database mutation.
2. **Local-First & Zero-Cost Baseline**: Core services run locally without requiring paid third-party API dependencies.
3. **Observability**: End-to-end tracing and auditing via OpenTelemetry, Langfuse, and structured event logs.
