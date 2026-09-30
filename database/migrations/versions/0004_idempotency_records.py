"""0004 idempotency records

Revision ID: 0004_idempotency_records
Revises: 1605711be9a0
Create Date: 2026-09-30 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from database.base import GUID

# revision identifiers, used by Alembic.
revision: str = '0004_idempotency_records'
down_revision: Union[str, None] = '1605711be9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'idempotency_records',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('scope', sa.String(length=100), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('response_payload', sa.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope', 'idempotency_key', name='uq_idempotency_scope_key')
    )
    op.create_index(op.f('ix_idempotency_records_id'), 'idempotency_records', ['id'], unique=False)
    op.create_index(op.f('ix_idempotency_records_idempotency_key'), 'idempotency_records', ['idempotency_key'], unique=False)
    op.create_index(op.f('ix_idempotency_records_scope'), 'idempotency_records', ['scope'], unique=False)
    op.create_index(op.f('ix_idempotency_records_status'), 'idempotency_records', ['status'], unique=False)
    op.create_index('ix_idempotency_records_expires_at', 'idempotency_records', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_idempotency_records_expires_at', table_name='idempotency_records')
    op.drop_index(op.f('ix_idempotency_records_status'), table_name='idempotency_records')
    op.drop_index(op.f('ix_idempotency_records_scope'), table_name='idempotency_records')
    op.drop_index(op.f('ix_idempotency_records_idempotency_key'), table_name='idempotency_records')
    op.drop_index(op.f('ix_idempotency_records_id'), table_name='idempotency_records')
    op.drop_table('idempotency_records')
