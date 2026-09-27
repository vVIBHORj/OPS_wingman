# Evaluation & Benchmarking Subsystem

This module implements offline evaluation, golden dataset benchmarking, and regression testing for OpsWingman.

## Structure
- `datasets/`: Curated benchmark scenarios with known ground-truth actions and outputs.
- `evaluators/`: Deterministic and LLM-as-a-judge scoring evaluators (measuring tool call accuracy, policy compliance, safety, and hallucination).
- `regression/`: Automated suites run in CI to catch behavioral regressions.
- `reports/`: Exported evaluation runs, metrics, and trace artifacts.
