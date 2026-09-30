"""update probe_data types

Revision ID: b88042bae240
Revises: c95e49e551be
Create Date: 2026-09-11 14:45:53.382353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b88042bae240'
down_revision: Union[str, None] = 'c95e49e551be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = 'castdb'

def upgrade() -> None:
    op.alter_column("probe_data",
                    "value",
                    new_column_name="value_jsonb",
                    nullable=True,
                    schema=SCHEMA)
    op.add_column("probe_data",
                  sa.Column("value_float", sa.Float(), nullable=True),
                  schema=SCHEMA)

    # Backfill value_float from the numeric jsonb values
    op.execute(
        """
        UPDATE castdb.probe_data pd
        SET value_float = (pd.value_jsonb #>> '{}')::double precision
        FROM castdb.metric_type mt
        WHERE pd.metric_type_uuid = mt.uuid
          AND mt.value_type IN ('float'
            , 'int')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE castdb.probe_data
        SET value_jsonb = to_jsonb(value_float)
        WHERE value_float IS NOT NULL
        """
    )
    op.drop_column("probe_data", "value_float", schema=SCHEMA)

    op.alter_column("probe_data", "value_jsonb", nullable=False, new_column_name="value", schema=SCHEMA)
