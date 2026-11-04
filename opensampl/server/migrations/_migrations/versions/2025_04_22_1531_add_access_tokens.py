"""add access tokens

Revision ID: 4435cf3ed8eb
Revises: 89ca5e16c662
Create Date: 2025-04-22 15:31:20.546256

"""
from typing import Sequence, Union
from datetime import datetime
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4435cf3ed8eb'
down_revision: Union[str, None] = '89ca5e16c662'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'api_access_keys',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key', sa.String(length=64), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        schema='access',
        if_not_exists=True,
    )

def downgrade():
    op.drop_table('api_access_keys', schema='access', if_exists=True)
