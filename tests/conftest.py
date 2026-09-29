"""Global pytest configuration and fixtures for OpsWingman.

Provides shared fixtures for database sessions, models, and application testing.
"""

import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure repository root is added to sys.path
REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Import all models to register with Base.metadata
from database.models import (
    ApprovalRecord,
    Base,
    Customer,
    DomainEvent,
    KnowledgeChunk,
    KnowledgeDocument,
    Order,
    OrderItem,
    Payment,
    Product,
    Shipment,
    Ticket,
)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """In-memory SQLite database session for unit tests with initial core seed."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Seed default customer and products for tests
    cust = Customer(
        id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        email="test.user@example.com",
        first_name="Aarav",
        last_name="Mehta",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        phone="+919876543210",
    )
    prod1 = Product(
        id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        sku="SKU-TEST-01",
        name="Smart Wireless Speaker",
        unit_price=Decimal("1999.00"),
        currency="INR",
        inventory_count=80,
        is_active=True,
    )
    prod2 = Product(
        id=uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        sku="SKU-TEST-02",
        name="Bluetooth Smart Tag",
        unit_price=Decimal("499.00"),
        currency="INR",
        inventory_count=200,
        is_active=True,
    )
    session.add_all([cust, prod1, prod2])
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()
