"""update db tables

Revision ID: 7f8adc06bb6b
Revises: fe18404ea614
Create Date: 2024-12-04 11:55:12.955284

"""
from typing import Sequence, Union, Dict

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection
from loguru import logger
import uuid

# revision identifiers, used by Alembic.
revision: str = '7f8adc06bb6b'
down_revision: Union[str, None] = 'fe18404ea614'
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
    # Create connection for executing raw SQL
    connection = op.get_bind()
    inspector = reflection.Inspector.from_engine(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('probe_metadata', schema=SCHEMA)]

    # Step 1: Add new UUID column to probe_metadata (nullable initially)
    if 'uuid' not in existing_columns:
        op.add_column('probe_metadata', sa.Column('uuid', sa.String(36), nullable=True), schema=SCHEMA)
        # Generate and store UUIDs for existing probe_metadata records
        probe_uuid_map = create_uuid_mapping(
            connection,
            'probe_metadata',
            ['probe_id', 'ip_address']
        )

        # Update probe_metadata with UUIDs
        for (probe_id, ip_address), new_uuid in probe_uuid_map.items():
            op.execute(f"""
                UPDATE {SCHEMA}.probe_metadata 
                SET uuid = '{new_uuid}', vendor = 'ADVA'
                WHERE probe_id = '{probe_id}' 
                AND ip_address = '{ip_address}'
            """)

        # Make UUID column non-nullable and make it the primary key
        op.alter_column('probe_metadata', 'uuid',
                        existing_type=sa.String(36),
                        nullable=False,
                        schema=SCHEMA
                        )

    if 'public' not in existing_columns:
        op.add_column('probe_metadata', sa.Column('public', sa.Boolean, nullable=True), schema=SCHEMA)



    def safe_drop_constraint(constraint, table):
        if table in inspector.get_table_names(schema=SCHEMA):
            constraints = [fk['name'] for fk in inspector.get_foreign_keys(table, schema=SCHEMA) if fk['name']]
            if constraint in constraints:
                op.drop_constraint(constraint, table, type_='foreignkey', schema=SCHEMA)

    # First drop foreign key constraints from dependent tables
    safe_drop_constraint('ad_data_probe_id_ip_address_fkey', 'ad_data')
    safe_drop_constraint('mtie_data_probe_id_ip_address_fkey', 'mtie_data')
    safe_drop_constraint('avg_phase_err_data_probe_id_ip_address_fkey', 'avg_phase_err_data')
    safe_drop_constraint('raw_data_probe_id_ip_address_fkey', 'raw_data')
    safe_drop_constraint('headers_probe_id_ip_address_fkey', 'headers')

    # Drop old primary key and create new one with UUID
    pk_info = inspector.get_pk_constraint('probe_metadata', schema=SCHEMA)
    existing_pk_name = pk_info.get('name')
    existing_pk_cols = pk_info.get('constrained_columns', [])

    # Replace only if it's not already set to 'uuid' as the sole primary key
    if existing_pk_cols != ['uuid']:
        if existing_pk_name:
            op.drop_constraint(existing_pk_name, 'probe_metadata', type_='primary', schema=SCHEMA)

        op.create_primary_key(
            'probe_metadata_pkey',
            'probe_metadata',
            ['uuid'],
            schema=SCHEMA
        )
    def safe_create_unique_constraint(name, table, columns):
        existing = [uc['name'] for uc in inspector.get_unique_constraints(table, schema=SCHEMA)]
        if name not in existing:
            op.create_unique_constraint(name, table, columns, schema=SCHEMA)

    safe_create_unique_constraint('uq_probe_metadata_uuid', 'probe_metadata', ['uuid'])
    safe_create_unique_constraint('uq_probe_metadata_name', 'probe_metadata', ['name'])
    safe_create_unique_constraint('uq_probe_metadata_ipaddress_probeid', 'probe_metadata', ['ip_address', 'probe_id'])


    # Now create adva_metadata table (after uuid is unique)
    op.create_table('adva_metadata',
                    sa.Column('probe_uuid', sa.String(36),
                              sa.ForeignKey(f'{SCHEMA}.probe_metadata.uuid'),
                              primary_key=True),
                    sa.Column('type', sa.Text),
                    sa.Column('start', sa.TIMESTAMP),
                    sa.Column('frequency', sa.Integer),
                    sa.Column('timemultiplier', sa.Integer),
                    sa.Column('multiplier', sa.Integer),
                    sa.Column('title', sa.Text),
                    sa.Column('adva_probe', sa.Text),
                    sa.Column('adva_reference', sa.Text),
                    sa.Column('adva_reference_expected_ql', sa.Text),
                    sa.Column('adva_source', sa.Text),
                    sa.Column('adva_direction', sa.Text),
                    sa.Column('adva_version', sa.Float),
                    sa.Column('adva_status', sa.Text),
                    sa.Column('adva_mtie_mask', sa.Text),
                    sa.Column('adva_mask_margin', sa.Integer),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Migrate data from adva_headers to adva_metadata
    if 'adva_headers' in inspector.get_table_names(schema=SCHEMA):
        op.execute(f"""
            INSERT INTO {SCHEMA}.adva_metadata (
                probe_uuid, type, start, frequency, multiplier,
                adva_probe, adva_reference,
                adva_source, adva_direction, adva_version, adva_status,
                adva_mtie_mask, adva_mask_margin
            )
            SELECT 
                pm.uuid,
                ah.type,
                ah.start,
                ah.frequency,
                CAST(ah.multiplier as INTEGER),
                ah.adva_probe,
                ah.adva_ref as adva_reference,
                ah.adva_src as adva_source,
                ah.adva_direction,
                CAST(ah.adva_version as FLOAT),
                ah.adva_status,
                ah.adva_mtie_mask,
                CAST(ah.adva_mask_margin as INTEGER)
            FROM {SCHEMA}.adva_headers ah
            JOIN {SCHEMA}.headers h ON h.adva_id = ah.id
            JOIN {SCHEMA}.probe_metadata pm 
                ON pm.probe_id = h.probe_id 
                AND pm.ip_address = h.ip_address
        """)

    # Create new probe_data table
    op.create_table('probe_data',
                    sa.Column('time', sa.TIMESTAMP, primary_key=True),
                    sa.Column('probe_uuid', sa.String(36),
                              sa.ForeignKey(f'{SCHEMA}.probe_metadata.uuid'),
                              primary_key=True),
                    sa.Column('value', sa.NUMERIC),
                    schema=SCHEMA,
                    if_not_exists=True
                    )

    # Convert probe_data to hypertable
    op.execute("""
        SELECT create_hypertable('castdb.probe_data', 'time',
            chunk_time_interval => INTERVAL '1 hour',
            if_not_exists => TRUE,
            migrate_data => TRUE);
    """)

    # Drop old header tables
    op.drop_table('adva_headers', schema=SCHEMA, if_exists=True)
    op.drop_table('headers', schema=SCHEMA, if_exists=True)



def downgrade():
    # This migration is not reversible due to potential data loss
    # and the complexity of regenerating composite keys
    logger.info("Downgrade is not supported for this migration.")
