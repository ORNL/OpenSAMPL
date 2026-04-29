"""
tests/conftest.py

Shared pytest fixtures for openSAMPL integration tests.

Prerequisites
-------------
- PostgreSQL with PostGIS extension available
- pytest-postgresql installed:
    uv add --group dev pytest-postgresql
- On macOS (Homebrew):
    brew install postgresql postgis

pytest-postgresql will locate pg_ctl automatically from your PATH. If you
have multiple Postgres versions installed, point it at the right one via
pytest.ini or pyproject.toml:

    [tool.pytest.ini_options]
    postgresql_exec = "/opt/homebrew/opt/postgresql@16/bin/pg_ctl"
"""

import pytest
from pytest_postgresql import factories as pg_factories
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from opensampl.db.orm import Base
from opensampl.db.orm import Defaults as DBDefaults
from opensampl.db.orm import MetricType as DBMetricType
from opensampl.db.orm import Reference as DBReference
from opensampl.db.orm import ReferenceType as DBReferenceType
from opensampl.metrics import METRICS, MetricType
from opensampl.references import REF_TYPES, ReferenceType


# ---------------------------------------------------------------------------
# pytest-postgresql process fixture
#
# postgresql_proc manages the Postgres server lifetime (session-scoped).
# We deliberately avoid the postgresql connection fixture so we have no
# dependency on a specific psycopg version — the project already has
# psycopg2-binary, and SQLAlchemy handles the connection from here.
# ---------------------------------------------------------------------------

postgresql_proc = pg_factories.postgresql_proc()


# ---------------------------------------------------------------------------
# Helpers: introspect METRICS / REF_TYPES the same way VENDORS.all() does
# ---------------------------------------------------------------------------

def _all_metrics() -> list[MetricType]:
    """All MetricType instances defined on the METRICS class."""
    return [v for v in METRICS.__dict__.values() if isinstance(v, MetricType)]


def _all_ref_types() -> list[ReferenceType]:
    """All ReferenceType instances defined on REF_TYPES (includes CompoundReferenceType)."""
    return [v for v in REF_TYPES.__dict__.values() if isinstance(v, ReferenceType)]


# ---------------------------------------------------------------------------
# Session-scoped engine
# Schema, tables, seed data, and the get_default_uuid_for stub are all
# created once per test session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine(postgresql_proc):
    """
    Session-scoped SQLAlchemy engine pointed at the pytest-postgresql instance.

    Connects using psycopg2-binary (already a project dependency) so there is
    no dependency on psycopg3.  Creates the opensampl_test database on first
    run via a temporary autocommit connection to the default 'postgres' database.

    Lifecycle:
        1. Create the opensampl_test database.
        2. Install PostGIS and create the castdb schema.
        3. Create all ORM tables via Base.metadata.create_all().
        4. Seed metric_type, reference_type, reference, and defaults tables.
        5. Install the get_default_uuid_for() PL/pgSQL stub.
    """
    # postgresql_proc exposes plain attributes — no psycopg version dependency
    host = postgresql_proc.host
    port = postgresql_proc.port
    user = postgresql_proc.user
    test_dbname = "opensampl_test"

    # Connect to the default 'postgres' db to create our test database.
    # Must use isolation_level=AUTOCOMMIT because CREATE DATABASE cannot run
    # inside a transaction block.
    bootstrap_url = f"postgresql+psycopg2://{user}@{host}:{port}/postgres"
    bootstrap_engine = create_engine(bootstrap_url, isolation_level="AUTOCOMMIT")
    with bootstrap_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": test_dbname},
        ).fetchone()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{test_dbname}"'))
    bootstrap_engine.dispose()

    db_url = f"postgresql+psycopg2://{user}@{host}:{port}/{test_dbname}"
    engine = create_engine(db_url, echo=False)

    with engine.begin() as conn:
        # PostGIS is required by the Locations.geom column (GeoAlchemy2)
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {Base.metadata.schema}"))

    Base.metadata.create_all(engine)
    _seed_lookup_tables(engine)
    _install_default_uuid_stub(engine)

    yield engine

    engine.dispose()


# ---------------------------------------------------------------------------
# Seeding helpers (called once from db_engine, not exposed as fixtures)
# ---------------------------------------------------------------------------

