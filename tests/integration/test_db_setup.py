"""
tests/integration/test_db_setup.py

Smoke tests to verify the test database spun up and seeded correctly.
"""

import pytest
from sqlalchemy import text

from opensampl.db.orm import Defaults as DBDefaults
from opensampl.db.orm import MetricType as DBMetricType
from opensampl.db.orm import Reference as DBReference
from opensampl.db.orm import ReferenceType as DBReferenceType
from opensampl.metrics import METRICS, MetricType
from opensampl.references import REF_TYPES, ReferenceType


def test_schema_exists(db_session):
    """castdb schema was created."""
    result = db_session.execute(
        text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'castdb'")
    ).scalar()
    assert result == "castdb"


def test_postgis_installed(db_session):
    """PostGIS extension is available (required for Locations.geom)."""
    result = db_session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'postgis'")).scalar()
    assert result == "postgis"


def test_all_metrics_seeded(db_session):
    """Every MetricType defined on METRICS is present in the metric_type table."""
    expected = {v.name for v in METRICS.__dict__.values() if isinstance(v, MetricType)}
    seeded = {row.name for row in db_session.query(DBMetricType).all()}
    assert expected == seeded


def test_all_reference_types_seeded(db_session):
    """Every ReferenceType defined on REF_TYPES is present in the reference_type table."""
    expected = {v.name for v in REF_TYPES.__dict__.values() if isinstance(v, ReferenceType)}
    seeded = {row.name for row in db_session.query(DBReferenceType).all()}
    assert expected == seeded


def test_default_reference_row_exists(db_session):
    """A default UNKNOWN reference row exists for get_default_uuid_for('reference')."""
    unknown_ref_type = db_session.query(DBReferenceType).filter_by(name=REF_TYPES.UNKNOWN.name).one()
    ref = db_session.query(DBReference).filter_by(
        reference_type_uuid=unknown_ref_type.uuid,
        compound_reference_uuid=None,
    ).first()
    assert ref is not None


def test_defaults_table_seeded(db_session):
    """defaults table has entries for both metric_type and reference."""
    rows = {row.table_name for row in db_session.query(DBDefaults).all()}
    assert "metric_type" in rows
    assert "reference" in rows


def test_get_default_uuid_for_metric_type(db_session):
    """Stub function returns the UUID of the UNKNOWN metric type."""
    result = db_session.execute(text("SELECT get_default_uuid_for('metric_type')")).scalar()
    expected = db_session.query(DBMetricType.uuid).filter_by(name=METRICS.UNKNOWN.name).scalar()
    assert result == expected


def test_get_default_uuid_for_reference(db_session):
    """Stub function returns the UUID of the default UNKNOWN reference row."""
    result = db_session.execute(text("SELECT get_default_uuid_for('reference')")).scalar()
    unknown_ref_type = db_session.query(DBReferenceType).filter_by(name=REF_TYPES.UNKNOWN.name).one()
    expected = db_session.query(DBReference.uuid).filter_by(
        reference_type_uuid=unknown_ref_type.uuid,
        compound_reference_uuid=None,
    ).scalar()
    assert result == expected


def test_seeded_uuids_fixture(seeded_uuids):
    """seeded_uuids convenience fixture has the expected keys."""
    assert f"metric_type.{METRICS.UNKNOWN.name}" in seeded_uuids
    assert f"metric_type.{METRICS.PHASE_OFFSET.name}" in seeded_uuids
    assert f"reference_type.{REF_TYPES.UNKNOWN.name}" in seeded_uuids
    assert "reference.unknown" in seeded_uuids
    assert "default.metric_type" in seeded_uuids
    assert "default.reference" in seeded_uuids


def test_session_rollback_isolation(db_session, db_engine):
    """Writes in one session do not leak — the savepoint rolls back cleanly."""
    from opensampl.db.orm import TestMetadata

    db_session.add(TestMetadata(name="rollback-canary"))
    db_session.flush()

    # Row is visible within this session
    assert db_session.query(TestMetadata).filter_by(name="rollback-canary").one()

    # After the test ends the fixture rolls back, but we can verify the
    # mechanism works by checking a fresh session sees nothing yet
    from sqlalchemy.orm import Session
    with Session(bind=db_engine) as fresh:
        result = fresh.query(TestMetadata).filter_by(name="rollback-canary").first()
        assert result is None, "Savepoint did not isolate the write from other sessions"