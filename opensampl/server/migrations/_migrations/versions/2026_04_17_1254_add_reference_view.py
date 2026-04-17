"""add reference view

Revision ID: c95e49e551be
Revises: 5665e5902905
Create Date: 2026-04-17 12:54:27.037125

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c95e49e551be'
down_revision: Union[str, None] = '5665e5902905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'castdb'

CREATE_VIEW_SQL = f"""
CREATE VIEW {SCHEMA}.reference_probe_metadata
AS WITH probe_references AS (
         SELECT r.uuid,
            r.reference_type_uuid,
            r.compound_reference_uuid
           FROM {SCHEMA}.reference r
             JOIN {SCHEMA}.reference_type rt ON r.reference_type_uuid::text = rt.uuid::text
          WHERE rt.name::text = 'PROBE'::text
        )
 SELECT pm.uuid,
    pm.probe_id,
    pm.ip_address,
    pm.vendor,
    pm.model,
    pm.name,
    pm.public,
    pm.location_uuid,
    pm.test_uuid,
    pr.uuid AS reference_uuid
   FROM probe_references pr
     JOIN {SCHEMA}.probe_metadata pm ON pr.compound_reference_uuid::text = pm.uuid::text;
"""

DROP_VIEW_SQL = f"""
DROP VIEW IF EXISTS {SCHEMA}.reference_probe_metadata"""

def upgrade() -> None:
    # Drop the view first, just to be extra safe.
    op.execute(DROP_VIEW_SQL)
    op.execute(CREATE_VIEW_SQL)


def downgrade() -> None:
    op.execute(DROP_VIEW_SQL)
