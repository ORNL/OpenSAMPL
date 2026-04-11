"""Idempotent bootstrap of lookup tables required for load paths (reference_type, metric_type, reference, defaults)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import text

from opensampl.load.table_factory import TableFactory
from opensampl.metrics import METRICS
from opensampl.metrics import MetricType as PydanticMetricType
from opensampl.references import REF_TYPES
from opensampl.references import ReferenceType as PydanticReferenceType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _iter_reference_types() -> list[PydanticReferenceType]:
    return [v for v in REF_TYPES.__dict__.values() if isinstance(v, PydanticReferenceType)]


def _iter_metrics() -> list[PydanticMetricType]:
    return [v for v in METRICS.__dict__.values() if isinstance(v, PydanticMetricType)]


def ensure_get_default_uuid_function(session: Session) -> None:
    """
    Ensure public.get_default_uuid_for(text) exists.

    ProbeData.before_insert calls this name without a schema; it must live in a schema on the connection search_path
    (typically public).
    """
    if session.bind.dialect.name != "postgresql":
        return

    session.execute(
        text(
            """
CREATE OR REPLACE FUNCTION public.get_default_uuid_for(table_category text)
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT d.uuid::uuid
  FROM castdb.defaults AS d
  WHERE d.table_name = table_category
  LIMIT 1;
$$;
"""
        )
    )
    session.flush()


def seed_lookup_tables(session: Session) -> None:
    """
    Populate lookup tables from REF_TYPES, METRICS, and baseline reference/defaults rows.

    Safe to run repeatedly (uses TableFactory with if_exists='ignore').
    """
    ensure_get_default_uuid_function(session)

    rt_factory = TableFactory("reference_type", session=session)
    for ref in _iter_reference_types():
        rt_factory.write(data=ref.model_dump(), if_exists="ignore")

    unknown_rt = rt_factory.find_existing(data=REF_TYPES.UNKNOWN.model_dump())
    if unknown_rt is None:
        raise RuntimeError("Bootstrap failed: UNKNOWN reference_type missing after seed")

    ref_factory = TableFactory("reference", session=session)
    ref_factory.write(
        data={"reference_type_uuid": unknown_rt.uuid, "compound_reference_uuid": None},
        if_exists="ignore",
    )

    mt_factory = TableFactory("metric_type", session=session)
    for m in _iter_metrics():
        mt_factory.write(data=m.model_dump(), if_exists="ignore")

    unknown_mt = mt_factory.find_existing(data=METRICS.UNKNOWN.model_dump())
    if unknown_mt is None:
        raise RuntimeError("Bootstrap failed: UNKNOWN metric_type missing after seed")

    default_ref = ref_factory.find_existing(
        data={"reference_type_uuid": unknown_rt.uuid, "compound_reference_uuid": None}
    )
    if default_ref is None:
        raise RuntimeError("Bootstrap failed: default reference row missing")

    def_factory = TableFactory("defaults", session=session)
    def_factory.write(data={"table_name": "reference", "uuid": default_ref.uuid}, if_exists="ignore")
    def_factory.write(data={"table_name": "metric_type", "uuid": unknown_mt.uuid}, if_exists="ignore")

    ensure_campus_locations_view(session)

    session.flush()
    logger.info(
        "Lookup tables bootstrapped (defaults: reference={}, metric_type={})",
        default_ref.uuid,
        unknown_mt.uuid,
    )


def ensure_campus_locations_view(session: Session) -> None:
    """
    Create castdb.campus_locations view expected by the public geospatial Grafana dashboard.

    Maps ORM ``locations`` (PostGIS geom) to latitude/longitude/campus columns.
    """
    if session.bind.dialect.name != "postgresql":
        return

    session.execute(
        text(
            """
CREATE OR REPLACE VIEW castdb.campus_locations AS
SELECT
    l.uuid,
    l.name,
    ST_Y(l.geom::geometry) AS latitude,
    ST_X(l.geom::geometry) AS longitude,
    l.name AS campus,
    l.public
FROM castdb.locations l;
"""
        )
    )
    session.flush()
