"""add ntp values

Revision ID: 5665e5902905
Revises: d419cac01df2
Create Date: 2026-04-17 12:43:23.711453

"""
from typing import Sequence, Union
import uuid
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5665e5902905'
down_revision: Union[str, None] = 'd419cac01df2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'castdb'

def upgrade() -> None:
    op.create_table(
        "ntp_metadata",
        sa.Column(
            "probe_uuid",
            sa.String(),
            sa.ForeignKey(f"{SCHEMA}.probe_metadata.uuid"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("mode", sa.Text(), nullable=True),
        sa.Column(
            "reference",
            sa.Boolean(),
            nullable=True,
            comment="Is used as a reference for other probes",
        ),
        sa.Column("target_host", sa.Text(), nullable=True),
        sa.Column("target_port", sa.Integer(), nullable=True),
        sa.Column("sync_status", sa.Text(), nullable=True),
        sa.Column("leap_status", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("observation_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("collection_id", sa.Text(), nullable=True),
        sa.Column("collection_ip", sa.Text(), nullable=True),
        sa.Column("timeout", sa.Float(), nullable=True),
        sa.Column("additional_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=SCHEMA,
        if_not_exists=True,
        comment="NTP Clock Probe specific metadata"
    )

    metric_type_table = sa.table('metric_type',
                                 sa.column('uuid', sa.String),
                                 sa.column('name', sa.String),
                                 sa.column('description', sa.Text),
                                 sa.column('unit', sa.String),
                                 sa.column('value_type', sa.String),
                                 schema=SCHEMA
                                 )
    new_metrics = [
        dict(uuid=str(uuid.uuid4()),
             name="Delay",
             description=(
                 "Round-trip delay (RTD) or Round-Trip Time (RTT). The time in seconds it takes for a data signal to "
                 "travel from a source to a destination and back, including acknowledgement."
             ),
             unit="s",
             value_type='float',
             ),
        dict(uuid=str(uuid.uuid4()),
             name="Jitter",
             description=("Jitter or offset variation in delay in seconds. Represents inconsistent response times."),
             unit="s",
             value_type='float',
             ),
        dict(uuid=str(uuid.uuid4()),
             name="Stratum",
             description=(
                 'Stratum level. Hierarchical layer defining the distance (or "hops") between device and reference.'
             ),
             unit="level",
             value_type='int',
             ),
        dict(uuid=str(uuid.uuid4()),
             name="Reachability",
             description=(
                 "Reachability register (0-255) as a scalar for plotting. Ability of a source node to communicate "
                 "with a target node."
             ),
             unit="count",
             value_type='float',
             ),
        dict(uuid=str(uuid.uuid4()),
             name="Dispersion",
             description="Uncertainty in a clock's time relative to its reference source in seconds",
             unit="s",
             value_type='float',
             ),
        dict(uuid=str(uuid.uuid4()),
             name="NTP Root Delay",
             description=(
                 "Total round-trip network delay from the local system"
                 " all the way to the primary reference clock (stratum 0)"
             ),
             unit="s",
             value_type='float'
             ),
        dict(uuid=str(uuid.uuid4()),
             name="NTP Root Dispersion",
             description="The total accumulated clock uncertainty from the local system back to the primary reference clock",
             unit="s",
             value_type='float',
             ),
        dict(uuid=str(uuid.uuid4()),
             name="Poll Interval",
             description="Time between requests sent to a time server in seconds",
             unit="s",
             value_type='float',
             ),
        dict(uuid=str(uuid.uuid4()),
             name="Sync Health",
             description="1.0 if synchronized/healthy, 0.0 otherwise (probe-defined)",
             unit="ratio",
             value_type='float',
             )
    ]
    op.bulk_insert(metric_type_table, new_metrics)




def downgrade() -> None:
    op.drop_table('ntp_metadata', schema=SCHEMA, if_exists=True)
    metric_type = sa.sql.table(
        "metric_type",
        sa.column("name", sa.String),
        schema=SCHEMA,
    )

    op.execute(
        metric_type.delete().where(
            metric_type.c.name.in_(
                [
                    "Delay",
                    "Jitter",
                    "Stratum",
                    "Reachability",
                    "Dispersion",
                    "NTP Root Delay",
                    "NTP Root Dispersion",
                    "Poll Interval",
                    "Sync Health",
                ]
            )
        )
    )
