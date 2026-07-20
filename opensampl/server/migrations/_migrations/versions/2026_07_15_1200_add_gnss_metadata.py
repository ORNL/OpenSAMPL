"""add GNSS probe metadata

Revision ID: a7d91f3e62c4
Revises: c95e49e551be
Create Date: 2026-07-15 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7d91f3e62c4"
down_revision: Union[str, None] = "c95e49e551be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "castdb"


def upgrade() -> None:
    op.create_table(
        "gnss_metadata",
        sa.Column(
            "probe_uuid",
            sa.String(),
            sa.ForeignKey(f"{SCHEMA}.probe_metadata.uuid", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("device", sa.Text()),
        sa.Column("driver", sa.Text()),
        sa.Column("fix_mode", sa.Integer()),
        sa.Column("satellites_visible", sa.Integer()),
        sa.Column("satellites_used", sa.Integer()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("altitude", sa.Float()),
        sa.Column("gpsd_host", sa.Text()),
        sa.Column("gpsd_port", sa.Integer()),
        sa.Column("additional_metadata", postgresql.JSONB(astext_type=sa.Text())),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("gnss_metadata", schema=SCHEMA)
