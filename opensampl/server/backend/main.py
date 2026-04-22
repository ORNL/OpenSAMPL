"""API Configuration to Indirectly interact with the database"""

import io
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Optional

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
    """Time Data Model"""

    time: str
    value: float


class WriteTablePayload(BaseModel):
    """Write Table Payload Model"""

    table: str
    data: dict[str, Any]
    if_exists: load_data.conflict_actions = "update"


class ProbeMetadataPayload(BaseModel):
    """Probe Metadata Payload Model"""

    vendor: VendorType
    probe_key: ProbeKey
    data: dict[str, Any]


DATABASE_URI = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URI)

loglevel = os.getenv("BACKEND_LOG_LEVEL", "INFO")
app = FastAPI(
    title="openSAMPL Backend",
    description="""
    The backend for interacting with openSAMPL server

    Provides additional security and durability for loading data and interacting with database.
    """,
)


REQUEST_COUNT = Counter("http_requests_total", "Total number of HTTP requests", ["method", "endpoint", "http_status"])

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "Duration of HTTP requests in seconds", ["method", "endpoint"]
)

EXCLUDED_PATHS = {"/metrics", "/healthcheck", "/healthcheck_database", "/healthcheck_metadata"}

logger.configure(handlers=[{"sink": sys.stderr, "level": loglevel}])

USE_API_KEY = os.getenv("USE_API_KEY", "false").lower() == "true"
API_KEY_NAME = "access-key"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_keys():
    """Get active API keys"""
    env_keys = os.getenv("API_KEYS", "").strip()
    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    if keys:
        logger.debug("api access keys loaded from env")
        return keys
    try:
        Session = sessionmaker(bind=engine)  # noqa: N806
        with Session() as session:
            now = datetime.now(tz=UTC)
            stmt = select(APIAccessKey.key).where(or_(APIAccessKey.expires_at is None, APIAccessKey.expires_at > now))
            result = session.execute(stmt)
            keys = [row[0] for row in result.all()]
            logger.debug("api access keys loaded from db")
            return keys
    except Exception as e:
        logger.debug(f"exception attempting to load api access keys from db: {e}")
        return []


def validate_api_key(api_key: str = Security(api_key_header)):
    """Validate provided API key"""
    if not USE_API_KEY:
        return None  # Security is disabled
    if api_key not in get_keys():
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


def validate_api_key_or_allow_bootstrap(api_key: str = Security(api_key_header)):
    """Require an existing API key unless none have been provisioned yet."""
    if not USE_API_KEY:
        return None

    keys = get_keys()
    if not keys:
        logger.warning("No API keys configured; allowing bootstrap API key generation")
        return None

    if api_key not in keys:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


def get_db():
    """Get database session"""
    Session = sessionmaker(bind=engine)  # noqa: N806
    try:
        session = Session()
        yield session
    finally:
        session.close()


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """Middleware to track request metrics."""
    if request.url.path in EXCLUDED_PATHS:
        return await call_next(request)
    start_time = time.time()
    response: Response = await call_next(request)
    duration = time.time() - start_time

    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, http_status=response.status_code).inc()

    REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(duration)

    return response


# add route to docs from / to /docs
@app.get("/", include_in_schema=False)
async def docs_redirect():
    """Redirect bare url to docs"""
    return RedirectResponse(url="/docs")


@app.get("/setloglevel")
def set_log_level(newloglevel: str, api_key: str = Depends(validate_api_key)):
    """Change visible log level in backend container"""
    newloglevel = newloglevel.upper()
    logger.configure(handlers=[{"sink": sys.stderr, "level": newloglevel}])
    return {"loglevel": newloglevel}


@app.get("/checkloglevel")
def check_log_level(api_key: str = Depends(validate_api_key)):
    """Check which log levels are visible in backend container"""
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
    """Write given data to specified table"""
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


@app.post("/load_time_data")
async def load_time_data(  # noqa: PLR0912, C901
    probe_key_str: str = Form(...),
    metric_type_str: Optional[str] = Form(None),
    reference_type_str: Optional[str] = Form(None),
    compound_key_str: Optional[str] = Form(None),
    file: UploadFile = File(...),
    api_key: str = Depends(validate_api_key),
    session: Session = Depends(get_db),
):
    """Load provided data for given probe"""
    try:
        probe_key = ProbeKey(**json.loads(probe_key_str))

        if metric_type_str is not None:
            metric_type_dict = json.loads(metric_type_str)
            metric_type = MetricType(**metric_type_dict)
        else:
            metric_type = METRICS.UNKNOWN

        if reference_type_str is not None:
            reference_type_dict = json.loads(reference_type_str)
            if "reference_table" in reference_type_dict:
                reference_type = CompoundReferenceType(**reference_type_dict)
            else:
                reference_type = ReferenceType(**reference_type_dict)
        else:
            reference_type = REF_TYPES.UNKNOWN

        compound_key = None if compound_key_str is None else json.loads(compound_key_str)

        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        logger.info(df.head())
        # Convert time strings back to datetime
        df["time"] = pd.to_datetime(df["time"])

        # Use the same load_time_data function as before
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
        if session:
            session.rollback()
            session.close()
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            return JSONResponse(content={"message": f"Unique violation error: {e}"}, status_code=409)
        return JSONResponse(content={"message": f"Integrity error: {e}"}, status_code=500)
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        if session:
            session.rollback()
            session.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}") from e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if session:
            session.rollback()
            session.close()
        raise HTTPException(status_code=500, detail=f"Error processing time series data: {e!s}") from e


@app.post("/load_probe_metadata")
def load_probe_metadata(
    payload: ProbeMetadataPayload, api_key: str = Depends(validate_api_key), session: Session = Depends(get_db)
):
    """Load metadata for given probe"""
    logger.debug(f"Received payload: {payload.model_dump()}")

    try:
        load_data.load_probe_metadata(
            vendor=payload.vendor, probe_key=payload.probe_key, data=payload.data, session=session
        )
        logger.debug(
            f"Successfully wrote to {ProbeMetadata.__tablename__} and {payload.vendor.metadata_table}: {payload.data}"
        )
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
    """Update DB based on ORM Tables"""
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
def generate_api_key(
    expire_after: Optional[int] = None,
    api_key: str = Depends(validate_api_key_or_allow_bootstrap),
    session: Session = Depends(get_db),
):
    """Generate new API key in the database"""
    try:
        new_key = APIAccessKey()
        new_key.generate_key()
        if expire_after:
            new_key.expires_at = datetime.now(tz=UTC) + timedelta(days=expire_after)

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
    """Ensure the api is accepting queries"""
    return {"status": "OK"}


@app.get("/healthcheck_database")
def healthcheck_db():
    """Ensure the db is accepting connections"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        return JSONResponse(content={"message": f"Database connection error: {e!s}"}, status_code=503)
    else:
        return {"status": "OK"}


@app.get("/healthcheck_metadata")
def healthcheck_metadata():
    """Ensure that the database exists AND the expected format is present"""
    # eventually, we want to make the schema configurable through environment variables
    # for now, we have it hard coded too many places. So this is a small step towards that goal
    SCHEMA = "castdb"  # noqa: N806

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema;"),
                {"schema": SCHEMA},
            )
            schema_exists = result.fetchone() is not None
        if schema_exists:
            return {"status": "OK"}
        return JSONResponse(status_code=500, content={"message": f"Expected schema '{SCHEMA}' does not exist"})
    except SQLAlchemyError as e:
        return JSONResponse(content={"message": f"Database connection error: {e!s}"}, status_code=503)


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
