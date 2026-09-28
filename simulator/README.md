# OpsWingman — Business Simulator

The `simulator/` subsystem provides a deterministic business simulation engine operating on top of the PostgreSQL operational data layer. It executes controlled state transitions across **Orders**, **Payments**, and **Shipments** with strict domain validation.

---

## 1. Supported Operations

### Orders (`simulator/orders.py`)
- `create_order(...)`: Creates an order with items, calculates subtotal, tax (18% default), shipping, discount, and total. Starts in `PENDING` state.
- `get_order(...)`: Looks up order by UUID or `order_number`.
- `update_order_status(...)`: Validates and executes state transitions.
- `cancel_order(...)`: Cancels an active order before delivery/terminal state with an explicit cancellation reason.

### Payments (`simulator/payments.py`)
- `create_payment(...)`: Creates a payment record linked to an existing order in `INITIATED` status.
- `capture_payment(...)`: Transitions payment from `INITIATED`/`AUTHORIZED` to `SUCCESSFUL`, sets `paid_at`, and advances order to `CONFIRMED`.
- `fail_payment(...)`: Marks payment as `FAILED` with specific `error_code` and `error_message`.
- `get_payment(...)`: Looks up payment by UUID or `payment_reference`.

### Shipments (`simulator/shipments.py`)
- `create_shipment(...)`: Dispatches shipment with assigned carrier (Delhivery, BlueDart), generated tracking number, and advances order to `SHIPPED`.
- `update_shipment_status(...)`: Updates transit checkpoints (`IN_TRANSIT`, `OUT_FOR_DELIVERY`, etc.).
- `delay_shipment(...)`: Marks shipment as `DELAYED` with delay reason, location, and updated ETA.
- `deliver_shipment(...)`: Marks shipment as `DELIVERED`, records `actual_delivery_date`, and advances Order to `DELIVERED`.
- `get_shipment(...)`: Looks up shipment by UUID or `tracking_number`.

---

## 2. State Transition Rules

### Order Transitions
```
PENDING   ──► CONFIRMED ──► PROCESSING ──► SHIPPED ──► DELIVERED (Terminal)
   │               │            │             │
   └───────────────┴────────────┴─────────────┴───────► CANCELLED (Terminal)
   │
   └──► ON_HOLD ──► [Resumes to previous valid state]
```

### Payment Transitions
```
INITIATED ──► AUTHORIZED ──► SUCCESSFUL ──► REFUNDED (Terminal)
    │             │
    └──► FAILED   └──► FAILED (Terminal attempt)
```

### Shipment Transitions
```
MANIFESTED ──► IN_TRANSIT ──► OUT_FOR_DELIVERY ──► DELIVERED (Terminal)
    │              │                 │
    └──► DELAYED ──┴─────────────────┴───────────► RETURNED (Terminal)
```

---

## 3. Running Simulator Scenarios

Run the built-in scenario demonstration script:
```bash
python -m simulator.demo
```

Run programmatic simulation in Python:
```python
from simulator import BusinessSimulator

with BusinessSimulator() as sim:
    # Executes full lifecycle (Create -> Pay -> Ship -> Deliver)
    order, payment, shipment = sim.run_normal_order_flow(
        customer_id=customer.id,
        items=[{"sku": "SKU-AUDIO-01", "quantity": 1}],
        carrier="Delhivery"
    )
```

---

## 4. Running Simulator Tests

Run all unit and domain simulation tests:
```bash
pytest tests/unit/test_simulator.py -v
```
*(Tests both valid lifecycles and strictly rejected illegal state transitions).*
