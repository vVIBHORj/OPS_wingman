"""0005 audit events

Revision ID: 0005_audit_events
Revises: 0004_idempotency_records
Create Date: 2026-10-05 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from database.base import GUID

# revision identifiers, used by Alembic.
revision: str = '0005_audit_events'
down_revision: Union[str, None] = '0004_idempotency_records'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_events',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('event_id', sa.String(length=100), nullable=False),
        sa.Column('run_id', sa.String(length=100), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('actor', sa.String(length=100), server_default='OpsAgent', nullable=False),
        sa.Column('workflow_state', sa.String(length=50), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.String(length=100), nullable=True),
        sa.Column('operation', sa.String(length=100), nullable=True),
        sa.Column('tool_name', sa.String(length=100), nullable=True),
        sa.Column('tool_arguments', sa.JSON(), nullable=True),
        sa.Column('tool_result_summary', sa.JSON(), nullable=True),
        sa.Column('policy_decision', sa.JSON(), nullable=True),
        sa.Column('risk_assessment_summary', sa.JSON(), nullable=True),
        sa.Column('verification_status', sa.String(length=50), nullable=True),
        sa.Column('approval_status', sa.String(length=50), nullable=True),
        sa.Column('retry_attempt', sa.Integer(), nullable=True),
        sa.Column('idempotency_info', sa.JSON(), nullable=True),
        sa.Column('success', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_provenance', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_events_id'), 'audit_events', ['id'], unique=False)
    op.create_index(op.f('ix_audit_events_event_id'), 'audit_events', ['event_id'], unique=True)
    op.create_index(op.f('ix_audit_events_run_id'), 'audit_events', ['run_id'], unique=False)
    op.create_index(op.f('ix_audit_events_event_type'), 'audit_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_audit_events_timestamp'), 'audit_events', ['timestamp'], unique=False)
    op.create_index('ix_audit_events_run_id_timestamp', 'audit_events', ['run_id', 'timestamp'], unique=False)
    op.create_index('ix_audit_events_type_timestamp', 'audit_events', ['event_type', 'timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_audit_events_type_timestamp', table_name='audit_events')
    op.drop_index('ix_audit_events_run_id_timestamp', table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_timestamp'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_event_type'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_run_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_event_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_id'), table_name='audit_events')
    op.drop_table('audit_events')
