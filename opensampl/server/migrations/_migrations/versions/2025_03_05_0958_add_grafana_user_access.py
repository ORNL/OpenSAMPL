"""add grafana user access

Revision ID: ba4a99e5f745
Revises: bd1322d0b00f
Create Date: 2025-03-05 09:58:44.110655

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba4a99e5f745'
down_revision: Union[str, None] = 'bd1322d0b00f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("GRANT ALL ON SCHEMA castdb TO grafana;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA castdb TO grafana;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA castdb GRANT SELECT ON TABLES TO grafana;")


def downgrade() -> None:
    pass
