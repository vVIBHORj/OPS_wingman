"""
Deterministic Seed Data Generator for OpsWingman.

Generates reproducible ground truth entities supporting 6 core operational scenarios:
1. Normal Order: Paid, shipped, in-transit on schedule.
2. Delayed Order: Paid, shipped, delayed past ETA, open ticket attached.
3. Cancelled Order: Paid, cancelled before dispatch with cancellation reason.
4. Failed Payment: Order pending, payment transaction failed with error code.
5. Delivered Order: Completed full lifecycle with confirmed actual delivery.
6. Customer with Multiple Orders: Single customer profile with varied order histories.
"""

import logging
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Tuple

# Ensure repository root is on sys.path for direct execution: python database/seed.py
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy.orm import Session  # noqa: E402

from database.models import (  # noqa: E402
    ApprovalRecord,
    ApprovalStatus,
    AuditEventRecord,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Product,
    Shipment,
    ShipmentStatus,
    Ticket,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from database.session import SessionLocal  # noqa: E402

logger = logging.getLogger("opswingman.seed")


class SeedError(RuntimeError):
    """Base exception for seed errors."""

    pass


class SeedEnvironmentError(SeedError):
    """Raised when seeding is attempted in an unauthorized or production/staging environment."""

    pass


class SeedDatabaseTargetError(SeedError):
    """Raised when seeding is attempted on an unauthorized database host or database name."""

    pass


class SeedConfirmationError(SeedError):
    """Raised when enterprise synthetic seeding is attempted without explicit opt-in."""

    pass


FORBIDDEN_ENVIRONMENTS = {"production", "prod", "staging", "stage"}
AUTHORIZED_LOCAL_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "db",
    "postgres",
    "opswingman_db",
    "test",
    "dev",
    "local",
}


def validate_database_safety(session: Session) -> Dict[str, str]:
    """Validates that the target database and runtime environment are strictly authorized

    for seeding. Refuses execution on production, staging, or unknown remote hosts.
    Never exposes credentials or secrets in logs or exception messages.
    """
    # 1. Environment validation
    envs_to_check = set()
    for env_var in ("ENVIRONMENT", "ENV", "APP_ENV"):
        val = os.getenv(env_var)
        if val:
            envs_to_check.add(val.lower().strip())

    try:
        from backend.config import get_settings

        cfg_env = get_settings().environment.lower().strip()
        if cfg_env:
            envs_to_check.add(cfg_env)
    except Exception:
        pass

    for env_val in envs_to_check:
        for forbidden in FORBIDDEN_ENVIRONMENTS:
            if forbidden in env_val:
                raise SeedEnvironmentError(
                    f"Database seeding is strictly forbidden in '{env_val}' environment."
                )

    # 2. Database identity inspection
    bind = session.get_bind()
    if bind is None:
        raise SeedDatabaseTargetError("Session is not bound to a valid database engine.")

    url = bind.url
    driver = (url.drivername or "").lower()
    host = (url.host or "").lower()
    dbname = (url.database or "").lower()

    # Refuse production/staging database names
    for forbidden in FORBIDDEN_ENVIRONMENTS:
        if forbidden in dbname:
            raise SeedDatabaseTargetError(
                f"Database name '{dbname}' appears to be production or staging. Refusing seed."
            )

    # Refuse remote/cloud production host patterns
    forbidden_host_markers = [
        "prod",
        "production",
        "staging",
        "stage",
        "rds.amazonaws.com",
        "cloudsql",
        "azure",
        "elephantsql",
        "supabase.co",
    ]
    for marker in forbidden_host_markers:
        if marker in host:
            raise SeedDatabaseTargetError(
                f"Database host '{host}' indicates an unauthorized remote/production target. "
                "Refusing seed."
            )

    # For network-backed dialects (Postgres, MySQL), host must be in authorized local list
    if host and host not in AUTHORIZED_LOCAL_HOSTS:
        raise SeedDatabaseTargetError(
            f"Database host '{host}' is not in authorized local development/test allowlist. "
            "Refusing seed."
        )

    return {
        "driver": driver,
        "host": host or "local",
        "database": dbname or "memory",
    }


# Fixed Deterministic UUIDs for reference in tests and verification
CUSTOMER_ROHAN_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
CUSTOMER_PRIYA_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
CUSTOMER_AMIT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
CUSTOMER_ANANYA_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
CUSTOMER_VIKRAM_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")

PRODUCT_WIRELESS_EARBUDS_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PRODUCT_MECHANICAL_KEYBOARD_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
PRODUCT_COTTON_TSHIRT_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
PRODUCT_LEATHER_WALLET_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
PRODUCT_SMART_WATCH_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")

ORDER_NORMAL_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
ORDER_DELAYED_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
ORDER_CANCELLED_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")
ORDER_FAILED_PAYMENT_ID = uuid.UUID("00000000-0000-4000-8000-000000000004")
ORDER_DELIVERED_ID = uuid.UUID("00000000-0000-4000-8000-000000000005")
ORDER_MULTI_ROHAN_2_ID = uuid.UUID("00000000-0000-4000-8000-000000000006")


