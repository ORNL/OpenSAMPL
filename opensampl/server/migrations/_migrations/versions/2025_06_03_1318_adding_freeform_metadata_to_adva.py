"""adding freeform metadata to adva

Revision ID: 4b47485da562
Revises: 519588f63e5c
Create Date: 2025-06-03 13:18:34.256294

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from loguru import logger

# revision identifiers, used by Alembic.
revision: str = '4b47485da562'
down_revision: Union[str, None] = '519588f63e5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA='castdb'

def upgrade() -> None:
    op.add_column('adva_metadata',
        sa.Column('additional_metadata', sa.dialects.postgresql.JSONB(), nullable=True,
                 comment="Additional metadata found in the file headers that did not match existing columns"),
        schema=SCHEMA)


def downgrade() -> None:
    op.drop_column('adva_metadata', 'additional_metadata', schema=SCHEMA, if_exists=True)
