"""update retention policy

Revision ID: 89ca5e16c662
Revises: e881512e7a10
Create Date: 2025-04-14 12:31:26.335799

"""
from typing import Sequence, Union
import os
from alembic import op
import sqlalchemy as sa
import re

# revision identifiers, used by Alembic.
revision: str = '89ca5e16c662'
down_revision: Union[str, None] = 'e881512e7a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def sanitize_interval(value: str, fallback: str) -> str:
    """
    Validate that the input string is a safe Postgres INTERVAL.
    Fallback to a default if not valid.
    """
    # Very basic pattern: number + space + unit (e.g., '7 days', '1 hour', etc.)
    pattern = r"^\s*\d+\s+(second|minute|hour|day|week|month|year)s?\s*$"
    if re.match(pattern, value.strip(), re.IGNORECASE):
        return value.strip()
    return fallback

def upgrade() -> None:
    chunk_interval = sanitize_interval(os.getenv("CHUNK_INTERVAL", ""), "1 day")

    # set chunks interval (1 hour was too small). Can be configured in ENV
    op.execute(f"SELECT set_chunk_time_interval('castdb.probe_data', INTERVAL '{chunk_interval}');")




def downgrade():
    # Reset chunk interval to 1 hour
    op.execute("SELECT set_chunk_time_interval('castdb.probe_data', INTERVAL '1 hour');")

