"""setting default reference and metric

Revision ID: 90e87a6293f7
Revises: 4b47485da562
Create Date: 2025-06-03 13:58:13.297062

"""
from typing import Sequence, Union
import os
from alembic import op
import sqlalchemy as sa

from loguru import logger

# revision identifiers, used by Alembic.
revision: str = '90e87a6293f7'
down_revision: Union[str, None] = '4b47485da562'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'castdb'

def upgrade() -> None:
    # Create the default_table
    op.create_table(
        'defaults',
        sa.Column('table_name', sa.Text, primary_key=True, comment='Name of the table/category this entry belongs to'),
        sa.Column('uuid', sa.String(36), nullable=False, comment='UUID reference resolved from name_value'),
        schema=SCHEMA,
        if_not_exists=True,
    )

    # 2. Function to get default UUID
    op.execute(sa.text(f"""
    CREATE OR REPLACE FUNCTION get_default_uuid_for(table_arg TEXT)
    RETURNS UUID AS $$
    DECLARE
        result UUID;
    BEGIN
        SELECT uuid INTO result
        FROM {SCHEMA}.defaults
        WHERE table_name = table_arg;
    
        IF result IS NULL THEN
            RAISE EXCEPTION 'No default UUID found for table: %', table_arg;
        END IF;
    
        RETURN result;
    END;
    $$ LANGUAGE plpgsql;
    """))

    # 3. Function to set default UUID by name
    op.execute(sa.text(f"""
    CREATE OR REPLACE FUNCTION set_default_by_name(
        table_arg TEXT,
        name_value TEXT
    )
    RETURNS VOID AS $$
    DECLARE
        id UUID;
        schema_name TEXT := '{SCHEMA}';
        sql TEXT;
    BEGIN
        -- Use format with two %I to quote both schema and table names
        sql := format('SELECT uuid FROM %I.%I WHERE lower(name) = lower($1) LIMIT 1',
                      schema_name, table_arg);
        EXECUTE sql INTO id USING name_value;

        IF id IS NULL THEN
            RAISE EXCEPTION 'No row found in %.% with name = %', schema_name, table_arg, name_value;
        END IF;

        INSERT INTO "{SCHEMA}"."defaults" (table_name, uuid)
        VALUES (table_arg, id)
        ON CONFLICT (table_name) DO UPDATE
        SET uuid = EXCLUDED.uuid;
    END;
    $$ LANGUAGE plpgsql;
    """))

    # Set the defaults
    op.execute(sa.text(f"""SELECT set_default_by_name('metric_type', 'Phase Offset')"""))
    op.execute(sa.text(f"""SELECT set_default_by_name('reference_type', 'UNKNOWN')"""))

    op.execute(sa.text(f"""
    INSERT INTO "{SCHEMA}"."defaults" (table_name, uuid)
    VALUES ('reference', get_default_uuid_for('reference_type'))
    """))


def downgrade() -> None:
    op.execute(sa.text("""
    DROP FUNCTION IF EXISTS set_default_by_name CASCADE;
    DROP FUNCTION IF EXISTS get_default_uuid_for CASCADE;
    """))
    op.drop_table('defaults', schema=SCHEMA, if_exists=True)
