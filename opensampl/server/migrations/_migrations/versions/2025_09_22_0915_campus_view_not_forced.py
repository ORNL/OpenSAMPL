"""campus view not forced

Revision ID: d419cac01df2
Revises: 2e2b5c419a9b
Create Date: 2025-09-22 09:15:53.973961

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd419cac01df2'
down_revision: Union[str, None] = '2e2b5c419a9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
CREATE OR REPLACE VIEW castdb.campus_locations AS
WITH ornl AS (
  SELECT l_1.uuid, l_1.name, l_1.geom, l_1.public
  FROM castdb.locations l_1
  WHERE l_1.name = 'Oak Ridge National Laboratory'
),
hvc AS (
  SELECT l_1.uuid, l_1.name, l_1.geom, l_1.public
  FROM castdb.locations l_1
  WHERE l_1.name = 'Hardin Valley Campus'
)
SELECT
  l.uuid,
  l.name,
  l.public,
  CASE
    WHEN l.name = hvc.name AND ornl.geom IS NOT NULL
      THEN ST_Y(ornl.geom::geometry)
    ELSE ST_Y(l.geom::geometry)
  END AS latitude,
  CASE
    WHEN l.name = hvc.name AND ornl.geom IS NOT NULL
      THEN ST_X(ornl.geom::geometry)
    ELSE ST_X(l.geom::geometry)
  END AS longitude,
  CASE
    WHEN l.name = hvc.name AND ornl.name IS NOT NULL
      THEN ornl.name
    ELSE l.name
  END AS campus,
  CASE
    WHEN l.name = hvc.name AND ornl.geom IS NOT NULL
      THEN ornl.geom
    ELSE l.geom
  END AS geom
FROM castdb.locations l
LEFT JOIN hvc  ON TRUE
LEFT JOIN ornl ON TRUE;    
""")


def downgrade() -> None:
    pass
