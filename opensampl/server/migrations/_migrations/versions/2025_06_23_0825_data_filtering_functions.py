"""data filtering functions

Revision ID: c73212f2c0dd
Revises: 94f32a76726e
Create Date: 2025-06-23 08:25:44.638142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c73212f2c0dd'
down_revision: Union[str, None] = '94f32a76726e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
    -- Function to filter probe data by probe UUID
    CREATE OR REPLACE FUNCTION get_probe_data_by_probe(probe_uuid_param TEXT)
    RETURNS TABLE(
        "time" TIMESTAMP,
        probe_uuid VARCHAR(36),
        reference_uuid VARCHAR(36),
        metric_type_uuid VARCHAR(36),
        value JSONB
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            pd.time,
            pd.probe_uuid,
            pd.reference_uuid,
            pd.metric_type_uuid,
            pd.value
        FROM castdb.probe_data pd
        WHERE pd.probe_uuid = probe_uuid_param
        ORDER BY pd.time;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Function to filter probe data by metric type UUID
    CREATE OR REPLACE FUNCTION get_probe_data_by_metric(metric_type_uuid_param TEXT)
    RETURNS TABLE(
        "time" TIMESTAMP,
        probe_uuid VARCHAR(36),
        reference_uuid VARCHAR(36),
        metric_type_uuid VARCHAR(36),
        value JSONB
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            pd.time,
            pd.probe_uuid,
            pd.reference_uuid,
            pd.metric_type_uuid,
            pd.value
        FROM castdb.probe_data pd
        WHERE pd.metric_type_uuid = metric_type_uuid_param
        ORDER BY pd.time;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Function to filter probe data by both probe UUID and metric type UUID
    CREATE OR REPLACE FUNCTION get_probe_data_by_probe_and_metric(
        probe_uuid_param TEXT,
        metric_type_uuid_param TEXT
    )
    RETURNS TABLE(
        "time" TIMESTAMP,
        probe_uuid VARCHAR(36),
        reference_uuid VARCHAR(36),
        metric_type_uuid VARCHAR(36),
        value JSONB
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            pd.time,
            pd.probe_uuid,
            pd.reference_uuid,
            pd.metric_type_uuid,
            pd.value
        FROM castdb.probe_data pd
        WHERE pd.probe_uuid = probe_uuid_param 
          AND pd.metric_type_uuid = metric_type_uuid_param
        ORDER BY pd.time;
    END;
    $$ LANGUAGE plpgsql;
    """))


def downgrade() -> None:
    op.execute(sa.text("""
    DROP FUNCTION IF EXISTS get_probe_data_by_probe;
    DROP FUNCTION IF EXISTS get_probe_data_by_metric;
    DROP FUNCTION IF EXISTS get_probe_data_by_probe_and_metric;
    """))
