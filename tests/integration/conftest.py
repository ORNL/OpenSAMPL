"""Shared fixtures for integration-style tests backed by MockDB."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from opensampl.metrics import METRICS
from opensampl.references import REF_TYPES
from tests.utils.mockdb import MockDB


@pytest.fixture(scope="session")
def integration_db() -> MockDB:
    """Session-scoped MockDB with schema and default lookup rows pre-seeded."""
    return MockDB()


@pytest.fixture
def db_engine(integration_db: MockDB):
    """Engine handle for integration-style tests."""
    return integration_db.engine


@pytest.fixture
def db_session(integration_db: MockDB) -> Session:
    """
    Function-scoped session isolated by an outer transaction.

    This mirrors the intent of the previous pytest-postgresql fixture setup
    without depending on a live PostgreSQL process.
    """
    connection = integration_db.engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection)
    integration_db.set_current_session(session)
    try:
        yield session
    finally:
        session.close()
        integration_db.set_current_session(None)
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()


@pytest.fixture(scope="session")
def db_models(integration_db: MockDB) -> dict[str, type]:
    """Convenience access to MockDB table mappings."""
    return integration_db.table_mappings


@pytest.fixture(scope="session")
def seeded_uuids(integration_db: MockDB, db_models: dict[str, type]) -> dict[str, str]:
    """Expose seeded lookup UUIDs from the mock database."""
    DBDefaults = db_models["Defaults"]  # noqa: N806
    DBMetricType = db_models["MetricType"]  # noqa: N806
    DBReference = db_models["Reference"]  # noqa: N806
    DBReferenceType = db_models["ReferenceType"]  # noqa: N806
    session = integration_db.Session()
    try:
        uuids: dict[str, str] = {}

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


@pytest.fixture
def db_env(monkeypatch, db_engine) -> None:
    """Patch env vars so route-decorated functions point at the mock database URL."""
    monkeypatch.setenv("ROUTE_TO_BACKEND", "false")
    monkeypatch.setenv("DATABASE_URL", str(db_engine.url))
    monkeypatch.delenv("BACKEND_URL", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("INSECURE_REQUESTS", raising=False)
    monkeypatch.setenv("ENABLE_GEOLOCATE", "false")
