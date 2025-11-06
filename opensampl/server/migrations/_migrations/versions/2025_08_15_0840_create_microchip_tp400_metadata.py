"""create microchip tp400 metadata

Revision ID: 2e2b5c419a9b
Revises: c45e2dbdf900
Create Date: 2025-08-15 08:40:34.520515

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2e2b5c419a9b'
down_revision: Union[str, None] = 'c45e2dbdf900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'microchip_tp4100_metadata',
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
        comment='Microchip TP4100 Clock Probe specific metadata provided by probe text file exports.',
        schema='castdb',
        if_not_exists=True,
    )

def downgrade() -> None:
    op.drop_table('microchip_tp4100_metadata', schema='castdb', if_exists=True)