def create_seed_data(
    session: Session, auto_commit: bool = False
) -> Tuple[int, int, int, int, int, int]:
    """Populates the database with deterministic baseline seed data.

    Safe for repeated executions on empty or partial databases.
    Does not commit internally unless auto_commit=True.
    """
    validate_database_safety(session)
    now = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)

    # --------------------------------------------------------------------------
    # 1. Products (Catalog)
    # --------------------------------------------------------------------------
    products = [
        Product(
            id=PRODUCT_WIRELESS_EARBUDS_ID,
            sku="SKU-AUDIO-01",
            name="SonicBlast Wireless Earbuds Pro",
            description="Active noise cancelling wireless earbuds with 36hr battery life.",
            category="Electronics",
            unit_price=Decimal("2499.00"),
            currency="INR",
            inventory_count=150,
            is_active=True,
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=60),
        ),
        Product(
            id=PRODUCT_MECHANICAL_KEYBOARD_ID,
            sku="SKU-TECH-02",
            name="HyperKey RGB Mechanical Keyboard",
            description="Hot-swappable brown switch mechanical keyboard with per-key RGB.",
            category="Computer Accessories",
            unit_price=Decimal("4999.00"),
            currency="INR",
            inventory_count=75,
            is_active=True,
            created_at=now - timedelta(days=50),
            updated_at=now - timedelta(days=50),
        ),
        Product(
            id=PRODUCT_COTTON_TSHIRT_ID,
            sku="SKU-APPAREL-03",
            name="Premium Supima Cotton T-Shirt",
            description="100% organic Supima cotton classic crew-neck t-shirt.",
            category="Apparel",
            unit_price=Decimal("899.00"),
            currency="INR",
            inventory_count=300,
            is_active=True,
            created_at=now - timedelta(days=40),
            updated_at=now - timedelta(days=40),
        ),
        Product(
            id=PRODUCT_LEATHER_WALLET_ID,
            sku="SKU-ACCESSORY-04",
            name="Handcrafted Full Grain Leather Wallet",
            description="Slim bi-fold genuine leather wallet with RFID protection.",
            category="Accessories",
            unit_price=Decimal("1299.00"),
            currency="INR",
            inventory_count=120,
            is_active=True,
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
        ),
        Product(
            id=PRODUCT_SMART_WATCH_ID,
            sku="SKU-WEARABLE-05",
            name="PulseFit Smart Fitness Watch",
            description="AMOLED display, 24/7 heart rate monitor, SpO2 and GPS.",
            category="Wearables",
            unit_price=Decimal("3499.00"),
            currency="INR",
            inventory_count=90,
            is_active=True,
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=20),
        ),
    ]
    for p in products:
        exists = (
            session.get(Product, p.id) is not None
            or session.query(Product).filter(Product.sku == p.sku).first() is not None
        )
        if not exists:
            session.add(p)

    # --------------------------------------------------------------------------
    # 2. Customers
    # --------------------------------------------------------------------------
    customers = [
        Customer(
            id=CUSTOMER_ROHAN_ID,
            email="rohan.sharma@example.com",
            first_name="Rohan",
            last_name="Sharma",
            phone="+919876543210",
            company_name="Sharma Logistics",
            city="Bengaluru",
            state="Karnataka",
            pincode="560001",
            created_at=now - timedelta(days=90),
            updated_at=now - timedelta(days=90),
        ),
        Customer(
            id=CUSTOMER_PRIYA_ID,
            email="priya.patel@example.com",
            first_name="Priya",
            last_name="Patel",
            phone="+919812345678",
            company_name="Patel Traders",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001",
            created_at=now - timedelta(days=45),
            updated_at=now - timedelta(days=45),
        ),
        Customer(
            id=CUSTOMER_AMIT_ID,
            email="amit.verma@example.com",
            first_name="Amit",
            last_name="Verma",
            phone="+919701122334",
            company_name=None,
            city="Pune",
            state="Maharashtra",
            pincode="411001",
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
        ),
        Customer(
            id=CUSTOMER_ANANYA_ID,
            email="ananya.reddy@example.com",
            first_name="Ananya",
            last_name="Reddy",
            phone="+919848012345",
            company_name="Reddy Exports",
            city="Hyderabad",
            state="Telangana",
            pincode="500001",
            created_at=now - timedelta(days=25),
            updated_at=now - timedelta(days=25),
        ),
        Customer(
            id=CUSTOMER_VIKRAM_ID,
            email="vikram.singh@example.com",
            first_name="Vikram",
            last_name="Singh",
            phone="+919988776655",
            company_name="Singh & Sons",
            city="Jaipur",
            state="Rajasthan",
            pincode="302001",
            created_at=now - timedelta(days=15),
            updated_at=now - timedelta(days=15),
        ),
    ]
    for c in customers:
        exists = (
            session.get(Customer, c.id) is not None
            or session.query(Customer).filter(Customer.email == c.email).first() is not None
        )
        if not exists:
            session.add(c)

    # --------------------------------------------------------------------------
    # 3. Scenario 1: Normal Order (Customer: Priya Patel)
    # Status: SHIPPED, Paid via UPI, In-Transit on schedule
    # --------------------------------------------------------------------------
    order_normal = Order(
        id=ORDER_NORMAL_ID,
        order_number="ORD-2026-1001",
        customer_id=CUSTOMER_PRIYA_ID,
        status=OrderStatus.SHIPPED,
        currency="INR",
        subtotal_amount=Decimal("2499.00"),
        tax_amount=Decimal("449.82"),
        shipping_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("2948.82"),
        shipping_address_line1="12, Ashoka Park",
        shipping_address_line2="Navrangpura",
        shipping_city="Ahmedabad",
        shipping_state="Gujarat",
        shipping_pincode="380001",
        shipping_country="IN",
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=1),
    )
    order_normal.items.append(
        OrderItem(
            order_id=ORDER_NORMAL_ID,
            product_id=PRODUCT_WIRELESS_EARBUDS_ID,
            sku="SKU-AUDIO-01",
            product_name="SonicBlast Wireless Earbuds Pro",
            quantity=1,
            unit_price=Decimal("2499.00"),
            total_price=Decimal("2499.00"),
            created_at=now - timedelta(days=2),
        )
    )
    order_normal.payments.append(
        Payment(
            payment_reference="PAY-UPI-1001",
            order_id=ORDER_NORMAL_ID,
            amount=Decimal("2948.82"),
            currency="INR",
            payment_method=PaymentMethod.UPI,
            status=PaymentStatus.SUCCESSFUL,
            gateway_transaction_id="rzp_upi_test_90111",
            paid_at=now - timedelta(days=2),
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        )
    )
    order_normal.shipments.append(
        Shipment(
            shipment_number="SHP-DLV-1001",
            order_id=ORDER_NORMAL_ID,
            carrier="Delhivery",
            tracking_number="DEL123456789IN",
            status=ShipmentStatus.IN_TRANSIT,
            estimated_delivery_date=now + timedelta(days=2),
            current_location="Delhivery Hub Ahmedabad Central",
            shipped_at=now - timedelta(days=1),
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
    )
    order_normal.tickets.append(
        Ticket(
            ticket_number="TCK-2026-0004",
            customer_id=CUSTOMER_PRIYA_ID,
            order_id=ORDER_NORMAL_ID,
            title="Invoice download copy request for ORD-2026-1001",
            description=(
                "Could you please provide the GST tax invoice copy for my recent earbuds order?"
            ),
            channel=TicketChannel.EMAIL,
            status=TicketStatus.RESOLVED,
            priority=TicketPriority.LOW,
            category="GENERAL_INQUIRY",
            resolved_at=now - timedelta(days=1),
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=1),
        )
    )
    if not session.get(Order, ORDER_NORMAL_ID):
        session.add(order_normal)

    # --------------------------------------------------------------------------
    # 4. Scenario 2: Delayed Order (Customer: Amit Verma)
    # Status: SHIPPED, Paid via Card, Delayed past ETA, Open Support Ticket
    # --------------------------------------------------------------------------
    order_delayed = Order(
        id=ORDER_DELAYED_ID,
        order_number="ORD-2026-1002",
        customer_id=CUSTOMER_AMIT_ID,
        status=OrderStatus.SHIPPED,
        currency="INR",
        subtotal_amount=Decimal("4999.00"),
        tax_amount=Decimal("899.82"),
        shipping_amount=Decimal("100.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("5998.82"),
        shipping_address_line1="Flat 402, Greenfield Residency",
        shipping_address_line2="Kothrud",
        shipping_city="Pune",
        shipping_state="Maharashtra",
        shipping_pincode="411038",
        shipping_country="IN",
        created_at=now - timedelta(days=7),
        updated_at=now - timedelta(days=2),
    )
    order_delayed.items.append(
        OrderItem(
            order_id=ORDER_DELAYED_ID,
            product_id=PRODUCT_MECHANICAL_KEYBOARD_ID,
            sku="SKU-TECH-02",
            product_name="HyperKey RGB Mechanical Keyboard",
            quantity=1,
            unit_price=Decimal("4999.00"),
            total_price=Decimal("4999.00"),
            created_at=now - timedelta(days=7),
        )
    )
    order_delayed.payments.append(
        Payment(
            payment_reference="PAY-CRD-1002",
            order_id=ORDER_DELAYED_ID,
            amount=Decimal("5998.82"),
            currency="INR",
            payment_method=PaymentMethod.CARD,
            status=PaymentStatus.SUCCESSFUL,
            gateway_transaction_id="rzp_card_test_90222",
            paid_at=now - timedelta(days=7),
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(days=7),
        )
    )
    order_delayed.shipments.append(
        Shipment(
            shipment_number="SHP-BLU-1002",
            order_id=ORDER_DELAYED_ID,
            carrier="BlueDart",
            tracking_number="BLU987654321IN",
            status=ShipmentStatus.DELAYED,
            estimated_delivery_date=now - timedelta(days=3),  # ETA was 3 days ago
            current_location="BlueDart Regional Hub Hubli - Heavy Transit Congestion",
            delay_reason="Regional transit network disruption and weather advisory",
            shipped_at=now - timedelta(days=6),
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=1),
        )
    )
    order_delayed.tickets.append(
        Ticket(
            ticket_number="TCK-2026-0001",
            customer_id=CUSTOMER_AMIT_ID,
            order_id=ORDER_DELAYED_ID,
            title="Shipment ETA exceeded for order ORD-2026-1002",
            description=(
                "My keyboard was scheduled for delivery 3 days ago. BlueDart tracking shows no "
                "movement for 48 hours. Please update delivery ETA."
            ),
            channel=TicketChannel.EMAIL,
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            category="ORDER_DELAY",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
    )
    if not session.get(Order, ORDER_DELAYED_ID):
        session.add(order_delayed)

    # --------------------------------------------------------------------------
    # 5. Scenario 3: Cancelled Order (Customer: Ananya Reddy)
    # Status: CANCELLED, Paid via UPI, Cancellation Reason recorded
    # --------------------------------------------------------------------------
    order_cancelled = Order(
        id=ORDER_CANCELLED_ID,
        order_number="ORD-2026-1003",
        customer_id=CUSTOMER_ANANYA_ID,
        status=OrderStatus.CANCELLED,
        currency="INR",
        subtotal_amount=Decimal("1798.00"),
        tax_amount=Decimal("323.64"),
        shipping_amount=Decimal("50.00"),
        discount_amount=Decimal("100.00"),
        total_amount=Decimal("2071.64"),
        shipping_address_line1="Plot 88, Jubilee Hills",
        shipping_address_line2="Road No 36",
        shipping_city="Hyderabad",
        shipping_state="Telangana",
        shipping_pincode="500033",
        shipping_country="IN",
        cancellation_reason=(
            "Customer requested cancellation before dispatch due to change in delivery address."
        ),
        created_at=now - timedelta(days=4),
        updated_at=now - timedelta(days=3),
    )
    order_cancelled.items.append(
        OrderItem(
            order_id=ORDER_CANCELLED_ID,
            product_id=PRODUCT_COTTON_TSHIRT_ID,
            sku="SKU-APPAREL-03",
            product_name="Premium Supima Cotton T-Shirt",
            quantity=2,
            unit_price=Decimal("899.00"),
            total_price=Decimal("1798.00"),
            created_at=now - timedelta(days=4),
        )
    )
    order_cancelled.payments.append(
        Payment(
            payment_reference="PAY-UPI-1003",
            order_id=ORDER_CANCELLED_ID,
            amount=Decimal("2071.64"),
            currency="INR",
            payment_method=PaymentMethod.UPI,
            status=PaymentStatus.SUCCESSFUL,
            gateway_transaction_id="rzp_upi_test_90333",
            paid_at=now - timedelta(days=4),
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(days=4),
        )
    )
    order_cancelled.tickets.append(
        Ticket(
            ticket_number="TCK-2026-0002",
            customer_id=CUSTOMER_ANANYA_ID,
            order_id=ORDER_CANCELLED_ID,
            title="Cancellation confirmation request for ORD-2026-1003",
            description=(
                "I requested cancellation yesterday. Please verify that the order has been "
                "cancelled and initiate refund."
            ),
            channel=TicketChannel.WHATSAPP,
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.MEDIUM,
            category="CANCELLATION_REQUEST",
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=2),
        )
    )
    if not session.get(Order, ORDER_CANCELLED_ID):
        session.add(order_cancelled)

    # --------------------------------------------------------------------------
    # 6. Scenario 4: Failed Payment (Customer: Vikram Singh)
    # Status: PENDING, Payment status FAILED with error code
    # --------------------------------------------------------------------------
    order_failed_pay = Order(
        id=ORDER_FAILED_PAYMENT_ID,
        order_number="ORD-2026-1004",
        customer_id=CUSTOMER_VIKRAM_ID,
        status=OrderStatus.PENDING,
        currency="INR",
        subtotal_amount=Decimal("3499.00"),
        tax_amount=Decimal("629.82"),
        shipping_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("4128.82"),
        shipping_address_line1="77, Civil Lines",
        shipping_address_line2="Opposite Golf Club",
        shipping_city="Jaipur",
        shipping_state="Rajasthan",
        shipping_pincode="302006",
        shipping_country="IN",
        created_at=now - timedelta(hours=6),
        updated_at=now - timedelta(hours=6),
    )
    order_failed_pay.items.append(
        OrderItem(
            order_id=ORDER_FAILED_PAYMENT_ID,
            product_id=PRODUCT_SMART_WATCH_ID,
            sku="SKU-WEARABLE-05",
            product_name="PulseFit Smart Fitness Watch",
            quantity=1,
            unit_price=Decimal("3499.00"),
            total_price=Decimal("3499.00"),
            created_at=now - timedelta(hours=6),
        )
    )
    order_failed_pay.payments.append(
        Payment(
            payment_reference="PAY-NET-1004",
            order_id=ORDER_FAILED_PAYMENT_ID,
            amount=Decimal("4128.82"),
            currency="INR",
            payment_method=PaymentMethod.NETBANKING,
            status=PaymentStatus.FAILED,
            gateway_transaction_id="rzp_net_fail_90444",
            error_code="BAD_REQUEST_PAYMENT_TIMED_OUT",
            error_message="Customer bank gateway did not respond within timeout window.",
            paid_at=None,
            created_at=now - timedelta(hours=6),
            updated_at=now - timedelta(hours=6),
        )
    )
    order_failed_pay.tickets.append(
        Ticket(
            ticket_number="TCK-2026-0003",
            customer_id=CUSTOMER_VIKRAM_ID,
            order_id=ORDER_FAILED_PAYMENT_ID,
            title="Money debited from bank but order shows payment failed",
            description=(
                "Bank debited INR 4,128.82 from my HDFC account, but website says payment failed. "
                "Please check transaction reference PAY-NET-1004."
            ),
            channel=TicketChannel.PORTAL,
            status=TicketStatus.OPEN,
            priority=TicketPriority.URGENT,
            category="PAYMENT_FAILURE",
            created_at=now - timedelta(hours=5),
            updated_at=now - timedelta(hours=5),
        )
    )
    if not session.get(Order, ORDER_FAILED_PAYMENT_ID):
        session.add(order_failed_pay)

    # --------------------------------------------------------------------------
    # 7. Scenario 5: Delivered Order (Customer: Rohan Sharma - Order #1)
    # Status: DELIVERED, Completed full lifecycle
    # --------------------------------------------------------------------------
    order_delivered = Order(
        id=ORDER_DELIVERED_ID,
        order_number="ORD-2026-1005",
        customer_id=CUSTOMER_ROHAN_ID,
        status=OrderStatus.DELIVERED,
        currency="INR",
        subtotal_amount=Decimal("1299.00"),
        tax_amount=Decimal("233.82"),
        shipping_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("1532.82"),
        shipping_address_line1="Tower 3, Apt 1102, Prestige Palms",
        shipping_address_line2="Whitefield",
        shipping_city="Bengaluru",
        shipping_state="Karnataka",
        shipping_pincode="560066",
        shipping_country="IN",
        created_at=now - timedelta(days=14),
        updated_at=now - timedelta(days=9),
    )
    order_delivered.items.append(
        OrderItem(
            order_id=ORDER_DELIVERED_ID,
            product_id=PRODUCT_LEATHER_WALLET_ID,
            sku="SKU-ACCESSORY-04",
            product_name="Handcrafted Full Grain Leather Wallet",
            quantity=1,
            unit_price=Decimal("1299.00"),
            total_price=Decimal("1299.00"),
            created_at=now - timedelta(days=14),
        )
    )
    order_delivered.payments.append(
        Payment(
            payment_reference="PAY-UPI-1005",
            order_id=ORDER_DELIVERED_ID,
            amount=Decimal("1532.82"),
            currency="INR",
            payment_method=PaymentMethod.UPI,
            status=PaymentStatus.SUCCESSFUL,
            gateway_transaction_id="rzp_upi_test_90555",
            paid_at=now - timedelta(days=14),
            created_at=now - timedelta(days=14),
            updated_at=now - timedelta(days=14),
        )
    )
    order_delivered.shipments.append(
        Shipment(
            shipment_number="SHP-DLV-1005",
            order_id=ORDER_DELIVERED_ID,
            carrier="Delhivery",
            tracking_number="DEL998877665IN",
            status=ShipmentStatus.DELIVERED,
            estimated_delivery_date=now - timedelta(days=10),
            actual_delivery_date=now - timedelta(days=9),
            current_location="Delivered to recipient - Signed by Rohan Sharma",
            shipped_at=now - timedelta(days=13),
            created_at=now - timedelta(days=13),
            updated_at=now - timedelta(days=9),
        )
    )
    if not session.get(Order, ORDER_DELIVERED_ID):
        session.add(order_delivered)

    # --------------------------------------------------------------------------
    # 8. Scenario 6: Customer with Multiple Orders (Customer: Rohan Sharma - Order #2)
    # Status: PROCESSING, Paid via Card, shows multi-order customer history
    # --------------------------------------------------------------------------
    order_rohan_2 = Order(
        id=ORDER_MULTI_ROHAN_2_ID,
        order_number="ORD-2026-1006",
        customer_id=CUSTOMER_ROHAN_ID,
        status=OrderStatus.PROCESSING,
        currency="INR",
        subtotal_amount=Decimal("3398.00"),
        tax_amount=Decimal("611.64"),
        shipping_amount=Decimal("0.00"),
        discount_amount=Decimal("200.00"),
        total_amount=Decimal("3809.64"),
        shipping_address_line1="Tower 3, Apt 1102, Prestige Palms",
        shipping_address_line2="Whitefield",
        shipping_city="Bengaluru",
        shipping_state="Karnataka",
        shipping_pincode="560066",
        shipping_country="IN",
        created_at=now - timedelta(hours=12),
        updated_at=now - timedelta(hours=10),
    )
    order_rohan_2.items.append(
        OrderItem(
            order_id=ORDER_MULTI_ROHAN_2_ID,
            product_id=PRODUCT_WIRELESS_EARBUDS_ID,
            sku="SKU-AUDIO-01",
            product_name="SonicBlast Wireless Earbuds Pro",
            quantity=1,
            unit_price=Decimal("2499.00"),
            total_price=Decimal("2499.00"),
            created_at=now - timedelta(hours=12),
        )
    )
    order_rohan_2.items.append(
        OrderItem(
            order_id=ORDER_MULTI_ROHAN_2_ID,
            product_id=PRODUCT_COTTON_TSHIRT_ID,
            sku="SKU-APPAREL-03",
            product_name="Premium Supima Cotton T-Shirt",
            quantity=1,
            unit_price=Decimal("899.00"),
            total_price=Decimal("899.00"),
            created_at=now - timedelta(hours=12),
        )
    )
    order_rohan_2.payments.append(
        Payment(
            payment_reference="PAY-CRD-1006",
            order_id=ORDER_MULTI_ROHAN_2_ID,
            amount=Decimal("3809.64"),
            currency="INR",
            payment_method=PaymentMethod.CARD,
            status=PaymentStatus.SUCCESSFUL,
            gateway_transaction_id="rzp_crd_test_90666",
            paid_at=now - timedelta(hours=12),
            created_at=now - timedelta(hours=12),
            updated_at=now - timedelta(hours=12),
        )
    )
    if not session.get(Order, ORDER_MULTI_ROHAN_2_ID):
        session.add(order_rohan_2)

    session.flush()
    if auto_commit:
        session.commit()
    return len(customers), len(products), 6, 7, 6, 4


