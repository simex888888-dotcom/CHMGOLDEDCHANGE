"""Initial migration

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("amount_from", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount_to", sa.Numeric(18, 2), nullable=False),
        sa.Column("base_rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("our_rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("commission", sa.Numeric(18, 2), nullable=False),
        sa.Column("requisites", sa.Text(), nullable=False),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "approved", "in_progress", "completed", "cancelled",
                name="orderstatus"
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("cxc_order_id", sa.String(255), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])

    op.create_table(
        "rate_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pair", sa.String(20), nullable=False),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pair"),
    )
    op.create_index("ix_rate_cache_pair", "rate_cache", ["pair"])


def downgrade() -> None:
    op.drop_index("ix_rate_cache_pair", table_name="rate_cache")
    op.drop_table("rate_cache")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")
    op.execute("DROP TYPE IF EXISTS orderstatus")
