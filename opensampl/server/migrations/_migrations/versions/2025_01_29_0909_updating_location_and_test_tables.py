"""updating location and test tables

Revision ID: bd1322d0b00f
Revises: c464878dac7b
Create Date: 2025-01-29 09:09:01.383919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

from loguru import logger

import uuid
from typing import Dict


# revision identifiers, used by Alembic.
revision: str = 'bd1322d0b00f'
down_revision: Union[str, None] = 'c464878dac7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'castdb'


def create_uuid_mapping(connection, table_name: str, id_columns: list) -> Dict[tuple, str]:
    """Create mapping of old composite keys to new UUIDs"""
    # Query all existing records
    select_stmt = sa.text(f"""
        SELECT {', '.join(id_columns)} 
        FROM {SCHEMA}.{table_name}
    """)
    records = connection.execute(select_stmt).fetchall()

    # Create mapping
    return {tuple(record): str(uuid.uuid4()) for record in records}


def upgrade():
    connection = op.get_bind()
    inspector = reflection.Inspector.from_engine(connection)

    def safe_create_unique_constraint(name, table, columns):
        existing = [uc['name'] for uc in inspector.get_unique_constraints(table, schema=SCHEMA)]
        if name not in existing:
            op.create_unique_constraint(name, table, columns, schema=SCHEMA)

    def safe_drop_constraint(constraint, table, type_='foreignkey'):
        constraints = [fk['name'] for fk in inspector.get_foreign_keys(table, schema=SCHEMA) if fk['name']]
        if constraint in constraints:
            op.drop_constraint(constraint, table, type_=type_, schema=SCHEMA)

    def safe_create_foreign_key(
            constraint: str,
            source_table: str,
            referent_table: str,
            local_cols: list[str],
            remote_cols: list[str]
    ):
        existing_fks = [fk["name"] for fk in inspector.get_foreign_keys(source_table, schema=SCHEMA)]
        if constraint not in existing_fks:
            op.create_foreign_key(
                constraint,
                source_table,
                referent_table,
                local_cols,
                remote_cols,
                source_schema=SCHEMA,
                referent_schema=SCHEMA
            )

    location_columns = [col["name"] for col in inspector.get_columns("locations", schema=SCHEMA)]
    probe_md_columns = [col['name'] for col in inspector.get_columns('probe_metadata', schema=SCHEMA)]
    if "uuid" not in location_columns:
        op.add_column("locations", sa.Column("uuid", sa.String(36), nullable=True), schema=SCHEMA)
        location_uuid_map = create_uuid_mapping(
            connection,
            'locations',
            ['location_id']
        )

        # Update locations with UUIDs
        for (location_id,), new_uuid in location_uuid_map.items():
            op.execute(f"""
                UPDATE {SCHEMA}.locations 
                SET uuid = '{new_uuid}'
                WHERE location_id = '{location_id}'
            """)

        # Make locations UUID and name columns non-nullable
        op.alter_column('locations', 'uuid',
                        existing_type=sa.String(36),
                        nullable=False,
                        schema=SCHEMA
                        )

        safe_create_unique_constraint(
            'uq_locations_uuid',
            'locations',
            ['uuid']
        )
        safe_drop_constraint('probe_metadata_location_id_fkey', 'probe_metadata')
        if 'location_uuid' not in probe_md_columns:
            op.add_column('probe_metadata',
                          sa.Column('location_uuid', sa.String(36), nullable=True),
                          schema=SCHEMA
                          )
        if 'location_id' in probe_md_columns:
            op.execute(f"""
                    UPDATE {SCHEMA}.probe_metadata pm
                    SET location_uuid = l.uuid
                    FROM {SCHEMA}.locations l
                    WHERE pm.location_id = l.location_id
                """)
        safe_drop_constraint('locations_pkey', 'locations', type_='primary')
        op.create_primary_key(
            'locations_pkey',
            'locations',
            ['uuid'],
            schema=SCHEMA
        )
        safe_create_foreign_key(
        'probe_metadata_location_uuid_fkey',
        'probe_metadata',
        'locations',
        ['location_uuid'],
        ['uuid'],
        )

    if "public" not in location_columns:
        op.add_column("locations", sa.Column("public", sa.Boolean, nullable=True), schema=SCHEMA)

    op.alter_column('locations', 'name',
                    existing_type=sa.Text,
                    nullable=False,
                    schema=SCHEMA
                    )

    safe_create_unique_constraint(
        'uq_locations_name',
        'locations',
        ['name']
    )

    # Step 2: Handle test_metadata table
    test_columns = [col["name"] for col in inspector.get_columns("test_metadata", schema=SCHEMA)]

    if 'uuid' not in test_columns:
        op.add_column('test_metadata',
                      sa.Column('uuid', sa.String(36), nullable=True),
                      schema=SCHEMA
                      )

        # Generate UUIDs for test_metadata
        test_uuid_map = create_uuid_mapping(
            connection,
            'test_metadata',
            ['test_id']
        )

        # Update test_metadata with UUIDs
        for (test_id,), new_uuid in test_uuid_map.items():
            op.execute(f"""
                UPDATE {SCHEMA}.test_metadata 
                SET uuid = '{new_uuid}'
                WHERE test_id = '{test_id}'
            """)

        # Make test_metadata UUID and name columns non-nullable
        op.alter_column('test_metadata', 'uuid',
                        existing_type=sa.String(36),
                        nullable=False,
                        schema=SCHEMA
                        )

        safe_drop_constraint('probe_metadata_test_id_fkey', 'probe_metadata')

        if 'test_uuid' not in probe_md_columns:
            op.add_column('probe_metadata',
                          sa.Column('test_uuid', sa.String(36), nullable=True),
                          schema=SCHEMA
                          )

        if 'test_id' in probe_md_columns:
            op.execute(f"""
                UPDATE {SCHEMA}.probe_metadata pm
                SET test_uuid = t.uuid
                FROM {SCHEMA}.test_metadata t
                WHERE pm.test_id = t.test_id
            """)

        safe_drop_constraint('test_metadata_pkey', 'test_metadata', type_='primary')
        op.create_primary_key(
            'test_metadata_pkey',
            'test_metadata',
            ['uuid'],
            schema=SCHEMA
        )
        safe_create_foreign_key(
            'probe_metadata_test_uuid_fkey',
            'probe_metadata',
            'test_metadata',
            ['test_uuid'],
            ['uuid']
        )

    op.alter_column('test_metadata', 'name',
                    existing_type=sa.Text,
                    nullable=False,
                    schema=SCHEMA
                    )

    safe_create_unique_constraint(
        'uq_test_metadata_uuid',
        'test_metadata',
        ['uuid']
    )
    safe_create_unique_constraint(
        'uq_test_metadata_name',
        'test_metadata',
        ['name']
    )


    op.drop_column('locations', 'location_id', schema=SCHEMA, if_exists=True)
    op.drop_column('test_metadata', 'test_id', schema=SCHEMA, if_exists=True)
    op.drop_column('probe_metadata', 'location_id', schema=SCHEMA, if_exists=True)
    op.drop_column('probe_metadata', 'test_id', schema=SCHEMA, if_exists=True)

def downgrade():
    logger.info("Downgrade is not supported for this migration.")