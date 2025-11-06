"""turn off matviews

Revision ID: 74df2bd60bb8
Revises: 4435cf3ed8eb
Create Date: 2025-04-22 16:50:04.899162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from loguru import logger

# revision identifiers, used by Alembic.
revision: str = '74df2bd60bb8'
down_revision: Union[str, None] = '4435cf3ed8eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def has_update():
    conn = op.get_bind()
    has_privilege = conn.execute(sa.text("""
            SELECT has_table_privilege(current_user, 'cron.job', 'UPDATE') AS has_update
        """)).scalar()
    return has_privilege

def upgrade() -> None:
    """
    It ends up being more than adequate to simply run the queries via grafana to generate time buckets. Their caching is good enough.
    """

    if not has_update():
        logger.warning("current user cannot update cron.job table to turn off.")
        return

    op.execute("UPDATE cron.job SET active = false;")


def downgrade() -> None:
    if not has_update():
        logger.warning("current user cannot update cron.job table to turn back on.")
        return

    op.execute("UPDATE cron.job SET active = true;")
