"""Smoke tests to verify the seeded mock database state."""

from sqlalchemy import text

from opensampl.metrics import METRICS, MetricType
from opensampl.references import REF_TYPES, ReferenceType


def test_schema_exists(db_models):
    """Mocked tables preserve the expected logical table names."""
    assert db_models["MetricType"].__tablename__ == "metric_type"
    assert db_models["ReferenceType"].__tablename__ == "reference_type"
    assert db_models["Reference"].__tablename__ == "reference"


def test_postgis_installed(db_session):
    """Locations geometry metadata is present in the mock schema."""
    geometry_columns = db_session.execute(
        text("SELECT f_table_name, f_geometry_column FROM geometry_columns WHERE f_table_name = 'locations'")
    ).fetchall()
    assert ("locations", "geom") in geometry_columns


def test_all_metrics_seeded(db_session, db_models):
    """Every MetricType defined on METRICS is present in the metric_type table."""
    DBMetricType = db_models["MetricType"]  # noqa: N806
    expected = {v.name for v in METRICS.__dict__.values() if isinstance(v, MetricType)}
    seeded = {row.name for row in db_session.query(DBMetricType).all()}
    assert expected == seeded


def test_all_reference_types_seeded(db_session, db_models):
    """Every ReferenceType defined on REF_TYPES is present in the reference_type table."""
    DBReferenceType = db_models["ReferenceType"]  # noqa: N806
    expected = {v.name for v in REF_TYPES.__dict__.values() if isinstance(v, ReferenceType)}
    seeded = {row.name for row in db_session.query(DBReferenceType).all()}
    assert expected == seeded


def test_default_reference_row_exists(db_session, db_models):
    """A default UNKNOWN reference row exists for get_default_uuid_for('reference')."""
    DBReference = db_models["Reference"]  # noqa: N806
    DBReferenceType = db_models["ReferenceType"]  # noqa: N806
    unknown_ref_type = db_session.query(DBReferenceType).filter_by(name=REF_TYPES.UNKNOWN.name).one()
    ref = db_session.query(DBReference).filter_by(
        reference_type_uuid=unknown_ref_type.uuid,
        compound_reference_uuid=None,
    ).first()
    assert ref is not None


def test_defaults_table_seeded(db_session, db_models):
    """defaults table has entries for both metric_type and reference."""
    DBDefaults = db_models["Defaults"]  # noqa: N806
    rows = {row.table_name for row in db_session.query(DBDefaults).all()}
    assert "metric_type" in rows
    assert "reference" in rows


def test_get_default_uuid_for_metric_type(db_session, db_models):
    """Defaults table returns the UUID of the UNKNOWN metric type."""
    DBDefaults = db_models["Defaults"]  # noqa: N806
    DBMetricType = db_models["MetricType"]  # noqa: N806
    result = db_session.query(DBDefaults.uuid).filter_by(table_name="metric_type").scalar()
    expected = db_session.query(DBMetricType.uuid).filter_by(name=METRICS.UNKNOWN.name).scalar()
    assert result == expected


def test_get_default_uuid_for_reference(db_session, db_models):
    """Defaults table returns the UUID of the default UNKNOWN reference row."""
    DBDefaults = db_models["Defaults"]  # noqa: N806
    DBReference = db_models["Reference"]  # noqa: N806
    DBReferenceType = db_models["ReferenceType"]  # noqa: N806
    result = db_session.query(DBDefaults.uuid).filter_by(table_name="reference").scalar()
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


def test_session_rollback_isolation(db_session, db_engine, db_models):
    """The mocked session can roll back writes cleanly."""
    TestMetadata = db_models["TestMetadata"]  # noqa: N806

    db_session.add(TestMetadata(name="rollback-canary"))
    db_session.flush()

    assert db_session.query(TestMetadata).filter_by(name="rollback-canary").one()
    db_session.rollback()
    result = db_session.query(TestMetadata).filter_by(name="rollback-canary").first()
    assert result is None, "Rollback did not clear the pending write"
