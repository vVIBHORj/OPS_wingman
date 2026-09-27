# Async Workers Subsystem

The workers subsystem executes background tasks, event queue consumption, and periodic sync operations.

## Architecture
- Consumes tasks from Valkey queues.
- Executes background state checkpoints, notification dispatches, and async verification routines.
