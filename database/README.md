# Database Subsystem

This directory contains the operational data models, schema definitions, and migration scripts for OpsWingman.

## Structure
- `models/`: SQLAlchemy 2.0 declarative database models (operational tables, audit logs, vector indices).
- `migrations/`: Alembic schema migration versions and environment configurations.

## Extensions Required
- `vector`: PostgreSQL vector extension for similarity search and document embeddings (`pgvector`).
- `uuid-ossp`: For generating unique UUID identifiers.
