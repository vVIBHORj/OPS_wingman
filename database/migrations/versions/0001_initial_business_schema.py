"""0001 Initial business schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-27 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from database.base import GUID

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Customers Table
    op.create_table(
        'customers',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('company_name', sa.String(length=150), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('pincode', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_id'), 'customers', ['id'], unique=False)
    op.create_index(op.f('ix_customers_email'), 'customers', ['email'], unique=True)
    op.create_index(op.f('ix_customers_phone'), 'customers', ['phone'], unique=False)
    op.create_index('ix_customers_name', 'customers', ['first_name', 'last_name'], unique=False)

    # 2. Products Table
    op.create_table(
        'products',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('inventory_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_id'), 'products', ['id'], unique=False)
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=True)
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)
    op.create_index('ix_products_active_category', 'products', ['is_active', 'category'], unique=False)

    # 3. Orders Table
    op.create_table(
        'orders',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('order_number', sa.String(length=50), nullable=False),
        sa.Column('customer_id', GUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('subtotal_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('shipping_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('shipping_address_line1', sa.String(length=255), nullable=True),
        sa.Column('shipping_address_line2', sa.String(length=255), nullable=True),
        sa.Column('shipping_city', sa.String(length=100), nullable=True),
        sa.Column('shipping_state', sa.String(length=100), nullable=True),
        sa.Column('shipping_pincode', sa.String(length=20), nullable=True),
        sa.Column('shipping_country', sa.String(length=100), nullable=True, server_default='IN'),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_id'), 'orders', ['id'], unique=False)
    op.create_index(op.f('ix_orders_order_number'), 'orders', ['order_number'], unique=True)
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_index('ix_orders_customer_status', 'orders', ['customer_id', 'status'], unique=False)
    op.create_index('ix_orders_created_status', 'orders', ['created_at', 'status'], unique=False)

    # 4. Order Items Table
    op.create_table(
        'order_items',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('order_id', GUID(), nullable=False),
        sa.Column('product_id', GUID(), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=False),
        sa.Column('product_name', sa.String(length=200), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_id'), 'order_items', ['id'], unique=False)
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_index(op.f('ix_order_items_product_id'), 'order_items', ['product_id'], unique=False)

    # 5. Payments Table
    op.create_table(
        'payments',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('payment_reference', sa.String(length=100), nullable=False),
        sa.Column('order_id', GUID(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('payment_method', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('gateway_transaction_id', sa.String(length=100), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    op.create_index(op.f('ix_payments_payment_reference'), 'payments', ['payment_reference'], unique=True)
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    op.create_index(op.f('ix_payments_gateway_transaction_id'), 'payments', ['gateway_transaction_id'], unique=False)
    op.create_index('ix_payments_order_status', 'payments', ['order_id', 'status'], unique=False)

    # 6. Shipments Table
    op.create_table(
        'shipments',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('shipment_number', sa.String(length=50), nullable=False),
        sa.Column('order_id', GUID(), nullable=False),
        sa.Column('carrier', sa.String(length=100), nullable=False),
        sa.Column('tracking_number', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('estimated_delivery_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_delivery_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_location', sa.String(length=150), nullable=True),
        sa.Column('delay_reason', sa.Text(), nullable=True),
        sa.Column('shipped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shipments_id'), 'shipments', ['id'], unique=False)
    op.create_index(op.f('ix_shipments_shipment_number'), 'shipments', ['shipment_number'], unique=True)
    op.create_index(op.f('ix_shipments_order_id'), 'shipments', ['order_id'], unique=False)
    op.create_index(op.f('ix_shipments_tracking_number'), 'shipments', ['tracking_number'], unique=True)
    op.create_index(op.f('ix_shipments_status'), 'shipments', ['status'], unique=False)
    op.create_index('ix_shipments_order_status', 'shipments', ['order_id', 'status'], unique=False)
    op.create_index('ix_shipments_carrier_tracking', 'shipments', ['carrier', 'tracking_number'], unique=False)

    # 7. Tickets Table
    op.create_table(
        'tickets',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('ticket_number', sa.String(length=50), nullable=False),
        sa.Column('customer_id', GUID(), nullable=False),
        sa.Column('order_id', GUID(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tickets_id'), 'tickets', ['id'], unique=False)
    op.create_index(op.f('ix_tickets_ticket_number'), 'tickets', ['ticket_number'], unique=True)
    op.create_index(op.f('ix_tickets_customer_id'), 'tickets', ['customer_id'], unique=False)
    op.create_index(op.f('ix_tickets_order_id'), 'tickets', ['order_id'], unique=False)
    op.create_index(op.f('ix_tickets_status'), 'tickets', ['status'], unique=False)
    op.create_index(op.f('ix_tickets_priority'), 'tickets', ['priority'], unique=False)
    op.create_index(op.f('ix_tickets_category'), 'tickets', ['category'], unique=False)
    op.create_index('ix_tickets_customer_status', 'tickets', ['customer_id', 'status'], unique=False)
    op.create_index('ix_tickets_order_status', 'tickets', ['order_id', 'status'], unique=False)
    op.create_index('ix_tickets_created_status', 'tickets', ['created_at', 'status'], unique=False)


def downgrade() -> None:
    op.drop_table('tickets')
    op.drop_table('shipments')
    op.drop_table('payments')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('products')
    op.drop_table('customers')