INDIAN_CITIES = [
    ("Bengaluru", "Karnataka", "560001"),
    ("Mumbai", "Maharashtra", "400001"),
    ("Delhi", "Delhi", "110001"),
    ("Hyderabad", "Telangana", "500001"),
    ("Chennai", "Tamil Nadu", "600001"),
    ("Pune", "Maharashtra", "411001"),
    ("Kolkata", "West Bengal", "700001"),
    ("Ahmedabad", "Gujarat", "380001"),
    ("Jaipur", "Rajasthan", "302001"),
    ("Gurugram", "Haryana", "122001"),
    ("Noida", "Uttar Pradesh", "201301"),
    ("Chandigarh", "Punjab", "160017"),
    ("Kochi", "Kerala", "682001"),
    ("Indore", "Madhya Pradesh", "452001"),
    ("Lucknow", "Uttar Pradesh", "226001"),
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Aayush", "Krishna",
    "Ishan", "Shaurya", "Dhruv", "Kabir", "Ritvik", "Darsh", "Ananya", "Diya", "Saanvi",
    "Aadhya", "Pari", "Myra", "Riya", "Anika", "Navya", "Kavya", "Avani", "Prisha",
    "Meera", "Sara", "Tanvi", "Pooja", "Sneha", "Neha", "Rahul", "Rohit", "Amit",
    "Vikas", "Suresh", "Deepa", "Swati", "Nikhil", "Gaurav", "Manish", "Kiran", "Divya",
    "Shreya", "Varun", "Alok", "Sameer", "Tanmay", "Siddharth", "Manav", "Kunal", "Harsh",
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Malhotra", "Bhatia", "Mehta", "Shah", "Patel", "Joshi",
    "Kulkarni", "Deshmukh", "Rao", "Reddy", "Nair", "Menon", "Pillai", "Iyer", "Iyengar",
    "Banerjee", "Chatterjee", "Mukherjee", "Ghosh", "Das", "Sen", "Singh", "Kaur",
    "Chauhan", "Rathore", "Yadav", "Mishra", "Pandey", "Trivedi", "Saxena", "Kapoor",
]

