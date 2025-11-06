"""making default trigger functions

Revision ID: 94f32a76726e
Revises: 90e87a6293f7
Create Date: 2025-06-03 15:39:41.048401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94f32a76726e'
down_revision: Union[str, None] = '90e87a6293f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
    -- Trigger function to set default values for probe_data table
    CREATE OR REPLACE FUNCTION set_probe_data_defaults()
    RETURNS TRIGGER AS $$
    BEGIN
        -- Set default reference_uuid if not provided
        IF NEW.reference_uuid IS NULL THEN
            NEW.reference_uuid := get_default_uuid_for('reference');
        END IF;
        
        -- Set default metric_type_uuid if not provided
        IF NEW.metric_type_uuid IS NULL THEN
            NEW.metric_type_uuid := get_default_uuid_for('metric_type');
        END IF;
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Create the trigger that fires before INSERT or UPDATE
    CREATE TRIGGER probe_data_set_defaults
        BEFORE INSERT ON castdb.probe_data
        FOR EACH ROW
    EXECUTE FUNCTION set_probe_data_defaults();
    """))


def downgrade() -> None:
    op.execute(sa.text(
        """
        DROP TRIGGER IF EXISTS probe_data_set_defaults ON castdb.probe_data;
        DROP FUNCTION IF EXISTS set_probe_data_defaults;
        """
    ))
