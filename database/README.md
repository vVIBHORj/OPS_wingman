# OpsWingman — Database Subsystem

The `database/` module provides the deterministic operational data layer and single source of ground truth for OpsWingman.

---

## 1. Domain Entities Overview

The core domain consists of 7 interconnected entities designed using SQLAlchemy 2.0 and mapped with strict types (UUID primary keys, UTC timestamps, fixed-precision `Numeric(12, 2)` monetary fields):

1. **`Customer` (`customers`)**:
   - Represents Indian SMB buyers and client organizations.
   - Primary attributes: `id` (UUID), `email` (unique index), `first_name`, `last_name`, `phone`, `company_name`, `city`, `state`, `pincode`.
   - Relationships: One-to-many with `Order` and `Ticket`.

2. **`Product` (`products`)**:
   - Merchant item catalog with SKU tracking and inventory counts.
   - Primary attributes: `id` (UUID), `sku` (unique index), `name`, `description`, `category`, `unit_price` (`Numeric(12, 2)`), `currency` (INR), `inventory_count`, `is_active`.
   - Relationships: One-to-many with `OrderItem`.

3. **`Order` (`orders`)**:
   - Central transaction record for customer purchases.
   - Primary attributes: `id` (UUID), `order_number` (unique index), `customer_id` (FK), `status` (`OrderStatus`), `subtotal_amount`, `tax_amount`, `shipping_amount`, `discount_amount`, `total_amount`, shipping address fields, `cancellation_reason`.
   - Status Enum: `PENDING`, `CONFIRMED`, `PROCESSING`, `SHIPPED`, `DELIVERED`, `CANCELLED`, `ON_HOLD`.
   - Relationships: Belongs to `Customer`; Has many `OrderItem`, `Payment`, `Shipment`, and `Ticket`.

4. **`OrderItem` (`order_items`)**:
   - Order line item capturing product snapshot at time of purchase.
   - Primary attributes: `id` (UUID), `order_id` (FK), `product_id` (FK), `sku`, `product_name`, `quantity`, `unit_price`, `total_price`.

5. **`Payment` (`payments`)**:
   - Financial transaction records and payment gateway reconciliation.
   - Primary attributes: `id` (UUID), `payment_reference` (unique index), `order_id` (FK), `amount`, `currency`, `payment_method` (`UPI`, `CARD`, `NETBANKING`, `COD`, `WALLET`), `status` (`INITIATED`, `AUTHORIZED`, `SUCCESSFUL`, `FAILED`, `REFUNDED`), `gateway_transaction_id`, `error_code`, `error_message`, `paid_at`.

6. **`Shipment` (`shipments`)**:
   - Logistics fulfillment, carrier tracking, and transit exception handling.
   - Primary attributes: `id` (UUID), `shipment_number` (unique index), `order_id` (FK), `carrier` (e.g., Delhivery, BlueDart), `tracking_number` (unique index), `status` (`MANIFESTED`, `IN_TRANSIT`, `OUT_FOR_DELIVERY`, `DELIVERED`, `DELAYED`, `FAILED_ATTEMPT`, `RETURNED`), `estimated_delivery_date`, `actual_delivery_date`, `current_location`, `delay_reason`, `shipped_at`.

7. **`Ticket` (`tickets`)**:
   - Inbound customer service tickets and operational exception requests.
   - Primary attributes: `id` (UUID), `ticket_number` (unique index), `customer_id` (FK), `order_id` (optional FK), `title`, `description`, `channel` (`EMAIL`, `WHATSAPP`, `PORTAL`, `PHONE`), `status` (`OPEN`, `IN_PROGRESS`, `WAITING_ON_CUSTOMER`, `RESOLVED`, `CLOSED`), `priority` (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), `category`, `resolved_at`.

---

## 2. Entity Relationship Diagram

```
   ┌──────────────┐                  ┌──────────────┐
   │   Customer   │                  │   Product    │
   └──────┬───────┘                  └──────┬───────┘
          │ 1                               │ 1
          │                                 │
          │ N                               │ N
   ┌──────▼───────┐                  ┌──────▼───────┐
   │    Order     ├─────────────────►│  OrderItem   │
   └──┬───┬───┬───┘ 1              N └──────────────┘
      │   │   │
      │ 1 │ 1 │ 1
      │   │   │
      │ N │ N │ N
   ┌──▼─┐ ┌▼───┐ ┌▼──────┐
   │Pay-│ │Ship-││Ticket │
   │ment│ │ment ││       │
   └────┘ └─────┘ └───────┘
```

---

## 3. Database Migrations (Alembic)

Migrations are managed via Alembic against the PostgreSQL operational instance.

### Run Migrations (Upgrade to Latest):
```bash
alembic upgrade head
```

### Create a New Migration:
```bash
alembic revision --autogenerate -m "description_of_change"
```

### Rollback Previous Migration:
```bash
alembic downgrade -1
```

---

## 4. Deterministic Seed Data

OpsWingman provides a reproducible seed dataset in `database/seed.py` that populates 6 realistic operational scenarios:

| # | Scenario | Customer | Order # | Key State |
|---|---|---|---|---|
| 1 | **Normal Order** | Priya Patel | `ORD-2026-1001` | Shipped via Delhivery, Paid via UPI, In-Transit on schedule |
| 2 | **Delayed Order** | Amit Verma | `ORD-2026-1002` | Shipped via BlueDart, Delayed past ETA, open support ticket `TCK-2026-0001` attached |
| 3 | **Cancelled Order** | Ananya Reddy | `ORD-2026-1003` | Cancelled before dispatch, cancellation reason recorded, ticket `TCK-2026-0002` |
| 4 | **Failed Payment** | Vikram Singh | `ORD-2026-1004` | Payment failed with gateway timeout code, urgent ticket `TCK-2026-0003` |
| 5 | **Delivered Order** | Rohan Sharma | `ORD-2026-1005` | Delivered on `2026-09-18` with signed delivery confirmation |
| 6 | **Customer History** | Rohan Sharma | `ORD-2026-1006` | Second active order (`PROCESSING`) demonstrating multiple order history |

### Run Seed Command:
```bash
python -m database.seed
```

---

## 5. Local Testing

Run the domain model and constraint test suite:
```bash
pytest tests/unit/test_domain_models.py
```
*(Runs against isolated in-memory engine with all foreign key checks, constraints, and scenario validations).*