COMPANIES = [
    "Sharma Logistics", "Apex Retailers", "Zeta Solutions", "BlueSky Ventures",
    "Nexus Enterprises", "Zenith Logistics", "Vertex Innovations", "Solus Media",
    "Orion Traders", "Elevate Tech Labs", "CloudCraft Systems", "Metro Logistics",
]

PRODUCT_TEMPLATES = [
    ("SKU-AUDIO-06", "UltraBass Wireless Headset", "Electronics", Decimal("3999.00")),
    ("SKU-AUDIO-07", "NoiseShield Studio Headphones", "Electronics", Decimal("7499.00")),
    ("SKU-AUDIO-08", "PocketSound Bluetooth Mini Speaker", "Electronics", Decimal("1499.00")),
    ("SKU-AUDIO-09", "HiFi Soundbar 2.1 with Subwoofer", "Electronics", Decimal("8999.00")),
    ("SKU-AUDIO-10", "TrueWireless Gaming Earbuds", "Electronics", Decimal("2999.00")),
    ("SKU-ELEC-11", "FastCharge 65W GaN Wall Adapter", "Electronics", Decimal("1899.00")),
    ("SKU-ELEC-12", "PowerVault 20000mAh Power Bank", "Electronics", Decimal("2299.00")),
    ("SKU-ELEC-13", "MagSafe Wireless Charging Pad", "Electronics", Decimal("1699.00")),
    ("SKU-ELEC-14", "Rugged 1TB Portable External SSD", "Electronics", Decimal("7999.00")),
    ("SKU-ELEC-15", "Smart WiFi Plug with Energy Monitor", "Electronics", Decimal("899.00")),
    ("SKU-ELEC-16", "Dual-Band Mesh WiFi 6 Router", "Electronics", Decimal("5499.00")),
    ("SKU-ELEC-17", "Braided USB-C to Lightning Cable", "Electronics", Decimal("699.00")),
    ("SKU-ELEC-18", "4K Ultra-HD HDMI 2.1 Cable 2M", "Electronics", Decimal("799.00")),
    ("SKU-TECH-19", "Precision Wireless Laser Mouse", "Computer Accessories", Decimal("1799.00")),
    ("SKU-TECH-20", "Aluminum 7-in-1 USB-C Multi Hub", "Computer Accessories", Decimal("2899.00")),
    ("SKU-TECH-21", "Ergonomic Gas-Spring Monitor Arm", "Computer Accessories", Decimal("3499.00")),
    ("SKU-TECH-22", "1080p Full HD Pro Streaming Cam", "Computer Accessories", Decimal("4299.00")),
    ("SKU-TECH-23", "Studio Condenser USB Microphone", "Computer Accessories", Decimal("5499.00")),
    ("SKU-TECH-24", "RGB Extended Gaming Desk Mat", "Computer Accessories", Decimal("999.00")),
    ("SKU-TECH-25", "Mechanical Numpad Blue Switches", "Computer Accessories", Decimal("1599.00")),
    ("SKU-TECH-26", "Laptop Stand Dual Cooling Fans", "Computer Accessories", Decimal("1899.00")),
    ("SKU-TECH-27", "Vertical Ergonomic Optical Mouse", "Computer Accessories", Decimal("2199.00")),
    ("SKU-TECH-28", "Mechanical Keycap Set Custom PBT", "Computer Accessories", Decimal("1299.00")),
    ("SKU-TECH-29", "Magnetic Cable Management Clips", "Computer Accessories", Decimal("499.00")),
    ("SKU-TECH-30", "ScreenBar LED Desk Reading Lamp", "Computer Accessories", Decimal("3299.00")),
    ("SKU-APPAREL-31", "Classic Oxford Button-Down Shirt", "Apparel", Decimal("1899.00")),
    ("SKU-APPAREL-32", "Tailored Stretch Slim-Fit Chinos", "Apparel", Decimal("2199.00")),
    ("SKU-APPAREL-33", "All-Weather Packable Windbreaker", "Apparel", Decimal("2999.00")),
    ("SKU-APPAREL-34", "Heavyweight Fleece Pullover Hoodie", "Apparel", Decimal("2499.00")),
    ("SKU-APPAREL-35", "Pure Linen Casual Summer Shirt", "Apparel", Decimal("2299.00")),
    ("SKU-APPAREL-36", "Performance Athletic Joggers", "Apparel", Decimal("1499.00")),
    ("SKU-APPAREL-37", "Merino Wool Blend Knit Sweater", "Apparel", Decimal("3299.00")),
    ("SKU-APPAREL-38", "Classic Pique Polo T-Shirt Navy", "Apparel", Decimal("1199.00")),
    ("SKU-APPAREL-39", "Relaxed Fit Denim Jeans Indigo", "Apparel", Decimal("2799.00")),
    ("SKU-APPAREL-40", "Thermal Base Layer Crew-Neck Top", "Apparel", Decimal("1299.00")),
    ("SKU-APPAREL-41", "Seamless Moisture-Wicking Top", "Apparel", Decimal("899.00")),
    ("SKU-APPAREL-42", "High-Waist Performance Leggings", "Apparel", Decimal("1699.00")),
    ("SKU-FOOT-43", "Retro Low-Top Canvas Sneakers", "Footwear", Decimal("1999.00")),
    ("SKU-FOOT-44", "Cushioned Road Running Shoes", "Footwear", Decimal("4499.00")),
    ("SKU-FOOT-45", "Breathable Mesh Slip-On Loafers", "Footwear", Decimal("2499.00")),
    ("SKU-FOOT-46", "Waterproof Trail Hiking Shoes", "Footwear", Decimal("5999.00")),
    ("SKU-BAG-47", "Water-Resistant Commuter Backpack", "Bags & Luggage", Decimal("2799.00")),
    ("SKU-BAG-48", "Full-Grain Leather Weekend Duffel", "Bags & Luggage", Decimal("4999.00")),
    ("SKU-BAG-49", "Minimalist Padded Laptop Sleeve 14", "Bags & Luggage", Decimal("1199.00")),
    ("SKU-BAG-50", "Crossbody Anti-Theft Sling Bag", "Bags & Luggage", Decimal("1699.00")),
    ("SKU-BAG-51", "Hard-Shell Cabin Trolley Suitcase", "Bags & Luggage", Decimal("6499.00")),
    ("SKU-WEAR-52", "AuraFit Smart Health Ring", "Wearables", Decimal("9999.00")),
    ("SKU-WEAR-53", "GPS Multisport Fitness Tracker", "Wearables", Decimal("4999.00")),
    ("SKU-FIT-54", "High-Density Non-Slip Yoga Mat 6mm", "Fitness", Decimal("1299.00")),
    ("SKU-FIT-55", "Adjustable Quick-Select Dumbbell", "Fitness", Decimal("7999.00")),
    ("SKU-FIT-56", "Latex Resistance Bands Set of 5", "Fitness", Decimal("799.00")),
    ("SKU-FIT-57", "Deep Tissue Percussion Massager", "Fitness", Decimal("4499.00")),
    ("SKU-HOME-58", "Insulated Stainless Steel Bottle 1L", "Home & Living", Decimal("899.00")),
    ("SKU-HOME-59", "Minimalist Ceramic Mug Set (4-Pack)", "Home & Living", Decimal("1299.00")),
    ("SKU-HOME-60", "Smart LED Desk Lamp with Dimmer", "Home & Living", Decimal("2499.00")),
    ("SKU-HOME-61", "Ultrasonic Aromatherapy Diffuser", "Home & Living", Decimal("1799.00")),
    ("SKU-HOME-62", "French Press Coffee Maker 800ml", "Home & Living", Decimal("1499.00")),
    ("SKU-HOME-63", "Soy Wax Scented Candle Amber", "Home & Living", Decimal("699.00")),
    ("SKU-HOME-64", "Microfiber Queen Bed Sheet Set", "Home & Living", Decimal("1999.00")),
    ("SKU-HOME-65", "Ergonomic Memory Foam Cushion", "Home & Living", Decimal("1599.00")),
    ("SKU-HOME-66", "Bamboo Cutlery & Storage Organizer", "Home & Living", Decimal("1199.00")),
    ("SKU-HOME-67", "Double-Walled Borosilicate Glasses", "Home & Living", Decimal("899.00")),
    ("SKU-HOME-68", "Digital High-Precision Kitchen Scale", "Home & Living", Decimal("999.00")),
    ("SKU-HOME-69", "Compact Cordless Handheld Vacuum", "Home & Living", Decimal("3499.00")),
    ("SKU-HOME-70", "Natural Jute Indoor Plant Planter", "Home & Living", Decimal("599.00")),
    ("SKU-HOME-71", "Ceramic Pour-Over Coffee Dripper", "Home & Living", Decimal("799.00")),
    ("SKU-HOME-72", "Acoustic Felt Desk Divider Panel", "Home & Living", Decimal("1899.00")),
    ("SKU-HOME-73", "Magnetic Wall Knife Strip Metal", "Home & Living", Decimal("999.00")),
    ("SKU-HOME-74", "Cast Iron Pre-Seasoned Skillet 10in", "Home & Living", Decimal("2299.00")),
    ("SKU-HOME-75", "Electric Gooseneck Smart Kettle", "Home & Living", Decimal("3899.00")),
    ("SKU-HOME-76", "Non-Stick Ceramic Baking Sheet Set", "Home & Living", Decimal("1499.00")),
    ("SKU-HOME-77", "Air Purifier Filter HEPA H13 Grade", "Home & Living", Decimal("1799.00")),
    ("SKU-HOME-78", "Weighted Blanket 15lbs Cotton", "Home & Living", Decimal("4999.00")),
    ("SKU-HOME-79", "Electric Automatic Wine Opener", "Home & Living", Decimal("1299.00")),
    ("SKU-HOME-80", "Multi-Angle Tablet & iPad Stand", "Home & Living", Decimal("999.00")),
]

