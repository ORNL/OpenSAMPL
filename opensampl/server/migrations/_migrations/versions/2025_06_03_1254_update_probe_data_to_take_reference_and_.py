"""update probe data to take reference and metric

Revision ID: 519588f63e5c
Revises: d1546c1ecf9b
Create Date: 2025-06-03 12:54:47.183309

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from loguru import logger

# revision identifiers, used by Alembic.
revision: str = '519588f63e5c'
down_revision: Union[str, None] = 'd1546c1ecf9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'castdb'

time_buckets = [
    #suffix   interval    cron schedule (min hr * * *)
    ('1min', '1 minute', '*/5 * * * *'),     # Every 5 minutes
    ('5min', '5 minutes', '*/5 * * * *'),    # Every 5 minutes
    ('15min', '15 minutes', '*/15 * * * *'), # Every 15 minutes
    ('1hour', '1 hour', '0 * * * *'),        # Start of every hour
    ('6hour', '6 hours', '0 */6 * * *'),     # Every 6 hours
    ('1day', '1 day', '0 0 * * *')           # Midnight every day
]

def upgrade():
    """Update probe_data table structure"""
    # Add new columns to probe_data table
    op.add_column('probe_data',
        sa.Column('reference_uuid', sa.String(length=36), nullable=True,
                 comment="Foreign key to the reference point for the reading"),
        schema=SCHEMA, if_not_exists=True)

    op.add_column('probe_data',
        sa.Column('metric_type_uuid', sa.String(length=36), nullable=True,
                 comment="Foreign key to the metric type being measured"),
        schema=SCHEMA, if_not_exists=True)

    connection = op.get_bind()

    unknown_reference_uuid = connection.execute(
        sa.text("""
            SELECT r.uuid FROM castdb.reference r 
            JOIN castdb.reference_type rt ON r.reference_type_uuid = rt.uuid 
            WHERE lower(rt.name) = lower('UNKNOWN')
        """)
    ).scalar()

    phase_offset_metric_uuid = connection.execute(
        sa.text("SELECT uuid FROM castdb.metric_type WHERE lower(name) = lower('Phase Offset')")
    ).scalar()

    # Populate new columns with UNKNOWN reference and phase offset metric for existing records
    op.execute(
        sa.text("""
                UPDATE castdb.probe_data
                SET reference_uuid   = :ref_uuid,
                    metric_type_uuid = :metric_uuid
                WHERE reference_uuid IS NULL
                   OR metric_type_uuid IS NULL
                """).bindparams(ref_uuid=unknown_reference_uuid, metric_uuid=phase_offset_metric_uuid)
    )

    # Make the new columns non-nullable now that they have values
    op.alter_column('probe_data', 'reference_uuid', nullable=False, schema=SCHEMA)
    op.alter_column('probe_data', 'metric_type_uuid', nullable=False, schema=SCHEMA)

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_probe_data_reference_uuid', 'probe_data', 'reference',
        ['reference_uuid'], ['uuid'], source_schema=SCHEMA, referent_schema=SCHEMA
    )

    op.create_foreign_key(
        'fk_probe_data_metric_type_uuid', 'probe_data', 'metric_type',
        ['metric_type_uuid'], ['uuid'], source_schema=SCHEMA, referent_schema=SCHEMA
    )

    # Before we can change the type of "value" we need to drop the mat views
    for suffix, _, _ in time_buckets:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS castdb.avg_phase_err_{suffix} CASCADE;")
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS castdb.mtie_{suffix} CASCADE;")

    pk_name = connection.execute(
        sa.text("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_schema = :schema_name
                  AND table_name = 'probe_data'
                  AND constraint_type = 'PRIMARY KEY'
                """).bindparams(schema_name=SCHEMA)
    ).scalar()

    # Drop the old primary key constraint (whatever it's named)
    if pk_name:
        op.drop_constraint(pk_name, 'probe_data', type_='primary', schema=SCHEMA)

    # Create new primary key with all required columns
    op.create_primary_key(
        'probe_data_pkey', 'probe_data',
        ['time', 'probe_uuid', 'reference_uuid', 'metric_type_uuid'],
        schema=SCHEMA
    )

    # Change value column from NUMERIC to JSONB (containing numeric value)
    op.alter_column('probe_data', 'value',
        type_=sa.dialects.postgresql.JSONB(),
        postgresql_using='to_jsonb(value)',
        comment="Measurement value stored as JSON; value's expected type defined via metric",
        schema=SCHEMA)

def downgrade():
    """Revert probe_data table structure changes"""
    connection = op.get_bind()

    conflict_count = connection.execute(sa.text("""
                                                SELECT COUNT(*)
                                                FROM (SELECT TIME, probe_uuid
                                                      FROM castdb.probe_data
                                                      GROUP BY TIME, probe_uuid
                                                      HAVING COUNT (*) > 1) dupes
                                        """)).scalar()

    if conflict_count > 0:
        raise Exception("Unsafe downgrade: would violate original primary key due to duplicated time/probe_uuid")

    # Add back the old NUMERIC value column
    op.add_column('probe_data',
        sa.Column('value_old', sa.NUMERIC(), nullable=True),
        schema=SCHEMA)

    # Copy JSONB values back to NUMERIC (this will lose non-numeric data!)
    op.execute("""
        UPDATE castdb.probe_data 
        SET value_old = (value::text)::numeric
        WHERE value IS NOT NULL AND jsonb_typeof(value) = 'number'
    """)

    # Drop the JSONB value column
    op.drop_column('probe_data', 'value', schema=SCHEMA)

    # Rename the old column back to 'value'
    op.alter_column('probe_data', 'value_old', new_column_name='value', schema=SCHEMA)

    # Drop the new primary key
    op.drop_constraint('probe_data_pkey', 'probe_data', type_='primary', schema=SCHEMA)

    # Recreate the old primary key
    op.create_primary_key(
        'probe_data_pkey', 'probe_data',
        ['time', 'probe_uuid'],
        schema=SCHEMA
    )

    # Drop foreign key constraints
    op.drop_constraint('fk_probe_data_reference_uuid', 'probe_data', type_='foreignkey', schema=SCHEMA)
    op.drop_constraint('fk_probe_data_metric_type_uuid', 'probe_data', type_='foreignkey', schema=SCHEMA)

    # Drop the new columns
    op.drop_column('probe_data', 'reference_uuid', schema=SCHEMA)
    op.drop_column('probe_data', 'metric_type_uuid', schema=SCHEMA)