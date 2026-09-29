"""0003 rag and approvals

Revision ID: 0003_rag_and_approvals
Revises: 0002_domain_events
Create Date: 2026-09-29 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from database.base import GUID

# revision identifiers, used by Alembic.
revision: str = '0003_rag_and_approvals'
down_revision: Union[str, None] = '0002_domain_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Knowledge Documents Table
    op.create_table(
        'knowledge_documents',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('doc_metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_documents_id'), 'knowledge_documents', ['id'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_document_type'), 'knowledge_documents', ['document_type'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_status'), 'knowledge_documents', ['status'], unique=False)
    op.create_index('ix_knowledge_documents_source_version', 'knowledge_documents', ['source', 'version'], unique=False)

    # 2. Knowledge Chunks Table
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('document_id', GUID(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('document_version', sa.String(length=50), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('chunk_metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_chunks_id'), 'knowledge_chunks', ['id'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_document_id'), 'knowledge_chunks', ['document_id'], unique=False)
    op.create_index('ix_knowledge_chunks_doc_idx', 'knowledge_chunks', ['document_id', 'chunk_index'], unique=False)

    # 3. Approval Records Table
    op.create_table(
        'approval_records',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('approval_id', sa.String(length=100), nullable=False),
        sa.Column('run_id', sa.String(length=100), nullable=False),
        sa.Column('workflow_id', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('target_entity_type', sa.String(length=50), nullable=True),
        sa.Column('target_entity_id', sa.String(length=100), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('policy_id', sa.String(length=100), nullable=True),
        sa.Column('policy_version', sa.String(length=50), nullable=True),
        sa.Column('policy_decision', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approver_id', sa.String(length=100), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('citations', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_records_id'), 'approval_records', ['id'], unique=False)
    op.create_index(op.f('ix_approval_records_approval_id'), 'approval_records', ['approval_id'], unique=True)
    op.create_index(op.f('ix_approval_records_run_id'), 'approval_records', ['run_id'], unique=False)
    op.create_index(op.f('ix_approval_records_workflow_id'), 'approval_records', ['workflow_id'], unique=False)
    op.create_index(op.f('ix_approval_records_status'), 'approval_records', ['status'], unique=False)
    op.create_index('ix_approvals_status_requested', 'approval_records', ['status', 'requested_at'], unique=False)


def downgrade() -> None:
    op.drop_table('approval_records')
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_documents')