CARRIERS = ["Delhivery", "BlueDart", "DTDC", "Ekart Logistics", "Shadowfax", "FedEx India"]
DELAY_REASONS = [
    "Regional transit network disruption at Hubli Hub",
    "Adverse weather conditions along NH-48 interstate corridor",
    "Consignee address clarification requested by last-mile delivery agent",
    "Customs clearance inspection at airport cargo terminal",
    "Heavy monsoon localized waterlogging affecting dispatch route",
    "Logistics hub automated sorter maintenance delay",
    "Customer requested delivery date reschedule to subsequent weekend",
]

CANCELLATION_REASONS = [
    "Customer requested cancellation before warehouse packaging",
    "Found duplicate order placed through customer family account",
    "Found lower price during weekend promotional event",
    "Incorrect delivery pincode selected at checkout",
    "Delivery estimated timeframe too long for customer travel schedule",
    "Ordered incorrect size variant, customer will replace with new order",
]

TICKET_TEMPLATES = [
    ("Package not delivered past estimated date", "Delivery Delay", TicketPriority.HIGH),
    ("Tracking status stuck at hub for 48h", "Delivery Delay", TicketPriority.HIGH),
    ("Delivery marked but parcel not received", "Delivery Delay", TicketPriority.URGENT),
    ("Outer shipping cardboard box crushed and torn", "Damaged Product", TicketPriority.HIGH),
    ("Product seal broken upon delivery", "Damaged Product", TicketPriority.HIGH),
    ("Item missing cable from manufacturer box", "Product Query", TicketPriority.MEDIUM),
    ("Double deduction on UPI during checkout", "Payment Failure", TicketPriority.URGENT),
    ("Bank debited but order still showing PENDING", "Payment Failure", TicketPriority.URGENT),
    ("Refund for cancelled order not in bank", "Cancellation & Refund", TicketPriority.HIGH),
    ("Need urgent cancellation for high-value order", "Cancellation & Refund", TicketPriority.HIGH),
    ("Need revised tax invoice with company GSTIN", "Invoicing", TicketPriority.LOW),
    ("Update address to office in same pincode", "Address Change", TicketPriority.MEDIUM),
    ("Product size small, need replacement variant", "Return Request", TicketPriority.MEDIUM),
    ("Question regarding warranty coverage", "Product Query", TicketPriority.LOW),
    ("Delivery partner spoke unfamiliar dialect", "Delivery Service", TicketPriority.LOW),
]


