"""Main functionality for loading data into the database"""

import json
from functools import wraps
from typing import Any, Callable, Literal, Optional

import pandas as pd
import requests
from loguru import logger
from sqlalchemy import UniqueConstraint, and_, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from opensampl.constants import ENV_VARS
from opensampl.db.orm import Base
from opensampl.vendors.constants import ProbeKey, VendorType

conflict_actions = Literal["error", "replace", "update", "ignore"]
request_methods = Literal["POST", "GET", "PUT", "DELETE"]


def route_or_direct(route_endpoint: str, method: request_methods = "POST", send_file: bool = False):
    """
    Handle routing to backend or direct database operations based on environment configuration via decorator

    Args:
    ----
        route_endpoint: The backend endpoint to route to if ROUTE_TO_BACKEND is True
        method: if routing through backend, the request method. Default: POST
        send_file: bool, if True sends a file to backend. Otherwise, json. Default: False

    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: list, **kwargs: dict) -> Callable:
            session = kwargs.pop("session", None)
            backend_url = ENV_VARS.BACKEND_URL.get_value()
            route_to_backend = ENV_VARS.ROUTE_TO_BACKEND.get_value()
            database_url = ENV_VARS.DATABASE_URL.get_value()
            api_key = ENV_VARS.API_KEY.get_value()

            logger.debug(f"{route_to_backend=}")
            if route_to_backend:
                if not backend_url:
                    raise ValueError("Set BACKEND_URL env var to use ROUTE_TO_BACKEND functionality")

                headers = {
                    "access-key": api_key,
                }

                pyld = func(*args, **kwargs)
                if send_file:
                    request_params = pyld
                    logger.debug(f"data={pyld.get('data')}")
                    logger.debug(f"filesize in bytes={len(pyld.get('files').get('file')[1])}")
                else:
                    request_params = {
                        "json": pyld,
                    }
                    headers.update({"Content-Type": "application/json"})
                    logger.debug(f"json={json.dumps(pyld, indent=4)}")
                # Extract data from the function
                try:
                    response = requests.request(
                        method=method,
                        url=f"{backend_url}/{route_endpoint}",
                        headers=headers,
                        **request_params,
                        timeout=300,
                    )
                    response.raise_for_status()
                    logger.debug(f"Response: {response.json()}")
                except requests.exceptions.RequestException as e:
                    logger.debug(f"Error making request to backend: {e}")
                    raise
            else:
                if not session:
                    if not database_url:
                        raise ValueError(
                            "Provide Session or Set DATABASE_URL env var to use direct database operations or set "
                            "ROUTE_TO_BACKEND to true and configure BACKEND_URL to use backend routing"
                        )
                    session = sessionmaker(create_engine(database_url))()

                return func(*args, **kwargs, session=session)

        return wrapper

    return decorator


@route_or_direct("write_to_table")
def write_to_table(
    table: str,
    data: dict[str, Any],
    if_exists: conflict_actions = "update",
    session: Optional[Session] = None,
):
    """
    Write object to table with configurable behavior for handling conflicts.

    Args:
    ----
        table: Name of the table to write to
        data: Dictionary of column names and values to write
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

    if ENV_VARS.ROUTE_TO_BACKEND.get_value():
        return {"table": table, "data": data, "if_exists": if_exists}

    try:
        TableModel = resolve_table_model(table)  # noqa: N806
        inspector = inspect(TableModel)
        pk_columns = [col.key for col in inspector.primary_key]
        pk_conditions = build_pk_conditions(TableModel, pk_columns, data)

        unique_constraints = extract_unique_constraints(inspector, data)

        if not pk_conditions and not unique_constraints:
            raise ValueError(f"Did not provide identifiable fields for {table}")  # noqa: TRY301

        existing = find_existing_entry(session, TableModel, pk_conditions, unique_constraints)

        if existing:
            handle_existing_entry(existing, TableModel, data, pk_columns, inspector, if_exists, session)
        else:
            logger.debug(f"Will create new entry in {table} with {data}")
            session.add(TableModel(**data))

        session.commit()
        return None  # noqa: TRY300

    except Exception as e:
        session.rollback()
        logger.error(f"Error writing to table: {e}")
        raise


