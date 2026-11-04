"""making microsemi table

Revision ID: c45e2dbdf900
Revises: c73212f2c0dd
Create Date: 2025-06-23 16:54:41.381184

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql

from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers, used by Alembic.
revision: str = 'c45e2dbdf900'
down_revision: Union[str, None] = 'c73212f2c0dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA='castdb'

def upgrade():
    op.create_table(
        'microchip_twst_metadata',
        sa.Column(
            'probe_uuid',
            sa.String(),
            sa.ForeignKey('castdb.probe_metadata.uuid', ondelete='CASCADE'),
            primary_key=True,
            comment='Foreign key to the associated probe'
        ),
        sa.Column(
            'additional_metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Additional metadata found in the file headers that did not match existing columns'
        ),
        comment='Microchip TWST Clock Probe specific metadata provided by probe text file exports.',
        schema='castdb',
        if_not_exists=True,
    )

    metric_type_table = sa.table('metric_type',
                                 sa.column('uuid', sa.String),
                                 sa.column('name', sa.String),
                                 sa.column('description', sa.Text),
                                 sa.column('unit', sa.String),
                                 sa.column('value_type', sa.String),
                                 schema=SCHEMA
                                 )

    # Generate UUIDs for metric types
    ebno_uuid = str(uuid.uuid4())

    op.bulk_insert(metric_type_table, [
        {
            'uuid': ebno_uuid,
            'name': 'Eb/No',
            'description': (
            "Energy per bit to noise power spectral density ratio measured at the clock probe. "
            "Indicates the quality of the received signal relative to noise."),
            'unit': 'dB',
            'value_type': 'float'
        }
    ])


def downgrade():
    op.drop_table('microsemi_twst_metadata', schema='castdb', if_exists=True)

    op.execute(sa.text("DELETE FROM castdb.metric_type WHERE name = 'Eb/No'"))

