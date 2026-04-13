"""add column comments

Revision ID: 07cf92bf4aa0
Revises: 74df2bd60bb8
Create Date: 2025-06-03 12:23:43.611971

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from loguru import logger

# revision identifiers, used by Alembic.
revision: str = '07cf92bf4aa0'
down_revision: Union[str, None] = '74df2bd60bb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'castdb'

def upgrade():
    """Add comments to all existing columns"""

    # Add comments to locations table
    op.alter_column('locations', 'uuid',
                    comment="Auto generated primary key UUID for the location",
                    schema=SCHEMA)
    op.alter_column('locations', 'name',
                    comment="Unique name identifying the location",
                    schema=SCHEMA)
    op.alter_column('locations', 'geom',
                    comment="Geospatial point geometry (lat, lon, z)",
                    schema=SCHEMA)
    op.alter_column('locations', 'public',
                    comment="Whether this location is publicly visible",
                    schema=SCHEMA)

    # Add comments to test_metadata table
    op.alter_column('test_metadata', 'uuid',
                    comment="Auto generated primary key UUID for the test",
                    schema=SCHEMA)
    op.alter_column('test_metadata', 'name',
                    comment="Unique name of the test",
                    schema=SCHEMA)
    op.alter_column('test_metadata', 'start_date',
                    comment="Start timestamp of the test",
                    schema=SCHEMA)
    op.alter_column('test_metadata', 'end_date',
                    comment="End timestamp of the test",
                    schema=SCHEMA)

    # Add comments to probe_metadata table
    op.alter_column('probe_metadata', 'uuid',
                    comment="Auto generated primary key UUID for the probe metadata entry",
                    schema=SCHEMA)
    op.alter_column('probe_metadata', 'probe_id',
                    comment="Interface ID of the probe device; can be multiple probes from the same ip_address",
                    schema=SCHEMA)
    op.alter_column('probe_metadata', 'ip_address',
                    comment="IP address of the probe",
                    schema=SCHEMA)
    op.alter_column('probe_metadata', 'vendor',
                    comment="Manufacturer/vendor of the probe",
                    schema=SCHEMA)
    op.alter_column('probe_metadata', 'model',
                    comment="Model name/number of the probe",
                    schema=SCHEMA)
    op.alter_column('probe_metadata', 'name',
                    comment="Human-readable name for the probe",
                    schema=SCHEMA)
    op.alter_column('probe_metadata', 'public',
                    comment="Whether this probe is publicly visible",
                    schema=SCHEMA)
    op.alter_column('probe_metadata', 'location_uuid',
                    comment="Foreign key to the associated location",
                    schema=SCHEMA)
    op.alter_column('probe_metadata', 'test_uuid',
                    comment="Foreign key to the associated test",
                    schema=SCHEMA)

    # Add comments to probe_data table
    op.alter_column('probe_data', 'time',
                    comment="Timestamp of the measurement",
                    schema=SCHEMA)
    op.alter_column('probe_data', 'probe_uuid',
                    comment="Foreign key to the probe that collected the data",
                    schema=SCHEMA)

    # Add comments to adva_metadata table
    op.alter_column('adva_metadata', 'probe_uuid',
                    comment="Foreign key to the associated probe",
                    schema=SCHEMA)
    op.alter_column('adva_metadata', 'type',
                    comment="ADVA measurement type (eg Phase)",
                    schema=SCHEMA)
    op.alter_column('adva_metadata', 'start',
                    comment="Start time for the current measurement series",
                    schema=SCHEMA)
    op.alter_column('adva_metadata', 'frequency',
                    comment="Sampling frequency of the ADVA probe, in rate per second",
                    schema=SCHEMA)
    op.alter_column('adva_metadata', 'timemultiplier',
                    comment="Time multiplier used by the ADVA tool",
                    schema=SCHEMA)
    op.alter_column('adva_metadata', 'multiplier',
                    comment="Data scaling multiplier",
                    schema=SCHEMA)


def downgrade():
    """Remove comments from all columns"""
    # Remove comments from locations table
    op.alter_column('locations', 'uuid', comment=None, schema=SCHEMA)
    op.alter_column('locations', 'name', comment=None, schema=SCHEMA)
    op.alter_column('locations', 'geom', comment=None, schema=SCHEMA)
    op.alter_column('locations', 'public', comment=None, schema=SCHEMA)

    # Remove comments from test_metadata table
    op.alter_column('test_metadata', 'uuid', comment=None, schema=SCHEMA)
    op.alter_column('test_metadata', 'name', comment=None, schema=SCHEMA)
    op.alter_column('test_metadata', 'start_date', comment=None, schema=SCHEMA)
    op.alter_column('test_metadata', 'end_date', comment=None, schema=SCHEMA)

    # Remove comments from probe_metadata table
    op.alter_column('probe_metadata', 'uuid', comment=None, schema=SCHEMA)
    op.alter_column('probe_metadata', 'probe_id', comment=None, schema=SCHEMA)
    op.alter_column('probe_metadata', 'ip_address', comment=None, schema=SCHEMA)
    op.alter_column('probe_metadata', 'vendor', comment=None, schema=SCHEMA)
    op.alter_column('probe_metadata', 'model', comment=None, schema=SCHEMA)
    op.alter_column('probe_metadata', 'name', comment=None, schema=SCHEMA)
    op.alter_column('probe_metadata', 'public', comment=None, schema=SCHEMA)
    op.alter_column('probe_metadata', 'location_uuid', comment=None, schema=SCHEMA)
    op.alter_column('probe_metadata', 'test_uuid', comment=None, schema=SCHEMA)

    # Remove comments from probe_data table
    op.alter_column('probe_data', 'time', comment=None, schema=SCHEMA)
    op.alter_column('probe_data', 'probe_uuid', comment=None, schema=SCHEMA)

    # Remove comments from adva_metadata table
    op.alter_column('adva_metadata', 'probe_uuid', comment=None, schema=SCHEMA)
    op.alter_column('adva_metadata', 'type', comment=None, schema=SCHEMA)
    op.alter_column('adva_metadata', 'start', comment=None, schema=SCHEMA)
    op.alter_column('adva_metadata', 'frequency', comment=None, schema=SCHEMA)
    op.alter_column('adva_metadata', 'timemultiplier', comment=None, schema=SCHEMA)
    op.alter_column('adva_metadata', 'multiplier', comment=None, schema=SCHEMA)