def resolve_table_model(table: str):
    """
    Retrieve the SQLAlchemy model class for the given table name.

    Args:
    ----
        table: Name of the table to resolve

    Returns:
    -------
        The corresponding SQLAlchemy model class

    Raises:
    ------
        ValueError: If table name is not found in metadata

    """
    for mapper in Base.registry.mappers:
        if mapper.class_.__tablename__ == table:
            return mapper.class_
    raise ValueError(f"Table {table} not found in database schema")


def build_pk_conditions(
    TableModel,  # noqa: N803,ANN001
    pk_columns: list[str],
    data: dict[str, Any],
):
    """
    Construct primary key filter conditions from provided data.

    Args:
    ----
        TableModel: The SQLAlchemy table class
        pk_columns: List of primary key column names
        data: Dictionary of input data

    Returns:
    -------
        A list of SQLAlchemy binary expressions for primary key filtering

    """
    pk_conditions = []
    for pk in pk_columns:
        if pk in data:
            pk_conditions.append(getattr(TableModel, pk) == data[pk])
        else:
            logger.debug(f"{pk} is primary but not in data")
    logger.debug(f"{pk_conditions=}")
    return pk_conditions


def extract_unique_constraints(inspector: inspect, data: dict[str, Any]):
    """
    Identify unique constraints that can be used to match existing entries.

    Args:
    ----
        inspector: SQLAlchemy inspector for the table
        data: Dictionary of input data

    Returns:
    -------
        A list of lists of (column_name, value) pairs for unique constraints

    """
    unique_constraints = []
    for constraint in inspector.tables[0].constraints:
        if hasattr(constraint, "columns") and isinstance(constraint, UniqueConstraint):
            cols = [col.key for col in constraint.columns]
            if all(col in data for col in cols):
                unique_constraints.append([(col, data[col]) for col in cols])
    logger.debug(f"{unique_constraints=}")
    return unique_constraints


def find_existing_entry(
    session: Session,
    TableModel,  # noqa: N803,ANN001
    pk_conditions: list[tuple[str, Any]],
    unique_constraints: list[list[tuple[str, Any]]],
):
    """
    Attempt to retrieve an existing entry using primary key or unique constraints.

    Args:
    ----
        session: SQLAlchemy session
        TableModel: The SQLAlchemy table class
        pk_conditions: Primary key filter conditions
        unique_constraints: List of unique constraint filters

    Returns:
    -------
        The existing table instance if found, otherwise None

    """
    if pk_conditions:
        existing = session.query(TableModel).filter(and_(*pk_conditions)).first()
        if existing:
            return existing

    all_constraints = []
    for constraint_columns in unique_constraints:
        constraint_condition = and_(*(getattr(TableModel, col) == val for col, val in constraint_columns))
        all_constraints.append(constraint_condition)

    if all_constraints:
        return session.query(TableModel).filter(and_(*all_constraints)).first()

    return None


def handle_existing_entry(  # noqa: PLR0913
    existing,  # noqa: ANN001
    TableModel,  # noqa: N803, ANN001
    data: dict[str, Any],
    pk_columns: list[str],
    inspector: inspect,
    if_exists: conflict_actions,
    session: Optional[Session],
):
    """
    Handle update logic for an existing database entry based on if_exists policy.

    Args:
    ----
        existing: The existing SQLAlchemy instance
        TableModel: The SQLAlchemy table class
        data: Dictionary of input data
        pk_columns: List of primary key column names
        inspector: SQLAlchemy inspector for the table
        if_exists: Conflict resolution strategy: 'update', 'replace', 'ignore', or 'error'
        session: SQLAlchemy session

    Raises:
    ------
        ValueError: If conflict policy is 'error' and entry exists

    """
    logger.debug(f"Existing entry: {existing.to_dict()}")
    logger.debug(f"{data=}")

    new_thing = TableModel(**data)
    if hasattr(new_thing, "resolve_references"):
        new_thing.resolve_references(session=session)

    if if_exists == "error":
        raise ValueError(f"Entry exists with PK: {[data[pk] for pk in pk_columns]}")

    if if_exists == "ignore":
        logger.info(f"Skipping existing entry with PK: {[data[pk] for pk in pk_columns]}")
        return

    for col in inspector.columns.values():
        if col.key in pk_columns:
            continue

        current_value = getattr(existing, col.key)
        new_value = getattr(new_thing, col.key)

        if if_exists == "replace" and (new_value is not None or col.key in data):
            logger.debug(f"Replacing {col.key}: {current_value} -> {new_value}")
            setattr(existing, col.key, new_value)
        elif if_exists == "update" and current_value is None and new_value is not None:
            logger.debug(f"Updating {col.key} to {new_value}")
            setattr(existing, col.key, new_value)