def create_enterprise_seed_data(
    session: Session,
    confirm_enterprise: bool = False,
    auto_commit: bool = False,
) -> Dict[str, int]:
    """Generates a complete, deterministic, enterprise synthetic dataset.

    Targets: 150 Customers, 80 Products, 500 Orders, 1,000+ Items, 500 Payments,
    400+ Shipments, 120 Support Tickets, 50+ Approvals, 1,500+ Audit Events, 30 Docs.
    Guaranteed safe and idempotent across repeated and partial executions.
    Does not commit internally unless auto_commit=True.
    """
    validate_database_safety(session)

    opt_in_env = os.getenv("OPSWINGMAN_ALLOW_ENTERPRISE_SEED", "").lower() in ("true", "1", "yes")
    if not confirm_enterprise and not opt_in_env:
        raise SeedConfirmationError(
            "Enterprise synthetic seeding requires explicit opt-in confirmation. "
            "Pass confirm_enterprise=True or set OPSWINGMAN_ALLOW_ENTERPRISE_SEED=true."
        )

    from backend.rag.seed_knowledge import seed_default_knowledge

    rng = random.Random(42)
    now = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Base ground-truth scenarios (idempotent addition, no commit)
    create_seed_data(session, auto_commit=False)

    existing_customers = session.query(Customer).all()
    existing_products = session.query(Product).all()

    # 2. Add remaining customers to reach 150
    needed_customers = max(0, 150 - len(existing_customers))
    used_emails = {c.email for c in existing_customers}

    for i in range(needed_customers):
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        city_info = rng.choice(INDIAN_CITIES)
        email = f"{fn.lower()}.{ln.lower()}{i+10}@example.com"
        while email in used_emails:
            email = f"{fn.lower()}.{ln.lower()}{rng.randint(100, 9999)}@example.com"
        used_emails.add(email)

        has_company = rng.random() < 0.25
        company = rng.choice(COMPANIES) if has_company else None
        phone = f"+9198{rng.randint(10000000, 99999999)}"
        created_days_ago = rng.randint(5, 120)
        c_time = now - timedelta(days=created_days_ago)

        c = Customer(
            id=uuid.uuid4(),
            email=email,
            first_name=fn,
            last_name=ln,
            phone=phone,
            company_name=company,
            city=city_info[0],
            state=city_info[1],
            pincode=city_info[2],
            created_at=c_time,
            updated_at=c_time,
        )
        session.add(c)

    session.flush()
    all_customers = session.query(Customer).all()

    # 3. Add remaining products to reach 80
    needed_products = max(0, 80 - len(existing_products))
    existing_skus = {p.sku for p in existing_products}

    if needed_products > 0:
        for template in PRODUCT_TEMPLATES:
            if len(existing_skus) >= 80:
                break
            sku, name, cat, price = template
            if sku in existing_skus:
                continue
            p_time = now - timedelta(days=rng.randint(40, 150))
            p = Product(
                id=uuid.uuid4(),
                sku=sku,
                name=name,
                description=f"Enterprise {name.lower()} engineered for durability.",
                category=cat,
                unit_price=price,
                currency="INR",
                inventory_count=rng.randint(20, 350),
                is_active=True,
                created_at=p_time,
                updated_at=p_time,
            )
            session.add(p)
            existing_skus.add(sku)

    session.flush()
    all_products = session.query(Product).all()

    # 4. Generate orders to reach exactly 500
    current_order_count = session.query(Order).count()
    needed_orders = max(0, 500 - current_order_count)

    order_statuses = (
        [OrderStatus.DELIVERED] * 260
        + [OrderStatus.SHIPPED] * 75
        + [OrderStatus.PROCESSING] * 45
        + [OrderStatus.CONFIRMED] * 35
        + [OrderStatus.CANCELLED] * 40
        + [OrderStatus.ON_HOLD] * 20
        + [OrderStatus.PENDING] * 19
    )
    rng.shuffle(order_statuses)
    order_statuses = order_statuses[:needed_orders]

    new_shipments = []

    for i, target_status in enumerate(order_statuses):
        customer = rng.choice(all_customers)
        if i < 20:
            order_time = now - timedelta(hours=rng.randint(1, 23), minutes=rng.randint(1, 59))
        else:
            order_time = now - timedelta(days=rng.randint(1, 89), hours=rng.randint(0, 23))

        order_num = f"ORD-{order_time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        order_id = uuid.uuid4()

        item_count = rng.choices([1, 2, 3, 4], weights=[20, 45, 25, 10])[0]
        selected_products = rng.sample(all_products, item_count)

        subtotal = Decimal("0.00")
        items = []
        for prod in selected_products:
            qty = rng.choices([1, 2, 3], weights=[80, 15, 5])[0]
            item_total = prod.unit_price * qty
            subtotal += item_total
            items.append(
                OrderItem(
                    order_id=order_id,
                    product_id=prod.id,
                    sku=prod.sku,
                    product_name=prod.name,
                    quantity=qty,
                    unit_price=prod.unit_price,
                    total_price=item_total,
                    created_at=order_time,
                )
            )

        tax_amount = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
        shipping_amount = Decimal("0.00") if subtotal >= Decimal("999.00") else Decimal("99.00")
        discount_amount = Decimal("0.00")
        if subtotal > Decimal("3000.00") and rng.random() < 0.4:
            discount_amount = Decimal("250.00")
        elif subtotal > Decimal("1500.00") and rng.random() < 0.3:
            discount_amount = Decimal("100.00")

        total_amount = subtotal + tax_amount + shipping_amount - discount_amount
        cancellation_reason = (
            rng.choice(CANCELLATION_REASONS) if target_status == OrderStatus.CANCELLED else None
        )

        order = Order(
            id=order_id,
            order_number=order_num,
            customer_id=customer.id,
            status=target_status,
            currency="INR",
            subtotal_amount=subtotal,
            tax_amount=tax_amount,
            shipping_amount=shipping_amount,
            discount_amount=discount_amount,
            total_amount=total_amount,
            shipping_address_line1=f"Flat {rng.randint(101, 908)}, Tower {rng.randint(1, 12)}",
            shipping_address_line2=f"{customer.city} Heights",
            shipping_city=customer.city,
            shipping_state=customer.state,
            shipping_pincode=customer.pincode,
            shipping_country="IN",
            cancellation_reason=cancellation_reason,
            created_at=order_time,
            updated_at=order_time + timedelta(hours=rng.randint(1, 8)),
        )
        order.items = items
        session.add(order)

        # Payment for order
        pay_method = rng.choices(
            [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING, PaymentMethod.COD],
            weights=[55, 25, 15, 5],
        )[0]

        if target_status == OrderStatus.CANCELLED:
            pay_status = rng.choices(
                [PaymentStatus.REFUNDED, PaymentStatus.FAILED, PaymentStatus.INITIATED],
                weights=[65, 25, 10],
            )[0]
        elif target_status in (
            OrderStatus.DELIVERED,
            OrderStatus.SHIPPED,
            OrderStatus.PROCESSING,
            OrderStatus.CONFIRMED,
        ):
            pay_status = PaymentStatus.SUCCESSFUL
        elif target_status == OrderStatus.ON_HOLD:
            pay_status = rng.choices(
                [PaymentStatus.AUTHORIZED, PaymentStatus.SUCCESSFUL], weights=[60, 40]
            )[0]
        else:
            pay_status = rng.choices(
                [PaymentStatus.INITIATED, PaymentStatus.FAILED], weights=[50, 50]
            )[0]

        error_code = None
        error_msg = None
        if pay_status == PaymentStatus.FAILED:
            error_code = rng.choice(
                ["ERR_CARD_DECLINED", "ERR_UPI_TIMEOUT", "ERR_INSUFFICIENT_FUNDS", "ERR_NETBANKING"]
            )
            error_msg = f"Payment authorization failed via {pay_method.value}: {error_code}"

        pay_ref = (
            f"PAY-{pay_method.value[:3]}-{order_time.strftime('%m%d%H%M')}-"
            f"{uuid.uuid4().hex[:6].upper()}"
        )
        has_gateway_tx = pay_status in (
            PaymentStatus.SUCCESSFUL,
            PaymentStatus.REFUNDED,
            PaymentStatus.AUTHORIZED,
        )
        payment = Payment(
            id=uuid.uuid4(),
            payment_reference=pay_ref,
            order_id=order.id,
            amount=total_amount,
            currency="INR",
            payment_method=pay_method,
            status=pay_status,
            gateway_transaction_id=f"rzp_{uuid.uuid4().hex[:12]}" if has_gateway_tx else None,
            error_code=error_code,
            error_message=error_msg,
            paid_at=(
                order_time + timedelta(minutes=5)
                if pay_status in (PaymentStatus.SUCCESSFUL, PaymentStatus.REFUNDED)
                else None
            ),
            created_at=order_time,
            updated_at=order_time + timedelta(minutes=10),
        )
        session.add(payment)

        # Shipment for order
        if target_status in (
            OrderStatus.DELIVERED,
            OrderStatus.SHIPPED,
            OrderStatus.PROCESSING,
            OrderStatus.CONFIRMED,
        ):
            carrier = rng.choice(CARRIERS)
            trk = f"TRK-{carrier[:3].upper()}-{rng.randint(10000000, 99999999)}"
            shp_num = f"SHP-{order_time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            if target_status == OrderStatus.DELIVERED:
                s_status = ShipmentStatus.DELIVERED
                shipped_time = order_time + timedelta(days=1)
                delivered_time = shipped_time + timedelta(days=rng.randint(2, 4))
                delay_reason = None
            elif target_status == OrderStatus.SHIPPED:
                is_delayed = (
                    rng.random() < 0.45
                    and len([s for s in new_shipments if s.status == ShipmentStatus.DELAYED]) < 35
                )
                if is_delayed:
                    s_status = ShipmentStatus.DELAYED
                    shipped_time = order_time + timedelta(days=1)
                    delivered_time = None
                    delay_reason = rng.choice(DELAY_REASONS)
                else:
                    s_status = rng.choice(
                        [ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY]
                    )
                    shipped_time = order_time + timedelta(hours=rng.randint(12, 36))
                    delivered_time = None
                    delay_reason = None
            else:
                s_status = ShipmentStatus.MANIFESTED
                shipped_time = None
                delivered_time = None
                delay_reason = None

            shipment = Shipment(
                id=uuid.uuid4(),
                shipment_number=shp_num,
                order_id=order.id,
                carrier=carrier,
                tracking_number=trk,
                status=s_status,
                estimated_delivery_date=order_time + timedelta(days=rng.randint(3, 5)),
                actual_delivery_date=delivered_time,
                current_location=(
                    f"{customer.city} Hub"
                    if s_status != ShipmentStatus.MANIFESTED
                    else "Central Hub"
                ),
                delay_reason=delay_reason,
                shipped_at=shipped_time,
                created_at=order_time + timedelta(hours=6),
                updated_at=order_time + timedelta(hours=18),
            )
            session.add(shipment)
            new_shipments.append(shipment)

    session.flush()

    # 5. Payments backfill (for partial existing datasets where orders lack payments)
    current_payments = session.query(Payment).count()
    needed_payments = max(0, 500 - current_payments)
    if needed_payments > 0:
        unpaid_orders = (
            session.query(Order)
            .filter(~Order.payments.any())
            .limit(needed_payments)
            .all()
        )
        for u_order in unpaid_orders:
            pay_ref = (
                f"PAY-UPI-{u_order.created_at.strftime('%m%d%H%M')}-"
                f"{uuid.uuid4().hex[:6].upper()}"
            )
            payment = Payment(
                id=uuid.uuid4(),
                payment_reference=pay_ref,
                order_id=u_order.id,
                amount=u_order.total_amount,
                currency="INR",
                payment_method=PaymentMethod.UPI,
                status=PaymentStatus.SUCCESSFUL,
                gateway_transaction_id=f"rzp_{uuid.uuid4().hex[:12]}",
                paid_at=u_order.created_at + timedelta(minutes=5),
                created_at=u_order.created_at,
                updated_at=u_order.created_at + timedelta(minutes=10),
            )
            session.add(payment)
        session.flush()

    # 6. Shipments backfill (for partial existing datasets where eligible orders lack shipments)
    current_shipments = session.query(Shipment).count()
    needed_shipments = max(0, 400 - current_shipments)
    if needed_shipments > 0:
        eligible_orders = (
            session.query(Order)
            .filter(~Order.shipments.any())
            .filter(
                Order.status.in_([
                    OrderStatus.DELIVERED,
                    OrderStatus.SHIPPED,
                    OrderStatus.PROCESSING,
                    OrderStatus.CONFIRMED,
                ])
            )
            .limit(needed_shipments)
            .all()
        )
        for e_order in eligible_orders:
            carrier = rng.choice(CARRIERS)
            trk = f"TRK-{carrier[:3].upper()}-{rng.randint(10000000, 99999999)}"
            shp_num = f"SHP-{e_order.created_at.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            s_status = (
                ShipmentStatus.DELIVERED
                if e_order.status == OrderStatus.DELIVERED
                else ShipmentStatus.IN_TRANSIT
            )
            cust = e_order.customer or session.get(Customer, e_order.customer_id)
            shipment = Shipment(
                id=uuid.uuid4(),
                shipment_number=shp_num,
                order_id=e_order.id,
                carrier=carrier,
                tracking_number=trk,
                status=s_status,
                estimated_delivery_date=e_order.created_at + timedelta(days=4),
                actual_delivery_date=(
                    e_order.created_at + timedelta(days=3)
                    if s_status == ShipmentStatus.DELIVERED
                    else None
                ),
                current_location=f"{cust.city if cust else 'Central'} Hub",
                shipped_at=e_order.created_at + timedelta(days=1),
                created_at=e_order.created_at + timedelta(hours=6),
                updated_at=e_order.created_at + timedelta(hours=18),
            )
            session.add(shipment)
        session.flush()

    all_orders = session.query(Order).all()

    # 7. Support Tickets to reach 120
    current_tickets = session.query(Ticket).count()
    needed_tickets = max(0, 120 - current_tickets)

    if needed_tickets > 0 and all_orders:
        for _ in range(needed_tickets):
            t_template = rng.choice(TICKET_TEMPLATES)
            order = rng.choice(all_orders)
            customer = order.customer or session.get(Customer, order.customer_id)
            if not customer:
                if all_customers:
                    customer = rng.choice(all_customers)
                else:
                    customer = session.query(Customer).first()

            cust_id = customer.id if customer else order.customer_id
            cust_name = customer.first_name if customer else "Customer"

            t_time = order.created_at + timedelta(hours=rng.randint(2, 72))
            t_status = rng.choices(
                [
                    TicketStatus.OPEN,
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.WAITING_ON_CUSTOMER,
                    TicketStatus.RESOLVED,
                    TicketStatus.CLOSED,
                ],
                weights=[35, 30, 15, 15, 5],
            )[0]

            resolved_time = (
                t_time + timedelta(hours=rng.randint(4, 24))
                if t_status in (TicketStatus.RESOLVED, TicketStatus.CLOSED)
                else None
            )

            ticket = Ticket(
                id=uuid.uuid4(),
                ticket_number=f"TCK-{t_time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                customer_id=cust_id,
                order_id=order.id,
                title=f"{t_template[0]} (Ref: {order.order_number})",
                description=(
                    f"Customer {cust_name} reported: '{t_template[0]}' regarding "
                    f"order {order.order_number}. Needs operations review."
                ),
                channel=rng.choice(
                    [
                        TicketChannel.EMAIL,
                        TicketChannel.WHATSAPP,
                        TicketChannel.PORTAL,
                        TicketChannel.PHONE,
                    ]
                ),
                status=t_status,
                priority=t_template[2],
                category=t_template[1],
                resolved_at=resolved_time,
                created_at=t_time,
                updated_at=t_time + timedelta(hours=rng.randint(1, 12)),
            )
            session.add(ticket)

        session.flush()

    # 8. Approvals to reach 55+
    current_approvals = session.query(ApprovalRecord).count()
    needed_approvals = max(0, 55 - current_approvals)

    approval_actions = [
        ("cancel_order", "High-value order cancellation request requiring supervisor override"),
        ("process_refund", "Refund request exceeding automatic INR 2,000 threshold"),
        ("override_shipping_sla", "Manual freight upgrade request for delayed package"),
        ("manual_address_update", "Inter-city address modification during active transit"),
    ]

    if needed_approvals > 0 and all_orders:
        for _ in range(needed_approvals):
            order = rng.choice(all_orders)
            action_pair = rng.choice(approval_actions)
            req_time = now - timedelta(days=rng.randint(0, 14), hours=rng.randint(1, 23))

            appr_status = rng.choices(
                [
                    ApprovalStatus.PENDING,
                    ApprovalStatus.APPROVED,
                    ApprovalStatus.REJECTED,
                    ApprovalStatus.EXPIRED,
                ],
                weights=[40, 35, 20, 5],
            )[0]

            decided_time = (
                req_time + timedelta(hours=rng.randint(1, 8))
                if appr_status != ApprovalStatus.PENDING
                else None
            )
            approver = (
                "supervisor@opswingman.local"
                if appr_status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED)
                else None
            )
            rej_reason = (
                "Order is already in final transit; customer must initiate return upon delivery."
                if appr_status == ApprovalStatus.REJECTED
                else None
            )

            appr = ApprovalRecord(
                approval_id=f"APV-{req_time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                workflow_id=f"wf-{uuid.uuid4().hex[:12]}",
                action=action_pair[0],
                risk_level="HIGH" if rng.random() < 0.8 else "CRITICAL",
                target_entity_type="Order",
                target_entity_id=str(order.id),
                parameters={
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "amount": str(order.total_amount),
                },
                reason=action_pair[1],
                policy_id="POL-CAN-001" if action_pair[0] == "cancel_order" else "POL-REF-001",
                policy_version="1.0.0",
                policy_decision={
                    "allowed": False,
                    "requires_approval": True,
                    "risk_level": "HIGH",
                    "matched_rules": [
                        "High-value transaction threshold exceeded",
                        "Supervisor sign-off required",
                    ],
                },
                status=appr_status,
                requested_at=req_time,
                decided_at=decided_time,
                approver_id=approver,
                rejection_reason=rej_reason,
                citations=[
                    {
                        "document_id": "POL-CAN-001",
                        "title": "POL-CAN-001: Order Cancellation & Modification Policy",
                        "chunk_index": 0,
                        "text": (
                            "Cancellation of active orders with total value exceeding INR 5,000.00 "
                            "is classified as HIGH risk and requires human supervisor approval."
                        ),
                        "version": "1.0.0",
                        "similarity_score": 0.88,
                    }
                ],
                created_at=req_time,
                updated_at=decided_time or req_time,
            )
            session.add(appr)

        session.flush()

    # 9. Audit Events to reach 1,600+
    current_audit = session.query(AuditEventRecord).count()
    needed_audit = max(0, 1600 - current_audit)

    audit_event_types = [
        "REQUEST_RECEIVED",
        "POLICY_EVALUATED",
        "RISK_ASSESSED",
        "TOOL_EXECUTED",
        "APPROVAL_REQUESTED",
        "APPROVAL_RESOLVED",
        "ACTION_EXECUTED",
        "VERIFICATION_COMPLETED",
        "IDEMPOTENCY_HIT",
        "WORKFLOW_COMPLETED",
    ]

    if needed_audit > 0 and all_orders:
        for _ in range(needed_audit):
            order = rng.choice(all_orders)
            e_type = rng.choice(audit_event_types)
            e_time = order.created_at + timedelta(minutes=rng.randint(1, 360))
            run_id = f"run-{order.order_number.lower()}"

            tool_name = None
            if e_type in ("TOOL_EXECUTED", "ACTION_EXECUTED"):
                tool_name = rng.choice(
                    ["get_order", "get_shipment", "get_payment", "cancel_order", "process_refund"]
                )

            evt = AuditEventRecord(
                event_id=f"EVT-{e_time.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6].upper()}",
                run_id=run_id,
                timestamp=e_time,
                event_type=e_type,
                actor=rng.choice(["OpsAgent", "supervisor@opswingman.local", "system"]),
                workflow_state="COMPLETED" if rng.random() < 0.85 else "WAITING_FOR_APPROVAL",
                entity_type="Order",
                entity_id=str(order.id),
                operation=tool_name or e_type.lower(),
                tool_name=tool_name,
                tool_arguments=(
                    {"order_id": str(order.id), "order_number": order.order_number}
                    if tool_name
                    else None
                ),
                tool_result_summary=(
                    {"status": "SUCCESS", "verified": True} if tool_name else None
                ),
                policy_decision=(
                    {"allowed": True, "requires_approval": False}
                    if e_type == "POLICY_EVALUATED"
                    else None
                ),
                risk_assessment_summary=(
                    {"risk_score": 0.15, "risk_band": "LOW"}
                    if e_type == "RISK_ASSESSED"
                    else None
                ),
                verification_status="VERIFIED" if e_type == "VERIFICATION_COMPLETED" else None,
                success=True,
                metadata_provenance={
                    "is_synthetic": True,
                    "data_source": "SYNTHETIC_SEED",
                    "seed_scenario": "enterprise_baseline",
                },
                created_at=e_time,
                updated_at=e_time,
            )
            session.add(evt)

        session.flush()

    # 10. Seed knowledge documents idempotently (no commit)
    seed_default_knowledge(session, auto_commit=False)
    session.flush()

    if auto_commit:
        session.commit()

    return {
        "customers": session.query(Customer).count(),
        "products": session.query(Product).count(),
        "orders": session.query(Order).count(),
        "order_items": session.query(OrderItem).count(),
        "payments": session.query(Payment).count(),
        "shipments": session.query(Shipment).count(),
        "tickets": session.query(Ticket).count(),
        "approvals": session.query(ApprovalRecord).count(),
        "audit_events": session.query(AuditEventRecord).count(),
    }


