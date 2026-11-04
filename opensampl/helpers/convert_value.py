"""Backfill numeric probe values after the probe-data type migration."""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import click
from loguru import logger
from sqlalchemy import create_engine, text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from sqlalchemy import Engine

DEFAULT_BATCH_SIZE = "1d"
_DURATION_PATTERN = re.compile(r"^(?P<value>(?:\d+(?:\.\d*)?|\.\d+))(?P<unit>[mhdw])$", re.IGNORECASE)
_DURATION_SECONDS = {
    "m": 60,
    "h": 60 * 60,
    "d": 24 * 60 * 60,
    "w": 7 * 24 * 60 * 60,
}

METRIC_TYPES_SQL = text("""
    SELECT uuid
    FROM castdb.metric_type
    WHERE value_type IN ('float', 'int')
""")

SCHEMA_COLUMNS_SQL = text("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'castdb'
      AND table_name = 'probe_data'
      AND column_name IN ('value_jsonb', 'value_float')
""")

RANGE_SQL = text("""
    SELECT
        min(pd.time) AS start_time,
        max(pd.time) AS end_time
    FROM castdb.probe_data pd
    WHERE pd.metric_type_uuid = ANY(:metric_type_uuids)
      AND pd.value_float IS NULL
      AND pd.value_jsonb IS NOT NULL
""")

UPDATE_SQL = text("""
    UPDATE castdb.probe_data
    SET value_float = (value_jsonb #>> '{}')::double precision
    WHERE metric_type_uuid = ANY(:metric_type_uuids)
      AND value_float IS NULL
      AND value_jsonb IS NOT NULL
      AND time >= :start_time
      AND time < :end_time
""")


def parse_duration(value: str) -> timedelta:
    """Parse a positive duration expressed in minutes, hours, days, or weeks."""
    match = _DURATION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise click.BadParameter("must be a positive duration such as 30m, 12h, 1d, or 2w")

    seconds = float(match.group("value")) * _DURATION_SECONDS[match.group("unit").lower()]
    if seconds <= 0:
        raise click.BadParameter("must be greater than zero")
    return timedelta(seconds=seconds)


def resolve_workers(workers: int | None) -> int:
    """Resolve worker count from the option, environment, or local CPU count."""
    if workers is not None:
        return workers

    env_workers = os.getenv("WORKERS")
    if env_workers is not None:
        try:
            resolved = int(env_workers)
        except ValueError as exc:
            raise click.BadParameter("WORKERS must be a positive integer", param_hint="--workers") from exc
        if resolved <= 0:
            raise click.BadParameter("WORKERS must be a positive integer", param_hint="--workers")
        return resolved

    return os.cpu_count() or 4


def build_windows(
    start_time: datetime,
    end_time: datetime,
    batch_size: timedelta,
) -> list[tuple[datetime, datetime]]:
    """Build newest-first half-open time windows that include the final row."""
    end_exclusive = end_time + timedelta(microseconds=1)
    windows: list[tuple[datetime, datetime]] = []
    current_start = start_time
    while current_start < end_exclusive:
        current_end = min(current_start + batch_size, end_exclusive)
        windows.append((current_start, current_end))
        current_start = current_end
    windows.reverse()
    return windows


def _validate_schema(engine: Engine) -> None:
    """Ensure the value-type migration has created both required columns."""
    with engine.connect() as conn:
        columns = set(conn.execute(SCHEMA_COLUMNS_SQL).scalars().all())
    missing = {"value_jsonb", "value_float"} - columns
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise RuntimeError(
            f"The probe-data type migration has not been applied; missing castdb.probe_data column(s): {missing_names}"
        )


def _iter_waves(
    windows: list[tuple[datetime, datetime]],
    vacuum_every_batches: int,
) -> Iterable[list[tuple[datetime, datetime]]]:
    """Split windows at vacuum boundaries, or return one wave when disabled."""
    wave_size = vacuum_every_batches or len(windows)
    for index in range(0, len(windows), wave_size):
        yield windows[index : index + wave_size]


def run_backfill(
    database_url: str,
    workers: int,
    batch_size: timedelta,
    vacuum_every_batches: int,
    *,
    engine_factory: Callable[..., Engine] | None = None,
) -> int:
    """Backfill numeric values and return the number of rows updated."""
    factory = engine_factory or create_engine
    engine = factory(database_url, pool_size=workers + 1)
    logger.info("Using database: {}", engine.url)
    logger.info("Workers: {}", workers)

    try:
        _validate_schema(engine)
        with engine.connect() as conn:
            metric_type_uuids = conn.execute(METRIC_TYPES_SQL).scalars().all()

        if not metric_type_uuids:
            logger.info("No float/int metric types found; nothing to map.")
            return 0

        with engine.connect() as conn:
            time_range = conn.execute(
                RANGE_SQL,
                {"metric_type_uuids": metric_type_uuids},
            ).one()

        if time_range.start_time is None or time_range.end_time is None:
            logger.info("No values require backfilling.")
            return 0

        windows = build_windows(time_range.start_time, time_range.end_time, batch_size)
        logger.info("Backfilling values from {} through {}", time_range.start_time, time_range.end_time)

        def run_batch(window: tuple[datetime, datetime]) -> int:
            batch_start, batch_end = window
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL synchronous_commit = off"))
                result = conn.execute(
                    UPDATE_SQL,
                    {
                        "metric_type_uuids": metric_type_uuids,
                        "start_time": batch_start,
                        "end_time": batch_end,
                    },
                )
            logger.info("{} -> {}: committed {:,} rows", batch_start, batch_end, result.rowcount)
            return result.rowcount

        total_updated = 0
        vacuum_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for wave in _iter_waves(windows, vacuum_every_batches):
                total_updated += sum(pool.map(run_batch, wave))
                logger.info("Vacuuming probe_data...")
                with vacuum_engine.connect() as conn:
                    conn.execute(text("VACUUM castdb.probe_data"))

        logger.info("Value backfill complete; updated {:,} rows.", total_updated)
        return total_updated
    finally:
        engine.dispose()


@click.command("value-backfill")
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=None,
    help="Parallel database workers. Defaults to WORKERS or the local CPU count.",
)
@click.option(
    "--batch-size",
    type=str,
    default=DEFAULT_BATCH_SIZE,
    show_default=True,
    metavar="DURATION",
    help="Time span per batch, using m, h, d, or w units.",
)
@click.option(
    "--vacuum-every-batches",
    type=click.IntRange(min=0),
    default=None,
    metavar="INTEGER",
    help="Vacuum after this many batches; defaults to workers * 2. Use 0 for only a final vacuum.",
)
@click.pass_obj
def value_backfill(
    obj: dict[str, Any],
    workers: int | None,
    batch_size: str,
    vacuum_every_batches: int | None,
) -> None:
    """Map numeric JSON values into the optimized floating-point column."""
    config = obj["conf"]
    if config.ROUTE_TO_BACKEND:
        click.echo(
            "Warning: value-backfill requires a direct database connection and cannot run when ROUTE_TO_BACKEND=true.",
            err=True,
        )
        raise click.UsageError("Disable ROUTE_TO_BACKEND before running this command.")
    if not config.DATABASE_URL:
        raise click.UsageError("DATABASE_URL must be configured to run value-backfill.")

    resolved_workers = resolve_workers(workers)
    resolved_batch_size = parse_duration(batch_size)
    resolved_vacuum_cadence = resolved_workers * 2 if vacuum_every_batches is None else vacuum_every_batches

    try:
        run_backfill(
            config.DATABASE_URL,
            resolved_workers,
            resolved_batch_size,
            resolved_vacuum_cadence,
        )
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Value backfill failed: {exc}") from exc
