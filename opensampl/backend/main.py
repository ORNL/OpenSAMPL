"""FastAPI backend exposing OpenSAMPL database loading and health endpoints."""

import io
import json
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import psycopg2
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, Security, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security.api_key import APIKeyHeader
from loguru import logger
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from sqlalchemy import create_engine, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from opensampl import load_data
from opensampl.db.access_orm import APIAccessKey
from opensampl.db.orm import ProbeMetadata
from opensampl.metrics import METRICS, MetricType
from opensampl.references import REF_TYPES, CompoundReferenceType, ReferenceType
from opensampl.vendors.constants import ProbeKey, VendorType


class TimeDataPoint(BaseModel):
    """A single time/value sample."""

    time: str
    value: float


class WriteTablePayload(BaseModel):
    """Payload for writing a row to a table."""

    table: str
    data: dict[str, Any]
    if_exists: load_data.conflict_actions = "update"


class ProbeMetadataPayload(BaseModel):
    """Payload for loading probe metadata."""

    vendor: VendorType
    probe_key: ProbeKey
    data: dict[str, Any]


DATABASE_URI = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URI)

loglevel = os.getenv("BACKEND_LOG_LEVEL", "INFO")
app = FastAPI()


REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests in seconds",
    ["method", "endpoint"]
)

EXCLUDED_PATHS = {"/metrics", "/healthcheck", "/healthcheck_database", "/healthcheck_metadata"}

logger.configure(handlers=[{"sink": sys.stderr, "level": loglevel}])

USE_API_KEY = os.getenv("USE_API_KEY", "false").lower() == "true"
API_KEY_NAME = "access-key"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_keys():
    """Return the valid API keys from the environment, falling back to the database."""
    env_keys = os.getenv("API_KEYS", "").strip()
    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    if keys:
        logger.debug("api access keys loaded from env")
        return keys
    try:
        session_factory = sessionmaker(bind=engine)
        with session_factory() as session:
            now = datetime.now(tz=UTC).replace(tzinfo=None)
            stmt = select(APIAccessKey.key).where(
                or_(
                    APIAccessKey.expires_at.is_(None),
                    APIAccessKey.expires_at > now
                )
            )
            result = session.execute(stmt)
            keys = [row[0] for row in result.all()]
            logger.debug("api access keys loaded from db")
            return keys
    except Exception as e:
        logger.debug(f"exception attempting to load api access keys from db: {e}")
        return []

def validate_api_key(api_key: str = Security(api_key_header)):
    """Validate the request API key when API key security is enabled."""
    if not USE_API_KEY:
        return None  # Security is disabled
    if api_key not in get_keys():
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key

def get_db():
    """Yield a database session and close it afterwards."""
    session_factory = sessionmaker(bind=engine)
    session = None
    try:
        session = session_factory()
        yield session
    finally:
        if session is not None:
            session.close()

@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """Middleware to track request metrics."""
    if request.url.path in EXCLUDED_PATHS:
        return await call_next(request)
    start_time = time.time()
    response: Response = await call_next(request)
    duration = time.time() - start_time

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        http_status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response


# add route to docs from / to /docs
@app.get("/", include_in_schema=False)
async def docs_redirect():
    """Redirect the root path to the API docs."""
    return RedirectResponse(url="/docs")


@app.get("/setloglevel")
def set_log_level(newloglevel: str, api_key: str = Depends(validate_api_key)):
    """Change visible log level in backend container"""
    newloglevel = newloglevel.upper()
    logger.configure(handlers=[{"sink": sys.stderr, "level": newloglevel}])
    return {"loglevel": newloglevel}


@app.get("/checkloglevel")
def check_log_level(api_key: str = Depends(validate_api_key)):
    """Report which log level is currently visible in the backend container."""
    logger.debug("Debug test")
    logger.info("Info test")
    logger.warning("Warning test")
    logger.error("Error test")
    current_level = next(iter(logger._core.handlers.values()))["level"].name  # noqa: SLF001
    return {"loglevel": current_level}


