"""add updated_at to order items

Revision ID: 1605711be9a0
Revises: 0003_rag_and_approvals
Create Date: 2026-09-29 07:59:26.212374+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1605711be9a0'
down_revision: Union[str, None] = '0003_rag_and_approvals'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # order_items.updated_at was already defined in 0001_initial_business_schema.
    # To maintain idempotent migrations on both fresh and pre-existing databases,
    # inspect the table columns and only add updated_at if not already present.
    context = op.get_context()
    if getattr(context, "as_sql", False):
        op.execute(
            "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS updated_at "
            "TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL"
        )
        return

    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table('order_items'):
        columns = [c['name'] for c in insp.get_columns('order_items')]
        if 'updated_at' not in columns:
            op.add_column(
                'order_items',
                sa.Column(
                    'updated_at',
                    sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    nullable=False,
                ),
            )


def downgrade() -> None:
    # order_items.updated_at is part of the 0001_initial_business_schema baseline.
    # Dropping it here would corrupt the schema baseline established by 0001.
    pass
