"""0002 domain events

Revision ID: 0002_domain_events
Revises: 0001_initial_schema
Create Date: 2026-09-27 18:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from database.base import GUID

# revision identifiers, used by Alembic.
revision: str = '0002_domain_events'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'domain_events',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', GUID(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('correlation_id', sa.String(length=100), nullable=True),
        sa.Column('causation_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_domain_events_id'), 'domain_events', ['id'], unique=False)
    op.create_index(op.f('ix_domain_events_event_type'), 'domain_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_domain_events_entity_type'), 'domain_events', ['entity_type'], unique=False)
    op.create_index(op.f('ix_domain_events_entity_id'), 'domain_events', ['entity_id'], unique=False)
    op.create_index(op.f('ix_domain_events_correlation_id'), 'domain_events', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_domain_events_causation_id'), 'domain_events', ['causation_id'], unique=False)
    op.create_index('ix_domain_events_entity', 'domain_events', ['entity_type', 'entity_id'], unique=False)
    op.create_index('ix_domain_events_type_occurred', 'domain_events', ['event_type', 'occurred_at'], unique=False)
    op.create_index('ix_domain_events_occurred_at', 'domain_events', ['occurred_at'], unique=False)


def downgrade() -> None:
    op.drop_table('domain_events')
