"""create time buckets

Revision ID: c464878dac7b
Revises: 7f8adc06bb6b
Create Date: 2025-01-28 22:12:48.387383

"""
from typing import Sequence, Union, Tuple

from alembic import op
import sqlalchemy as sa
from loguru import logger


# revision identifiers, used by Alembic.
revision: str = 'c464878dac7b'
down_revision: Union[str, None] = '7f8adc06bb6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

time_buckets = [
    #suffix   interval    cron schedule (min hr * * *)
    ('1min', '1 minute', '*/5 * * * *'),     # Every 5 minutes
    ('5min', '5 minutes', '*/5 * * * *'),    # Every 5 minutes
    ('15min', '15 minutes', '*/15 * * * *'), # Every 15 minutes
    ('1hour', '1 hour', '0 * * * *'),        # Start of every hour
    ('6hour', '6 hours', '0 */6 * * *'),     # Every 6 hours
    ('1day', '1 day', '0 0 * * *')           # Midnight every day
]

# def execute_out_of_transaction(statement: str):
#     """Execute a statement outside of a transaction block"""
#     # Get connection from alembic
#     connection = op.get_bind()
#
#     # Close existing transaction
#     connection.execution_options(isolation_level="AUTOCOMMIT")
#
#     # Execute statement
#     connection.execute(statement)


def upgrade():
    # Install pg_cron extension if not exists
    op.execute("""
        CREATE EXTENSION IF NOT EXISTS pg_cron;
    """)

    for suffix, interval, schedule in time_buckets:
        # Create materialized views with indexes
        try:
            op.execute(f"""
                CREATE MATERIALIZED VIEW castdb.avg_phase_err_{suffix} AS
                SELECT 
                    time_bucket('{interval}', pd.time) as "time",
                    pd.probe_uuid as uuid,
                    AVG(pd.value) * 1e9 as value
                FROM castdb.probe_data pd
                GROUP BY 
                    time_bucket('{interval}', pd.time),
                    pd.probe_uuid;
    
                CREATE INDEX ON castdb.avg_phase_err_{suffix} ("time" DESC);
                CREATE INDEX ON castdb.avg_phase_err_{suffix} (uuid);
                
                CREATE UNIQUE INDEX IF NOT EXISTS avg_phase_err_{suffix}_unique_idx ON castdb.avg_phase_err_{suffix} ("time", uuid);
    
                CREATE MATERIALIZED VIEW castdb.mtie_{suffix} AS
                SELECT 
                    time_bucket('{interval}', pd.time) as "time",
                    pd.probe_uuid as uuid,
                    (MAX(pd.value) - MIN(pd.value)) * 1e9 as value
                FROM castdb.probe_data pd
                GROUP BY 
                    time_bucket('{interval}', pd.time),
                    pd.probe_uuid;
    
                CREATE INDEX ON castdb.mtie_{suffix} ("time" DESC);
                CREATE INDEX ON castdb.mtie_{suffix} (uuid);
                
                CREATE UNIQUE INDEX IF NOT EXISTS mtie_{suffix}_unique_idx ON castdb.mtie_{suffix} ("time", uuid);
                -- Schedule refresh using pg_cron
                SELECT cron.schedule(
                    'refresh_{suffix}',
                    '{schedule}',
                    $$
                    REFRESH MATERIALIZED VIEW CONCURRENTLY castdb.avg_phase_err_{suffix};
                    REFRESH MATERIALIZED VIEW CONCURRENTLY castdb.mtie_{suffix};
                    $$
                );
            """)
        except Exception as e:
            logger.warning(f"Error creating materialized view for {suffix}: {e}")


def downgrade():
    for suffix, _, _ in time_buckets:
        # Remove cron jobs first
        op.execute(f"""
            SELECT cron.unschedule('refresh_{suffix}');
        """)

        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS castdb.avg_phase_err_{suffix} CASCADE;")
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS castdb.mtie_{suffix} CASCADE;")

    # Remove hypertable (this will keep the table but remove timescale functionality)
    # op.execute("""
    #     SELECT drop_chunks('castdb.probe_data', older_than => '-infinity'::timestamp);
    # """)