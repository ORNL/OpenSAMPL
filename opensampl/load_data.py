"""Main functionality for loading data into the database"""

import json
from typing import Any, Literal, Optional

import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from opensampl.config.base import BaseConfig
from opensampl.db.orm import Base, ProbeData
from opensampl.load.routing import route
from opensampl.load.table_factory import TableFactory
from opensampl.metrics import MetricType
from opensampl.references import ReferenceType
from opensampl.vendors.constants import ProbeKey, VendorType

conflict_actions = Literal["error", "replace", "update", "ignore"]


@route("write_to_table")
def write_to_table(
    table: str,
    data: dict[str, Any],
    _config: BaseConfig,
    if_exists: conflict_actions = "update",
    session: Optional[Session] = None,
):
    """
    Write object to table with configurable behavior for handling conflicts.

    Args:
    ----
        table: Name of the table to write to
        data: Dictionary of column names and values to write
        _config: BaseSettings object, automatically filled by route wrapper
        if_exists: How to handle conflicts with existing entries. One of:
            - 'update': Only update fields that are provided and non-default (default)
            - 'error': Raise an error if entry exists
            - 'replace': Replace all non-primary-key fields with new values
            - 'ignore': Skip if entry exists
        session: Optional SQLAlchemy session

    Raises:
    ------
        ValueError: If table not found or invalid on_conflict value
        SQLAlchemyError: For database errors

    """
    if if_exists not in ["error", "replace", "update", "ignore"]:
        raise ValueError("on_conflict must be one of: 'error', 'replace', 'update', 'ignore'")

    if _config.ROUTE_TO_BACKEND:
        return {"table": table, "data": data, "if_exists": if_exists}

    if not isinstance(session, Session):
        raise TypeError("Session must be a SQLAlchemy session")

    try:
        table_factory = TableFactory(table, session)
        logger.debug(f"{data=}")

        table_factory.write(data=data, if_exists=if_exists)

        session.commit()
        return None  # noqa: TRY300

    except Exception as e:
        session.rollback()
        logger.error(f"Error writing to table: {e}")
        raise


@route("load_time_data", send_file=True)
def load_time_data(
    probe_key: ProbeKey,
    metric_type: MetricType,
    reference_type: ReferenceType,
    data: pd.DataFrame,
    _config: BaseConfig,
    compound_key: Optional[dict[str, Any]] = None,
    strict: bool = True,
    session: Optional[Session] = None,
):
    """
    Write time data to probe_data table

    Args:
        probe_key: ProbeKey object
        metric_type: MetricType object
        reference_type: ReferenceType object
        data: pandas dataframe with time and value columns
        _config: BaseSettings object, automatically filled by route wrapper
        compound_key: UUID for the reference if reference type is compound
        strict: If true, raises error if any of the data parts (reference/metric/etc) not found.
            If false, creates new probe. Default: True
        session: SQLAlchemy session

    """
    if _config.ROUTE_TO_BACKEND:
        csv_data = data.to_csv(index=False).encode("utf-8")
        return {
            "data": {
                "probe_key_str": json.dumps(probe_key.model_dump()),
                "metric_type_str": json.dumps(metric_type.model_dump()),
                "reference_type_str": json.dumps(reference_type.model_dump()),
                "compound_key_str": json.dumps(compound_key),
            },
            "files": {"file": ("time_data.csv", csv_data, "text/csv")},
        }

    if not isinstance(session, Session):
        raise TypeError("Session must be a SQLAlchemy session")

    try:
        from opensampl.load.data import DataFactory

        data_definition = DataFactory(
            probe_key=probe_key,
            metric_type=metric_type,
            reference_type=reference_type,
            compound_key=compound_key,
            strict=strict,
            session=session,
        )

        if any(x is None for x in [data_definition.probe, data_definition.metric, data_definition.reference]):
            raise RuntimeError(f"Not all required definition fields filled: {data_definition.dump_factory()}")  # noqa: TRY301

        df = data[["time", "value"]].copy()  # Only keep required columns.
        df["probe_uuid"] = data_definition.probe.uuid  # ty: ignore[possibly-unbound-attribute]
        df["reference_uuid"] = data_definition.reference.uuid  # ty: ignore[possibly-unbound-attribute]
        df["metric_type_uuid"] = data_definition.metric.uuid  # ty: ignore[possibly-unbound-attribute]

        # Ensure correct dtypes
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="raise")

        dtype = {column.name: column.type for column in ProbeData.__table__.columns}

        # Write directly to database using pandas
        df.to_sql(
            ProbeData.__tablename__,
            session.connection(),
            schema=ProbeData.__table__.schema,
            if_exists="append",
            index=False,
            method="multi",
            dtype=dtype,
        )

        session.commit()
    except Exception:
        session.rollback()
        raise


@route("load_probe_metadata")
def load_probe_metadata(
    *,
    vendor: VendorType,
    probe_key: ProbeKey,
    data: dict[str, Any],
    _config: BaseConfig,
    session: Optional[Session] = None,
):
    """Write object to table"""
    if _config.ROUTE_TO_BACKEND:
        return {
            "vendor": vendor.model_dump(),
            "probe_key": probe_key.model_dump(),
            "data": data,
        }

    if not isinstance(session, Session):
        raise TypeError("Session must be a SQLAlchemy session")

    try:
        pm_factory = TableFactory(name="probe_metadata", session=session)

        pm_cols = {col.name for col in pm_factory.inspector.columns}
        probe_info = {k: data.pop(k) for k in list(data.keys()) if k in pm_cols}
        probe_info.update({"probe_id": probe_key.probe_id, "ip_address": probe_key.ip_address, "vendor": vendor.name})
        probe = pm_factory.write(data=probe_info, if_exists="update")

        data["probe_uuid"] = probe.uuid

        write_to_table(table=vendor.metadata_table, data=data, session=session, if_exists="update")

        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error writing to table: {e}")
        raise


@route("create_new_tables", method="GET")
def create_new_tables(*, _config: BaseConfig, create_schema: bool = True, session: Optional[Session] = None):
    """Use the ORM definition to create all tables, optionally creating the schema as well"""
    if _config.ROUTE_TO_BACKEND:
        return {"create_schema": create_schema}

    if not isinstance(session, Session):
        raise TypeError("Session must be a SQLAlchemy session")

    try:
        if create_schema:
            session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {Base.metadata.schema}"))
            session.commit()
        Base.metadata.create_all(session.bind)
    except Exception as e:
        session.rollback()
        logger.error(f"Error writing to table: {e}")
        raise
