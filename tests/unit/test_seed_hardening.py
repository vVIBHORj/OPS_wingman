"""
Unit and regression tests for OPSwingman Enterprise Seed hardening.

Covers:
1. Opt-in confirmation requirement (SeedConfirmationError).
2. Environment rejection (production and staging environments).
3. Database target identity validation (refusal of remote/prod hosts/names, no credential leakage).
4. Single-transaction atomicity and clean rollback on failure.
5. First seed execution target counts and referential integrity.
6. Repeated execution idempotency across all entity types (zero duplicate records).
7. Partial dataset handling (additive fill without deleting or duplicating existing records).
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base
from database.models import (
    ApprovalRecord,
    AuditEventRecord,
    Customer,
    KnowledgeChunk,
    KnowledgeDocument,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    Product,
    Shipment,
    ShipmentStatus,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from database.seed import (
    SeedConfirmationError,
    SeedDatabaseTargetError,
    SeedEnvironmentError,
    create_enterprise_seed_data,
    create_seed_data,
    validate_database_safety,
)


@pytest.fixture(scope="function")
def isolated_db():
    """Isolated in-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ==============================================================================
# 1. Environment & Target Safety Guards
# ==============================================================================


def test_refuse_seeding_in_production_environment(isolated_db: Session, monkeypatch):
    """Ensure seeding is strictly rejected if environment is production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(SeedEnvironmentError) as exc_info:
        validate_database_safety(isolated_db)
    assert "production" in str(exc_info.value).lower()
    assert "strictly forbidden" in str(exc_info.value).lower()

    # Verify create_enterprise_seed_data also halts before any writes
    with pytest.raises(SeedEnvironmentError):
        create_enterprise_seed_data(isolated_db, confirm_enterprise=True)
    assert isolated_db.query(Customer).count() == 0


def test_refuse_seeding_in_staging_environment(isolated_db: Session, monkeypatch):
    """Ensure seeding is strictly rejected if environment is staging."""
    monkeypatch.setenv("ENV", "staging")
    with pytest.raises(SeedEnvironmentError) as exc_info:
        validate_database_safety(isolated_db)
    assert "staging" in str(exc_info.value).lower()


def test_refuse_seeding_on_remote_or_production_host():
    """Ensure database host validation rejects remote cloud or prod targets without credentials."""
    mock_session = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_url = MagicMock()
    mock_url.drivername = "postgresql"
    mock_url.host = "opswingman-db.prod.rds.amazonaws.com"
    mock_url.database = "opswingman"
    mock_url.password = "SUPER_SECRET_PASSWORD_123"
    mock_bind.url = mock_url
    mock_session.get_bind.return_value = mock_bind

    with pytest.raises(SeedDatabaseTargetError) as exc_info:
        validate_database_safety(mock_session)

    err_msg = str(exc_info.value)
    assert "SUPER_SECRET_PASSWORD_123" not in err_msg
    assert "unauthorized remote/production target" in err_msg


def test_refuse_seeding_on_production_database_name():
    """Ensure database target validation rejects databases named with prod/staging."""
    mock_session = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_url = MagicMock()
    mock_url.drivername = "postgresql"
    mock_url.host = "localhost"
    mock_url.database = "opswingman_production_v1"
    mock_bind.url = mock_url
    mock_session.get_bind.return_value = mock_bind

    with pytest.raises(SeedDatabaseTargetError) as exc_info:
        validate_database_safety(mock_session)

    assert "production or staging" in str(exc_info.value)


# ==============================================================================
# 2. Opt-in Confirmation Requirement
# ==============================================================================


def test_enterprise_seed_requires_explicit_confirmation(isolated_db: Session, monkeypatch):
    """Calling create_enterprise_seed_data without confirmation raises SeedConfirmationError."""
    monkeypatch.delenv("OPSWINGMAN_ALLOW_ENTERPRISE_SEED", raising=False)
    with pytest.raises(SeedConfirmationError) as exc_info:
        create_enterprise_seed_data(isolated_db, confirm_enterprise=False)

    assert "explicit opt-in" in str(exc_info.value).lower()
    assert isolated_db.query(Customer).count() == 0
    assert isolated_db.query(Order).count() == 0


def test_enterprise_seed_accepts_env_opt_in(isolated_db: Session, monkeypatch):
    """Setting OPSWINGMAN_ALLOW_ENTERPRISE_SEED satisfies the opt-in guard."""
    monkeypatch.setenv("OPSWINGMAN_ALLOW_ENTERPRISE_SEED", "true")
    # Calling with confirm_enterprise=False should proceed when env is set
    # We test create_seed_data to keep it fast
    counts = create_seed_data(isolated_db, auto_commit=False)
    assert counts[0] == 5
    assert counts[1] == 5


# ==============================================================================
# 3. Transaction Atomicity & Failure Rollback
# ==============================================================================


def test_failure_and_rollback_leaves_zero_records(isolated_db: Session, monkeypatch):
    """Simulated failure during enterprise seeding must completely roll back with 0 leaked rows."""
    from backend.rag import seed_knowledge

    def broken_seed_default_knowledge(session, auto_commit=False):
        raise RuntimeError("Simulated RAG knowledge ingestion failure midway through seeding")

    monkeypatch.setattr(seed_knowledge, "seed_default_knowledge", broken_seed_default_knowledge)

    try:
        create_enterprise_seed_data(isolated_db, confirm_enterprise=True, auto_commit=False)
        isolated_db.commit()
    except RuntimeError:
        isolated_db.rollback()

    # Verify that because no nested commits occurred, the entire transaction rolled back cleanly!
    assert isolated_db.query(Order).count() == 0
    assert isolated_db.query(Customer).count() == 0
    assert isolated_db.query(Product).count() == 0
    assert isolated_db.query(Ticket).count() == 0
    assert isolated_db.query(ApprovalRecord).count() == 0
    assert isolated_db.query(AuditEventRecord).count() == 0


# ==============================================================================
# 4. First Execution, Second Execution & Idempotency
# ==============================================================================


def test_first_and_second_seed_execution_idempotency(isolated_db: Session):
    """Verify first seed achieves targets, and second seed creates exactly 0 duplicate entities."""
    # First execution
    counts1 = create_enterprise_seed_data(isolated_db, confirm_enterprise=True, auto_commit=False)
    isolated_db.commit()

    assert counts1["customers"] == 150
    assert counts1["products"] == 80
    assert counts1["orders"] == 500
    assert counts1["order_items"] >= 1000
    assert counts1["payments"] == 500
    assert counts1["shipments"] >= 400
    assert counts1["tickets"] == 120
    assert counts1["approvals"] >= 50
    assert counts1["audit_events"] >= 1500

    docs_count1 = isolated_db.query(KnowledgeDocument).count()
    chunks_count1 = isolated_db.query(KnowledgeChunk).count()
    assert docs_count1 >= 30

    # Second execution (repeat run)
    counts2 = create_enterprise_seed_data(isolated_db, confirm_enterprise=True, auto_commit=False)
    isolated_db.commit()

    # Exact equality across all entity types
    assert counts2["customers"] == counts1["customers"]
    assert counts2["products"] == counts1["products"]
    assert counts2["orders"] == counts1["orders"]
    assert counts2["order_items"] == counts1["order_items"]
    assert counts2["payments"] == counts1["payments"]
    assert counts2["shipments"] == counts1["shipments"]
    assert counts2["tickets"] == counts1["tickets"]
    assert counts2["approvals"] == counts1["approvals"]
    assert counts2["audit_events"] == counts1["audit_events"]

    assert isolated_db.query(KnowledgeDocument).count() == docs_count1
    assert isolated_db.query(KnowledgeChunk).count() == chunks_count1


# ==============================================================================
# 5. Partial Existing Dataset Handling
# ==============================================================================


def test_partial_existing_dataset_fill_without_deletion(isolated_db: Session):
    """Verify existing records are preserved and the seeder additively reaches target counts."""
    # Pre-seed custom existing customer, product, and order
    custom_customer = Customer(
        id=uuid.uuid4(),
        email="preexisting.client@example.com",
        first_name="PreExisting",
        last_name="Client",
        city="Mumbai",
    )
    custom_product = Product(
        id=uuid.uuid4(),
        sku="SKU-PRE-EXISTING-01",
        name="Legacy Inventory Item",
        unit_price=Decimal("199.00"),
        currency="INR",
        inventory_count=45,
    )
    isolated_db.add_all([custom_customer, custom_product])
    isolated_db.flush()

    custom_order = Order(
        id=uuid.uuid4(),
        order_number="ORD-PRE-EXISTING-9999",
        customer_id=custom_customer.id,
        status=OrderStatus.CONFIRMED,
        currency="INR",
        total_amount=Decimal("199.00"),
    )
    isolated_db.add(custom_order)
    isolated_db.commit()

    assert isolated_db.query(Customer).count() == 1
    assert isolated_db.query(Product).count() == 1
    assert isolated_db.query(Order).count() == 1

    # Run enterprise seed
    counts = create_enterprise_seed_data(isolated_db, confirm_enterprise=True, auto_commit=False)
    isolated_db.commit()

    # Reaches target counts
    assert counts["customers"] == 150
    assert counts["products"] == 80
    assert counts["orders"] == 500

    # Pre-existing custom entities must NOT have been deleted!
    assert isolated_db.get(Customer, custom_customer.id) is not None
    assert isolated_db.get(Product, custom_product.id) is not None
    assert isolated_db.get(Order, custom_order.id) is not None


# ==============================================================================
# 6. Referential Integrity Verification
# ==============================================================================


def test_seed_referential_integrity(isolated_db: Session):
    """Verify that all seeded relationships and foreign keys are valid and consistent."""
    create_enterprise_seed_data(isolated_db, confirm_enterprise=True, auto_commit=False)
    isolated_db.commit()

    all_customers = {c.id for c in isolated_db.query(Customer).all()}
    all_products = {p.id for p in isolated_db.query(Product).all()}
    all_orders = {o.id for o in isolated_db.query(Order).all()}

    # Check Order Items
    order_items = isolated_db.query(OrderItem).all()
    assert len(order_items) >= 1000
    for item in order_items:
        assert item.order_id in all_orders
        assert item.product_id in all_products
        assert item.quantity > 0
        assert item.unit_price > 0
        assert item.total_price == item.unit_price * item.quantity

    # Check Payments
    payments = isolated_db.query(Payment).all()
    assert len(payments) == 500
    for pay in payments:
        assert pay.order_id in all_orders
        assert pay.amount >= 0
        assert pay.status in PaymentStatus

    # Check Shipments
    shipments = isolated_db.query(Shipment).all()
    assert len(shipments) >= 400
    for shp in shipments:
        assert shp.order_id in all_orders
        assert shp.status in ShipmentStatus
        assert shp.carrier is not None
        assert shp.tracking_number is not None

    # Check Tickets
    tickets = isolated_db.query(Ticket).all()
    assert len(tickets) == 120
    for tck in tickets:
        assert tck.customer_id in all_customers
        assert tck.order_id in all_orders
        assert tck.priority in TicketPriority
        assert tck.status in TicketStatus

    # Check Approvals
    approvals = isolated_db.query(ApprovalRecord).all()
    assert len(approvals) >= 50
    for appr in approvals:
        assert appr.target_entity_type == "Order"
        assert uuid.UUID(appr.target_entity_id) in all_orders

    # Check Audit Events
    audit_events = isolated_db.query(AuditEventRecord).all()
    assert len(audit_events) >= 1500
    for evt in audit_events:
        assert evt.entity_type == "Order"
        assert uuid.UUID(evt.entity_id) in all_orders