@route_or_direct("load_time_data", send_file=True)
def load_time_data(probe_key: ProbeKey, data: pd.DataFrame, session: Optional[Session] = None):
    """Load time series data"""
    route_to_backend = ENV_VARS.ROUTE_TO_BACKEND.get_value()
    if route_to_backend:
        csv_data = data.to_csv(index=False).encode("utf-8")
        return {
            "data": {"probe_key_str": json.dumps(probe_key.model_dump())},
            "files": {"file": ("time_data.csv", csv_data, "text/csv")},
        }

    from opensampl.db.orm import ProbeData, ProbeMetadata

    try:
        # Verify probe exists and get UUID
        probe = (
            session.query(ProbeMetadata)
            .filter(
                ProbeMetadata.probe_id == probe_key.probe_id,
                ProbeMetadata.ip_address == probe_key.ip_address,
            )
            .first()
        )

        if not probe:
            raise ValueError(f"Probe with key {probe_key} not found")  # noqa: TRY301

        df = data[["time", "value"]].copy()  # Only keep required columns.
        df["probe_uuid"] = probe.uuid

        # Ensure correct dtypes
        df = df.astype({"time": "datetime64[ns]", "value": "float64", "probe_uuid": str})

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
    except Exception as e:
        session.rollback()
        logger.error(f"Error loading time data: {e}")
        raise


@route_or_direct("load_probe_metadata")
def load_probe_metadata(
    vendor: VendorType,
    probe_key: ProbeKey,
    data: dict[str, Any],
    session: Optional[Session] = None,
):
    """Write object to table"""
    route_to_backend = ENV_VARS.ROUTE_TO_BACKEND.get_value()
    if route_to_backend:
        return {
            "vendor": vendor.model_dump(),
            "probe_key": probe_key.model_dump(),
            "data": data,
        }

    try:
        from opensampl.db.orm import ProbeMetadata

        probe = (
            session.query(ProbeMetadata)
            .filter(ProbeMetadata.probe_id == probe_key.probe_id, ProbeMetadata.ip_address == probe_key.ip_address)
            .first()
        )
        logger.debug(f"{probe=}")
        if not probe:
            probe = ProbeMetadata(
                probe_id=probe_key.probe_id,
                ip_address=probe_key.ip_address,
                vendor=vendor.name,
            )
            session.add(probe)
            session.flush()
        data["probe_uuid"] = probe.uuid

        write_to_table(table=vendor.metadata_table, data=data, session=session, if_exists="update")

        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error writing to table: {e}")
        raise


@route_or_direct("create_new_tables", method="GET")
def create_new_tables(create_schema: bool = True, session: Optional[Session] = None):
    """Use the ORM definition to create all tables, optionally creating the schema as well"""
    route_to_backend = ENV_VARS.ROUTE_TO_BACKEND.get_value()
    if route_to_backend:
        return {"create_schema": create_schema}
    try:
        if create_schema:
            session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {Base.metadata.schema}"))
            session.commit()
        Base.metadata.create_all(session.bind)
    except Exception as e:
        session.rollback()
        logger.error(f"Error writing to table: {e}")
        raise