@app.post("/write_to_table")
def write_to_table(
    payload: WriteTablePayload, api_key: str = Depends(validate_api_key), session: Session = Depends(get_db)
):
    """Write a row of data to the given table."""
    try:
        load_data.write_to_table(table=payload.table, data=payload.data, if_exists=payload.if_exists, session=session)
        logger.debug(f"Successfully wrote to {payload.table} using: {payload.data}")
        return JSONResponse(content={"message": f"Succeeded loading data into {payload.table}"}, status_code=200)
    except IntegrityError as e:
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            return JSONResponse(content={"message": f"Unique violation error: {e}"}, status_code=409)
        return JSONResponse(content={"message": f"Integrity error: {e}"}, status_code=500)
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error: {e}")
        return JSONResponse(content={"message": f"Database error: {e}"}, status_code=500)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return JSONResponse(content={"message": f"Invalid JSON data: {e}"}, status_code=400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JSONResponse(content={"message": f"Failed to load JSON into database: {e}"}, status_code=500)


def _parse_metric_type(metric_type_str: str | None) -> MetricType:
    if metric_type_str is None:
        return METRICS.UNKNOWN
    return MetricType(**json.loads(metric_type_str))


def _parse_reference_type(reference_type_str: str | None) -> ReferenceType | CompoundReferenceType:
    if reference_type_str is None:
        return REF_TYPES.UNKNOWN
    reference_type_dict = json.loads(reference_type_str)
    if "reference_table" in reference_type_dict:
        return CompoundReferenceType(**reference_type_dict)
    return ReferenceType(**reference_type_dict)


def _discard_session(session: Session | None) -> None:
    if session:
        session.rollback()
        session.close()


@app.post("/load_time_data")
async def load_time_data(
    probe_key_str: str = Form(...),
    metric_type_str: str | None = Form(None),
    reference_type_str: str | None = Form(None),
    compound_key_str: str | None = Form(None),
    file: UploadFile = File(...),
    api_key: str = Depends(validate_api_key),
    session: Session = Depends(get_db),
):
    """Load a CSV of time series data for a probe."""
    try:
        probe_key = ProbeKey(**json.loads(probe_key_str))
        metric_type = _parse_metric_type(metric_type_str)
        reference_type = _parse_reference_type(reference_type_str)
        compound_key = None if compound_key_str is None else json.loads(compound_key_str)

        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        logger.info(df.head())
        # Convert time strings back to datetime
        df["time"] = pd.to_datetime(df["time"])

        load_data.load_time_data(
            probe_key=probe_key,
            metric_type=metric_type,
            reference_type=reference_type,
            compound_key=compound_key,
            data=df,
            session=session,
        )

        return JSONResponse(content={"message": f"Successfully loaded {len(df)} data points"}, status_code=200)
    except IntegrityError as e:
        _discard_session(session)
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            return JSONResponse(content={"message": f"Unique violation error: {e}"}, status_code=409)
        return JSONResponse(content={"message": f"Integrity error: {e}"}, status_code=500)
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        _discard_session(session)
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}") from e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        _discard_session(session)
        raise HTTPException(status_code=500, detail=f"Error processing time series data: {e!s}") from e


@app.post("/load_probe_metadata")
def load_probe_metadata(
    payload: ProbeMetadataPayload, api_key: str = Depends(validate_api_key), session: Session = Depends(get_db)
):
    """Load metadata for a probe."""
    logger.debug(f"Received payload: {payload.model_dump()}")

    try:
        load_data.load_probe_metadata(vendor=payload.vendor, probe_key=payload.probe_key, data=payload.data,
                                      session=session)
        logger.debug(
            f"Successfully wrote to {ProbeMetadata.__tablename__} and {payload.vendor.metadata_table}: {payload.data}")
        return JSONResponse(content={"message": f"Succeeded loaded metadata for {payload.probe_key}"}, status_code=200)
    except IntegrityError as e:
        session.rollback()
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            return JSONResponse(content={"message": f"Unique violation error: {e}"}, status_code=409)
        return JSONResponse(content={"message": f"Integrity error: {e}"}, status_code=500)
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error: {e}")
        return JSONResponse(content={"message": f"Database error: {e}"}, status_code=500)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return JSONResponse(content={"message": f"Invalid JSON data: {e}"}, status_code=400)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return JSONResponse(content={"message": f"Failed to load JSON into database: {e}"}, status_code=500)


@app.get("/create_new_tables")
def create_new_tables(
    create_schema: bool = True, api_key: str = Depends(validate_api_key), session: Session = Depends(get_db)
):
    """Create any tables that do not yet exist."""
    try:
        load_data.create_new_tables(create_schema=create_schema, session=session)
        return JSONResponse(content={"message": "Succeeded in creating any new tables"}, status_code=200)
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error: {e}")
        return JSONResponse(content={"message": f"Database error: {e}"}, status_code=500)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return JSONResponse(content={"message": f"Invalid JSON data: {e}"}, status_code=400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JSONResponse(content={"message": f"Failed to load JSON into database: {e}"}, status_code=500)


@app.get("/gen_api_key")
def generate_api_key(expire_after: int | None = None, session: Session = Depends(get_db)):
    """Generate a new API access key, optionally expiring after the given number of days."""
    try:
        new_key = APIAccessKey()
        new_key.generate_key()
        if expire_after:
            new_key.expires_at = datetime.now(tz=UTC).replace(tzinfo=None) + timedelta(days=expire_after)

        session.add(new_key)

        session.commit()
        return JSONResponse(content={"message": "Succeeded in creating new access key"}, status_code=200)
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error: {e}")
        return JSONResponse(content={"message": f"Database error: {e}"}, status_code=500)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JSONResponse(content={"message": f"Failed to create new access key: {e}"}, status_code=500)


@app.get("/healthcheck")
def healthcheck():
    """Report that the service is up."""
    return {"status": "OK"}

@app.get("/healthcheck_database")
def healthcheck_db():
    """Report whether the database is reachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail="Database connection error") from e
    else:
        return {"status": "OK"}


@app.get("/healthcheck_metadata")
def healthcheck_metadata():
    """Report whether the castdb schema exists."""
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'castdb';"))
            schema_exists = result.fetchone() is not None
        if schema_exists:
            return {"status": "OK"}
        raise HTTPException(status_code=500, detail="Schema 'castdb' does not exist")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database connection error: {e!s}") from e


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
