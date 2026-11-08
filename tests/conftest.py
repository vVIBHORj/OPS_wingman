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
from sqlalchemy.pool import StaticPool

# Ensure repository root is added to sys.path
REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Import all models to register with Base.metadata
import database.models  # noqa: E402, F401
from database.models import Base, Customer, Product  # noqa: E402


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """In-memory SQLite database session for unit tests with initial core seed."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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


@pytest.fixture(scope="function")
def api_client(db_session: Session) -> Generator:
    """FastAPI TestClient with database dependency overridden by isolated db_session."""
    from fastapi.testclient import TestClient

    from backend.main import app
    from database.session import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def pytest_collection_modifyitems(config, items):
    """Automatically assigns directory-based markers (unit, integration, resilience,
    security, e2e) to test items based on file location.
    """
    for item in items:
        fspath_str = str(item.fspath)
        if "/unit" in fspath_str or "\\unit" in fspath_str:
            item.add_marker(pytest.mark.unit)
        elif "/integration" in fspath_str or "\\integration" in fspath_str:
            item.add_marker(pytest.mark.integration)
        elif "/resilience" in fspath_str or "\\resilience" in fspath_str:
            item.add_marker(pytest.mark.resilience)
        elif "/security" in fspath_str or "\\security" in fspath_str:
            item.add_marker(pytest.mark.security)
        elif "/e2e" in fspath_str or "\\e2e" in fspath_str:
            item.add_marker(pytest.mark.e2e)
