"""Seed script for OpsWingman Phase 3 Knowledge Base (RAG).

Ingests realistic policies, SOPs, and guidelines into the database.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.rag.seed_knowledge import seed_default_knowledge
from database.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Seeding knowledge base...")
    db = SessionLocal()
    try:
        count = seed_default_knowledge(db)
        logger.info("Successfully ingested/updated %d knowledge documents.", count)
    except Exception as e:
        logger.error("Failed to seed knowledge base: %s", e)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
