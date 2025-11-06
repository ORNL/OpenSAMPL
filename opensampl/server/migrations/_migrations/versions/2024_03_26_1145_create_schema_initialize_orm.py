"""create schema & initialize orm

Revision ID: fe18404ea614
Revises: 
Create Date: 2024-03-26 11:45:04.612673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = 'fe18404ea614'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'castdb'
def upgrade() -> None:
    # starting postgis
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Create our schema
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};")

    # Create locations table
    op.create_table('locations',
                    sa.Column('uuid', sa.String(36), primary_key=True),
                    sa.Column('name', sa.Text(), nullable=False, unique=True),
                    sa.Column('geom', geoalchemy2.Geometry(geometry_type='GEOMETRY', srid=4326)),
                    sa.Column('public', sa.Boolean(), nullable=True),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Create test_metadata table
    op.create_table('test_metadata',
                    sa.Column('uuid', sa.String(36), primary_key=True),
                    sa.Column('name', sa.Text(), unique=True, nullable=False),
                    sa.Column('start_date', sa.TIMESTAMP()),
                    sa.Column('end_date', sa.TIMESTAMP()),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Create probe_metadata table
    op.create_table('probe_metadata',
                    sa.Column('uuid', sa.String(36), primary_key=True),
                    sa.Column('probe_id', sa.Text()),
                    sa.Column('ip_address', sa.Text()),
                    sa.Column('vendor', sa.Text()),
                    sa.Column('model', sa.Text()),
                    sa.Column('name', sa.Text(), unique=True),
                    sa.Column('public', sa.Boolean(), nullable=True),
                    sa.Column('location_uuid', sa.String(36), sa.ForeignKey('castdb.locations.uuid')),
                    sa.Column('test_uuid', sa.String(36), sa.ForeignKey('castdb.test_metadata.uuid')),
                    sa.UniqueConstraint('probe_id', 'ip_address', name='uq_probe_metadata_ipaddress_probeid'),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Create probe_data table
    op.create_table('probe_data',
                    sa.Column('time', sa.TIMESTAMP(), primary_key=True),
                    sa.Column('probe_uuid', sa.String(36), sa.ForeignKey('castdb.probe_metadata.uuid'),
                              primary_key=True),
                    sa.Column('value', sa.NUMERIC()),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Create adva_metadata table
    op.create_table('adva_metadata',
                    sa.Column('probe_uuid', sa.String(36), sa.ForeignKey('castdb.probe_metadata.uuid'),
                              primary_key=True),
                    sa.Column('type', sa.Text()),
                    sa.Column('start', sa.TIMESTAMP()),
                    sa.Column('frequency', sa.Integer()),
                    sa.Column('timemultiplier', sa.Integer()),
                    sa.Column('multiplier', sa.Integer()),
                    sa.Column('title', sa.Text()),
                    sa.Column('adva_probe', sa.Text()),
                    sa.Column('adva_reference', sa.Text()),
                    sa.Column('adva_reference_expected_ql', sa.Text()),
                    sa.Column('adva_source', sa.Text()),
                    sa.Column('adva_direction', sa.Text()),
                    sa.Column('adva_version', sa.Float()),
                    sa.Column('adva_status', sa.Text()),
                    sa.Column('adva_mtie_mask', sa.Text()),
                    sa.Column('adva_mask_margin', sa.Integer()),
                    schema=SCHEMA,
                    if_not_exists=True
                    )


def downgrade() -> None:
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;")