def seed_database(
    enterprise: bool = True,
    confirm_enterprise: bool = False,
    force: bool = False,
) -> Dict[str, int]:
    """CLI / Execution entry point for database seeding."""
    with SessionLocal() as session:
        validate_database_safety(session)
        if enterprise:
            opt_in_env = (
                os.getenv("OPSWINGMAN_ALLOW_ENTERPRISE_SEED", "").lower() in ("true", "1", "yes")
            )
            if not confirm_enterprise and not opt_in_env:
                raise SeedConfirmationError(
                    "Enterprise synthetic seeding requires explicit opt-in confirmation. "
                    "Pass confirm_enterprise=True, use --confirm-enterprise-seed, "
                    "or set OPSWINGMAN_ALLOW_ENTERPRISE_SEED=true."
                )

            orders_cnt = session.query(Order).count()
            customers_cnt = session.query(Customer).count()
            products_cnt = session.query(Product).count()
            tickets_cnt = session.query(Ticket).count()
            approvals_cnt = session.query(ApprovalRecord).count()
            audit_cnt = session.query(AuditEventRecord).count()

            all_satisfied = (
                orders_cnt >= 500
                and customers_cnt >= 150
                and products_cnt >= 80
                and tickets_cnt >= 120
                and approvals_cnt >= 55
                and audit_cnt >= 1500
            )
            if all_satisfied and not force:
                logger.info("All enterprise seed target volumes already satisfied. Skipping seed.")
                print(
                    f"All enterprise seed target volumes already satisfied "
                    f"({orders_cnt} orders, {customers_cnt} customers, {products_cnt} products, "
                    f"{tickets_cnt} tickets, {approvals_cnt} approvals, {audit_cnt} audit events). "
                    "Skipping duplicate seed."
                )
                return {
                    "customers": customers_cnt,
                    "products": products_cnt,
                    "orders": orders_cnt,
                    "order_items": session.query(OrderItem).count(),
                    "payments": session.query(Payment).count(),
                    "shipments": session.query(Shipment).count(),
                    "tickets": tickets_cnt,
                    "approvals": approvals_cnt,
                    "audit_events": audit_cnt,
                }

            print("Seeding OpsWingman database with enterprise synthetic dataset...")
            try:
                stats = create_enterprise_seed_data(
                    session, confirm_enterprise=True, auto_commit=False
                )
                session.commit()
                print("Successfully seeded OpsWingman Enterprise Dataset:")
                for k, v in stats.items():
                    print(f"  - {k.replace('_', ' ').title()}: {v}")
                return stats
            except Exception:
                session.rollback()
                raise
        else:
            print("Seeding OpsWingman database with baseline 6 ground-truth scenarios...")
            try:
                counts = create_seed_data(session, auto_commit=False)
                session.commit()
                print("Successfully seeded baseline dataset:")
                print(f"  - Customers: {counts[0]}")
                print(f"  - Products: {counts[1]}")
                print(f"  - Orders: {counts[2]}")
                print(f"  - Order Items: {counts[3]}")
                print(f"  - Payments: {counts[4]}")
                print(f"  - Shipments: {counts[5]}")
                return {
                    "customers": counts[0],
                    "products": counts[1],
                    "orders": counts[2],
                    "order_items": counts[3],
                    "payments": counts[4],
                    "shipments": counts[5],
                }
            except Exception:
                session.rollback()
                raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Deterministic Database Seeder for OpsWingman"
    )
    parser.add_argument(
        "--confirm-enterprise-seed",
        action="store_true",
        default=False,
        help="Explicit confirmation required to seed enterprise dataset",
    )
    parser.add_argument(
        "--base-only",
        action="store_true",
        default=False,
        help="Seed only the baseline 6 operational scenarios",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force re-evaluation and seeding even if target volumes are satisfied",
    )
    args = parser.parse_args()

    try:
        seed_database(
            enterprise=not args.base_only,
            confirm_enterprise=args.confirm_enterprise_seed,
            force=args.force,
        )
    except SeedError as exc:
        print(f"Seed Aborted: {exc}", file=sys.stderr)
        sys.exit(1)