def _seed_lookup_tables(engine) -> None:
    """
    Populate metric_type, reference_type, reference, and defaults tables.

    Reads directly from the METRICS and REF_TYPES Python definitions so the
    test DB always matches what the application expects — no hardcoded values.
    After inserting the lookup rows, seeds the defaults table with the UUIDs
    of the UNKNOWN rows, mirroring how production initialises get_default_uuid_for().
    """
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # --- metric_type ---
        for metric in _all_metrics():
            data = metric.model_dump()  # value_type serialised to str by field_serializer
            if not session.query(DBMetricType).filter_by(name=data["name"]).first():
                session.add(DBMetricType(**data))

        # --- reference_type ---
        # CompoundReferenceType.model_dump() includes reference_table; the column is nullable so plain
        # ReferenceType rows (no reference_table) are stored with NULL, which is correct.
        for ref_type in _all_ref_types():
            data = ref_type.model_dump()
            if not session.query(DBReferenceType).filter_by(name=data["name"]).first():
                session.add(DBReferenceType(**data))

        session.flush()

        # --- reference: one default UNKNOWN row --------------------------
        # get_default_uuid_for('reference') needs at least one reference row to
        # point at.  We use the UNKNOWN reference type with no compound target.
        unknown_ref_type = session.query(DBReferenceType).filter_by(name=REF_TYPES.UNKNOWN.name).one()
        default_reference = session.query(DBReference).filter_by(
            reference_type_uuid=unknown_ref_type.uuid,
            compound_reference_uuid=None,
        ).first()
        if not default_reference:
            default_reference = DBReference(
                reference_type_uuid=unknown_ref_type.uuid,
                compound_reference_uuid=None,
            )
            session.add(default_reference)

        session.flush()

        # --- defaults table ---------------------------------------------
        # Maps table/category names to the UUID that get_default_uuid_for()
        # should return.  Mirrors what the production TimescaleDB init does.
        unknown_metric = session.query(DBMetricType).filter_by(name=METRICS.UNKNOWN.name).one()

        for table_name, uuid_value in [
            ("metric_type", unknown_metric.uuid),
            ("reference", default_reference.uuid),
        ]:
            if not session.query(DBDefaults).filter_by(table_name=table_name).first():
                session.add(DBDefaults(table_name=table_name, uuid=uuid_value))

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _install_default_uuid_stub(engine) -> None:
    """
    Install the get_default_uuid_for() PL/pgSQL stub.

    Rather than hardcoding UUIDs, the stub queries the defaults table — the
    same approach the production TimescaleDB function uses.  This means it
    automatically returns whatever was seeded above.
    """
    schema = Base.metadata.schema

    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE OR REPLACE FUNCTION get_default_uuid_for(entity_type TEXT)
            RETURNS TEXT AS $$
            DECLARE
                result_uuid TEXT;
            BEGIN
                SELECT uuid
                INTO result_uuid
                FROM {schema}.defaults
                WHERE table_name = entity_type;

                RETURN result_uuid;
            END;
            $$ LANGUAGE plpgsql;
        """))


# ---------------------------------------------------------------------------
# Per-test session — savepoint rollback keeps tests isolated
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session(db_engine) -> Session:
    """
    Function-scoped database session backed by a savepoint.

    Every test starts with the full seeded dataset intact.  Any rows inserted
    or updated during the test are rolled back when the test ends without
    disturbing the seeded rows, and without the cost of recreating the schema.

    Usage::

        def test_something(db_session):
            factory = TableFactory("locations", db_session)
            factory.write({"name": "test-loc", "lat": 35.9, "lon": -84.3})
            result = db_session.query(Locations).filter_by(name="test-loc").one()
            assert result.name == "test-loc"
            # row is gone after the test
    """
    connection = db_engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection)
    session.begin_nested()  # SAVEPOINT — inner rollback target

    yield session

    session.close()
    outer_transaction.rollback()  # wipes everything written during the test
    connection.close()


# ---------------------------------------------------------------------------
# Seeded UUIDs — expose the canonical lookup UUIDs tests may need directly
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def seeded_uuids(db_engine) -> dict:
    """
    Session-scoped dict of UUIDs inserted during seed, keyed by logical name.

    Useful when a test needs to construct ORM objects by hand (e.g. ProbeData)
    and must reference real FK values.

    Keys
    ----
    metric_type.<MetricType.name>   — UUID from the metric_type table
    reference_type.<ReferenceType.name> — UUID from the reference_type table
    reference.unknown               — UUID of the default UNKNOWN reference row
    default.metric_type             — what get_default_uuid_for('metric_type') returns
    default.reference               — what get_default_uuid_for('reference') returns

    Example::

        def test_probe_data(db_session, seeded_uuids):
            phase_offset_uuid = seeded_uuids["metric_type.Phase Offset"]
    """
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()

    try:
        uuids: dict = {}

        for row in session.query(DBMetricType).all():
            uuids[f"metric_type.{row.name}"] = row.uuid

        for row in session.query(DBReferenceType).all():
            uuids[f"reference_type.{row.name}"] = row.uuid

        unknown_ref_type = session.query(DBReferenceType).filter_by(name=REF_TYPES.UNKNOWN.name).one()
        unknown_ref = session.query(DBReference).filter_by(
            reference_type_uuid=unknown_ref_type.uuid,
            compound_reference_uuid=None,
        ).one()
        uuids["reference.unknown"] = unknown_ref.uuid

        for row in session.query(DBDefaults).all():
            uuids[f"default.{row.table_name}"] = row.uuid

        return uuids

    finally:
        session.close()


# ---------------------------------------------------------------------------
# Routing environment — patch BaseConfig for @route-decorated functions
# ---------------------------------------------------------------------------

@pytest.fixture
def db_env(db_engine, monkeypatch) -> None:
    """
    Set env vars so that BaseConfig routes directly to the test DB.

    Any test that calls a @route-decorated function (write_to_table,
    load_time_data, load_probe_metadata, create_new_tables) must include
    this fixture.  Pass session=db_session explicitly so the route wrapper
    uses your test session rather than opening a new one.

    Usage::

        def test_write_to_table(db_env, db_session):
            write_to_table(
                "locations",
                {"name": "test-loc", "lat": 35.9, "lon": -84.3},
                session=db_session,
            )
    """
    monkeypatch.setenv("ROUTE_TO_BACKEND", "false")
    monkeypatch.setenv("DATABASE_URL", str(db_engine.url))
    monkeypatch.delenv("BACKEND_URL", raising=False)