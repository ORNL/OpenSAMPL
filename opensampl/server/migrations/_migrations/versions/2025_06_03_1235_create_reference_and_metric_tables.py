"""create reference and metric tables

Revision ID: d1546c1ecf9b
Revises: 07cf92bf4aa0
Create Date: 2025-06-03 12:35:20.987981

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid

from loguru import logger

# revision identifiers, used by Alembic.
revision: str = 'd1546c1ecf9b'
down_revision: Union[str, None] = '07cf92bf4aa0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'castdb'

def upgrade():
    """Create reference system tables and populate with initial data"""

    # Create reference_type table
    op.create_table('reference_type',
                    sa.Column('uuid', sa.String(length=36), nullable=False, primary_key=True,
                              comment="Auto generated primary key UUID for the reference type"),
                    sa.Column('name', sa.String(), nullable=False, unique=True,
                              comment="Unique name of the reference type (e.g., GPS, GNSS, Unknown)"),
                    sa.Column('description', sa.Text(), nullable=True,
                              comment="Optional human-readable description of the reference type"),
                    sa.Column('reference_table', sa.String(), nullable=True,
                              comment="Optional table name if the reference type is a compound type"),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Create metric_type table
    op.create_table('metric_type',
                    sa.Column('uuid', sa.String(length=36), nullable=False, primary_key=True,
                              comment="Auto generated primary key UUID for the metric type"),
                    sa.Column('name', sa.String(), nullable=True, unique=True,
                              comment="Unique name for the metric type (e.g., phase offset, delay, quality)"),
                    sa.Column('description', sa.Text(), nullable=True,
                              comment="Optional human-readable description of the metric"),
                    sa.Column('unit', sa.String(), nullable=False,
                              comment="Measurement unit (e.g., ns, s, ppm)"),
                    sa.Column('value_type', sa.String(), nullable=False, server_default='string',
                              comment="Data type of the value (e.g., float, int, string)"),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Create reference table
    op.create_table('reference',
                    sa.Column('uuid', sa.String(length=36), nullable=False, primary_key=True,
                              comment="Auto generated primary key UUID for the reference entry"),
                    sa.Column('reference_type_uuid', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.reference_type.uuid'),
                              comment="Foreign key to the reference type (e.g., GPS, GNSS, Probe)"),
                    sa.Column('compound_reference_uuid', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.probe_metadata.uuid'), nullable=True,
                              comment="Optional foreign key if the reference type is Compound. Which table it references is determined via reference_table field in reference_type table"),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Populate reference_type table with initial values
    reference_type_table = sa.table('reference_type',
                                    sa.column('uuid', sa.String),
                                    sa.column('name', sa.String),
                                    sa.column('description', sa.Text),
                                    sa.column('reference_table', sa.Text),
                                    schema=SCHEMA
                                    )

    # Generate UUIDs for reference types
    gps_ref_type_uuid = str(uuid.uuid4())
    gnss_ref_type_uuid = str(uuid.uuid4())
    probe_ref_type_uuid = str(uuid.uuid4())
    unknown_ref_type_uuid = str(uuid.uuid4())

    op.bulk_insert(reference_type_table, [
        {
            'uuid': gps_ref_type_uuid,
            'name': 'GPS',
            'description': 'Global Positioning System time reference'
        },
        {
            'uuid': gnss_ref_type_uuid,
            'name': 'GNSS',
            'description': 'Global Navigation Satellite System time reference'
        },
        {
            'uuid': probe_ref_type_uuid,
            'name': 'PROBE',
            'description': 'Another probe device used as time reference',
            'reference_table': 'probe_metadata'
        },
        {
            'uuid': unknown_ref_type_uuid,
            'name': 'UNKNOWN',
            'description': 'Unknown or unspecified reference type'
        }
    ])

    reference_table = sa.table('reference',
                               sa.column('uuid', sa.String),
                               sa.column('reference_type_uuid', sa.String),
                               sa.column('compound_reference_uuid', sa.String),
                               schema=SCHEMA
                               )

    unknown_ref_uuid = str(uuid.uuid4())

    op.bulk_insert(reference_table, [
        {
            'uuid': unknown_ref_uuid,
            'reference_type_uuid': unknown_ref_type_uuid,
            'reference_probe_uuid': None
        }
    ])

    # Populate metric_type table with initial values
    metric_type_table = sa.table('metric_type',
                                 sa.column('uuid', sa.String),
                                 sa.column('name', sa.String),
                                 sa.column('description', sa.Text),
                                 sa.column('unit', sa.String),
                                 sa.column('value_type', sa.String),
                                 schema=SCHEMA
                                 )

    # Generate UUIDs for metric types
    phase_offset_uuid = str(uuid.uuid4())
    unknown_metric_uuid = str(uuid.uuid4())

    op.bulk_insert(metric_type_table, [
        {
            'uuid': phase_offset_uuid,
            'name': 'Phase Offset',
            'description': 'Difference in seconds between the probe\'s time reading and the reference time reading',
            'unit': 's',
            'value_type': 'float'
        },
        {
            'uuid': unknown_metric_uuid,
            'name': 'UNKNOWN',
            'description': 'Unknown or unspecified metric type, with value_type of jsonb due to flexibility',
            'unit': 'unknown',
            'value_type': 'jsonb'
        }
    ])


def downgrade():
    """Drop reference system tables"""
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('reference', schema=SCHEMA, if_exists=True)
    op.drop_table('metric_type', schema=SCHEMA, if_exists=True)
    op.drop_table('reference_type', schema=SCHEMA, if_exists=True)