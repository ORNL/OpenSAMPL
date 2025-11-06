import io
import json
import os
import sys
import time
from typing import Any, Dict, Callable, Optional
from datetime import datetime, timedelta
import pandas as pd
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Request, Response, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import create_engine, text, select, or_, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import sessionmaker, Session
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from opensampl.db.access_orm import APIAccessKey
from opensampl import load_data
from opensampl.db.orm import ProbeMetadata
from opensampl.vendors.constants import VendorType, ProbeKey
from opensampl.metrics import METRICS, MetricType
from opensampl.references import REF_TYPES, CompoundReferenceType, ReferenceType
import psycopg2

class TimeDataPoint(BaseModel):
    time: str
    value: float


class WriteTablePayload(BaseModel):
    table: str
    data: Dict[str, Any]
    if_exists: load_data.conflict_actions = 'update'


class ProbeMetadataPayload(BaseModel):
    vendor: VendorType
    probe_key: ProbeKey
    data: Dict[str, Any]


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
    env_keys = os.getenv('API_KEYS', '').strip()
    keys = [k.strip() for k in env_keys.split(',') if k.strip()]
    if keys:
        logger.debug("api access keys loaded from env")
        return keys
    try:
        Session = sessionmaker(bind=engine)
        with Session() as session:
            now = datetime.utcnow()
            stmt = select(APIAccessKey.key).where(
                or_(
                    APIAccessKey.expires_at == None,
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
    if not USE_API_KEY:
        return  # Security is disabled
    if api_key not in get_keys():
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key

def get_db():
    Session = sessionmaker(bind=engine)
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
    return RedirectResponse(url='/docs')


@app.get("/setloglevel")
def set_log_level(newloglevel: str, api_key: str = Depends(validate_api_key)):
    """
    change visible log level in backend container
    """
    newloglevel = newloglevel.upper()
    logger.configure(handlers=[{"sink": sys.stderr, "level": newloglevel}])
    return {"loglevel": newloglevel}


@app.get("/checkloglevel")
def check_log_level(api_key: str = Depends(validate_api_key)):
    """
    This is to check which log levels are visible in backend container
    """
    logger.debug('Debug test')
    logger.info('Info test')
    logger.warning('Warning test')
    logger.error('Error test')
    current_level = list(logger._core.handlers.values())[0]["level"].name
    return {"loglevel": current_level}


@app.post("/write_to_table")
def write_to_table(payload: WriteTablePayload, api_key: str = Depends(validate_api_key), session: Session = Depends(get_db)):
    try:
        load_data.write_to_table(table=payload.table, data=payload.data, if_exists=payload.if_exists, session=session)
        logger.debug(f'Successfully wrote to {payload.table} using: {payload.data}')
        return JSONResponse(content={"message": f"Succeeded loading data into {payload.table}"}, status_code=200)
    except IntegrityError as e:
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            return JSONResponse(content={"message": f"Unique violation error: {e}"}, status_code=409)
        return JSONResponse(content={"message": f"Integrity error: {e}"}, status_code=500)
    except SQLAlchemyError as e:
        logger.error(f'SQLAlchemy error: {e}')
        return JSONResponse(content={"message": f"Database error: {e}"}, status_code=500)
    except json.JSONDecodeError as e:
        logger.error(f'JSON decode error: {e}')
        return JSONResponse(content={"message": f"Invalid JSON data: {e}"}, status_code=400)
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        return JSONResponse(content={"message": f"Failed to load JSON into database: {e}"}, status_code=500)


@app.post("/load_time_data")
async def load_time_data(probe_key_str: str = Form(...),
                        metric_type_str: Optional[str] = Form(None),
                        reference_type_str: Optional[str] = Form(None),
                        compound_key_str: Optional[str] = Form(None),
                         file: UploadFile = File(...),
                         api_key: str = Depends(validate_api_key),
                         session: Session = Depends(get_db)):
    try:

        probe_key = ProbeKey(**json.loads(probe_key_str))

        if metric_type_str is not None:
            metric_type_dict = json.loads(metric_type_str)
            metric_type = MetricType(**metric_type_dict)
        else:
            metric_type = METRICS.UNKNOWN

        if reference_type_str is not None:
            reference_type_dict = json.loads(reference_type_str)
            if 'reference_table' in reference_type_dict:
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
        df['time'] = pd.to_datetime(df['time'])

        # Convert value strings back to float64
        # df['value'] = df['value'].astype('float64')

        # Use the same load_time_data function as before
        load_data.load_time_data(
            probe_key=probe_key,
            metric_type=metric_type,
            reference_type=reference_type,
            compound_key=compound_key,
            data=df,
            session=session
        )

        return JSONResponse(
            content={"message": f"Successfully loaded {len(df)} data points"},
            status_code=200
        )
    except IntegrityError as e:
        if session:
            session.rollback()
            session.close()
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            return JSONResponse(content={"message": f"Unique violation error: {e}"}, status_code=409)
        return JSONResponse(content={"message": f"Integrity error: {e}"}, status_code=500)
    except SQLAlchemyError as e:
        logger.error(f'Database error: {e}')
        if session:
            session.rollback()
            session.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        if session:
            session.rollback()
            session.close()
        raise HTTPException(status_code=500, detail=f"Error processing time series data: {str(e)}")


@app.post("/load_probe_metadata")
def load_probe_metadata(payload: ProbeMetadataPayload, api_key: str = Depends(validate_api_key), session: Session = Depends(get_db)):
    logger.debug(f"Received payload: {payload.model_dump()}")

    try:
        load_data.load_probe_metadata(vendor=payload.vendor, probe_key=payload.probe_key, data=payload.data,
                                      session=session)
        logger.debug(
            f'Successfully wrote to {ProbeMetadata.__tablename__} and {payload.vendor.metadata_table}: {payload.data}')
        return JSONResponse(content={"message": f"Succeeded loaded metadata for {payload.probe_key}"}, status_code=200)
    except IntegrityError as e:
        session.rollback()
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            return JSONResponse(content={"message": f"Unique violation error: {e}"}, status_code=409)
        return JSONResponse(content={"message": f"Integrity error: {e}"}, status_code=500)
    except SQLAlchemyError as e:
        logger.error(f'SQLAlchemy error: {e}')
        return JSONResponse(content={"message": f"Database error: {e}"}, status_code=500)
    except json.JSONDecodeError as e:
        logger.error(f'JSON decode error: {e}')
        return JSONResponse(content={"message": f"Invalid JSON data: {e}"}, status_code=400)
    except Exception as e:
        logger.exception(f'Unexpected error: {e}')
        return JSONResponse(content={"message": f"Failed to load JSON into database: {e}"}, status_code=500)


@app.get("/create_new_tables")
def create_new_tables(create_schema: bool = True, api_key: str = Depends(validate_api_key), session: Session = Depends(get_db)):
    try:
        load_data.create_new_tables(create_schema=create_schema, session=session)
        return JSONResponse(content={"message": f"Succeeded in creating any new tables"}, status_code=200)
    except SQLAlchemyError as e:
        logger.error(f'SQLAlchemy error: {e}')
        return JSONResponse(content={"message": f"Database error: {e}"}, status_code=500)
    except json.JSONDecodeError as e:
        logger.error(f'JSON decode error: {e}')
        return JSONResponse(content={"message": f"Invalid JSON data: {e}"}, status_code=400)
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        return JSONResponse(content={"message": f"Failed to load JSON into database: {e}"}, status_code=500)


@app.get("/gen_api_key")
def generate_api_key(expire_after: Optional[int] = None, session: Session = Depends(get_db)):
    try:

        new_key = APIAccessKey()
        new_key.generate_key()
        if expire_after:
            new_key.expires_at = datetime.utcnow() + timedelta(days=expire_after)

        session.add(new_key)

        session.commit()
        return JSONResponse(content={"message": f"Succeeded in creating new access key"}, status_code=200)
    except SQLAlchemyError as e:
        logger.error(f'SQLAlchemy error: {e}')
        return JSONResponse(content={"message": f"Database error: {e}"}, status_code=500)
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        return JSONResponse(content={"message": f"Failed to create new access key: {e}"}, status_code=500)


@app.get("/healthcheck")
def healthcheck():
    return {"status": "OK"}

@app.get("/healthcheck_database")
def healthcheck_db():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "OK"}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database connection error")


@app.get("/healthcheck_metadata")
def healthcheck_metadata():
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'castdb';"))
            schema_exists = result.fetchone() is not None
        if schema_exists:
            return {"status": "OK"}
        else:
            raise HTTPException(status_code=500, detail="Schema 'castdb' does not exist")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database connection error: {str(e)}")


@app.get("/metrics", include_in_schema=False)
def metrics():
    """
    Expose Prometheus metrics.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)