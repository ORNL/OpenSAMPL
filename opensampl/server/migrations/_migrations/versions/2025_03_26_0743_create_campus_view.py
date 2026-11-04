"""create campus view

Revision ID: e881512e7a10
Revises: ba4a99e5f745
Create Date: 2025-03-26 07:43:04.981724

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e881512e7a10'
down_revision: Union[str, None] = 'ba4a99e5f745'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

"""
This particular migration is not needed in our public version, just for the ORNL cast system
"""

def upgrade() -> None:
    op.execute("""
CREATE VIEW castdb.campus_locations AS
WITH ornl AS (
    SELECT * FROM castdb.locations l
    WHERE l.name = 'Oak Ridge National Laboratory'
),
     hvc AS (
         SELECT * FROM castdb.locations l
         WHERE l.name = 'Hardin Valley Campus'
     )
SELECT
    l.uuid,
    l.name,
    l.public,
    CASE
        WHEN l.name = hvc.name THEN ST_Y(ornl.geom :: geometry)
        ELSE ST_Y(l.geom :: geometry)
        END AS latitude,
    CASE
        WHEN l.name = hvc.name THEN ST_X(ornl.geom :: geometry)
        ELSE ST_X(l.geom :: geometry)
        END AS longitude,
    CASE
        WHEN l.name = hvc.name THEN ornl.name
        ELSE l.name
        END AS campus,
    CASE
        WHEN l.name = hvc.name THEN ornl.geom
        ELSE l.geom
        END AS geom
FROM castdb.locations l, hvc, ornl;
    """)
    op.execute('GRANT SELECT ON ALL TABLES IN SCHEMA castdb TO "grafana";')


def downgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS castdb.campus_locations CASCADE;"))
