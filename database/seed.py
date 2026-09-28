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

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Tuple
from sqlalchemy.orm import Session
from database.base import Base
from database.session import SessionLocal, get_sync_engine
from database.models import (
    Customer,
    Product,
    Order,
    OrderItem,
    Payment,
    Shipment,
    Ticket,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    ShipmentStatus,
    TicketStatus,
    TicketPriority,
    TicketChannel,
)

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


def create_seed_data(session: Session) -> Tuple[int, int, int, int, int, int]:
    """Populates the database with deterministic seed data."""
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
    session.add_all(products)

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
    session.add_all(customers)

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
            description="Could you please provide the GST tax invoice copy for my recent earbuds order?",
            channel=TicketChannel.EMAIL,
            status=TicketStatus.RESOLVED,
            priority=TicketPriority.LOW,
            category="GENERAL_INQUIRY",
            resolved_at=now - timedelta(days=1),
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=1),
        )
    )
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
            description="My keyboard was scheduled for delivery 3 days ago. BlueDart tracking shows no movement for 48 hours. Please update delivery ETA.",
            channel=TicketChannel.EMAIL,
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            category="ORDER_DELAY",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
    )
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
        cancellation_reason="Customer requested cancellation before dispatch due to change in delivery address.",
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
            description="I requested cancellation yesterday. Please verify that the order has been cancelled and initiate refund.",
            channel=TicketChannel.WHATSAPP,
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.MEDIUM,
            category="CANCELLATION_REQUEST",
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=2),
        )
    )
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
            description="Bank debited INR 4,128.82 from my HDFC account, but website says payment failed. Please check transaction reference PAY-NET-1004.",
            channel=TicketChannel.PORTAL,
            status=TicketStatus.OPEN,
            priority=TicketPriority.URGENT,
            category="PAYMENT_FAILURE",
            created_at=now - timedelta(hours=5),
            updated_at=now - timedelta(hours=5),
        )
    )
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
    session.add(order_rohan_2)

    session.commit()
    return len(customers), len(products), 6, 7, 6, 4


def seed_database():
    """CLI / Execution entry point for database seeding."""
    print("Seeding OpsWingman database with deterministic ground-truth scenarios...")
    with SessionLocal() as session:
        # Check if already seeded to prevent duplication
        existing_orders = session.query(Order).count()
        if existing_orders > 0:
            print(f"Database already contains {existing_orders} orders. Skipping duplicate seed.")
            return

        c_count, p_count, o_count, oi_count, pay_count, s_count = create_seed_data(session)
        print(f"Successfully seeded database:")
        print(f"  - Customers: {c_count}")
        print(f"  - Products: {p_count}")
        print(f"  - Orders: {o_count} (6 Scenarios)")
        print(f"  - Order Items: {oi_count}")
        print(f"  - Payments: {pay_count}")
        print(f"  - Shipments: {s_count}")


if __name__ == "__main__":
    seed_database()
