"""Tests for the numeric value maintenance backfill."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import click
import pytest
from click.testing import CliRunner

from opensampl.cli import cli
from opensampl.helpers.convert_value import build_windows, parse_duration, resolve_workers, run_backfill


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30m", timedelta(minutes=30)),
        ("12h", timedelta(hours=12)),
        ("1d", timedelta(days=1)),
        ("2w", timedelta(weeks=2)),
        ("1.5h", timedelta(minutes=90)),
    ],
)
def test_parse_duration(value, expected):
    """Supported duration units are converted to timedeltas."""
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", ["", "0h", "-1d", "1", "tomorrow"])
def test_parse_duration_rejects_invalid_values(value):
    """Invalid and nonpositive durations are rejected."""
    with pytest.raises(click.BadParameter):
        parse_duration(value)


def test_resolve_workers_prefers_argument(monkeypatch):
    """An explicit worker count takes precedence over the environment."""
    monkeypatch.setenv("WORKERS", "9")

    assert resolve_workers(3) == 3


def test_resolve_workers_uses_environment(monkeypatch):
    """WORKERS supplies the default when the option is omitted."""
    monkeypatch.setenv("WORKERS", "7")

    assert resolve_workers(None) == 7


def test_build_windows_is_newest_first_and_includes_end():
    """Batch windows are returned newest-first with an exclusive final bound."""
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 3)

    windows = build_windows(start, end, timedelta(days=1))

    assert windows == [
        (datetime(2026, 1, 3), datetime(2026, 1, 3, 0, 0, 0, 1)),
        (datetime(2026, 1, 2), datetime(2026, 1, 3)),
        (datetime(2026, 1, 1), datetime(2026, 1, 2)),
    ]


def test_route_to_backend_warns_and_aborts_before_connecting(tmp_path):
    """The maintenance operation cannot bypass configured backend routing."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ROUTE_TO_BACKEND=true\n"
        "BACKEND_URL=http://backend:8000\n"
        "DATABASE_URL=postgresql://db/test\n"
    )

    with patch("opensampl.helpers.convert_value.run_backfill") as mock_backfill:
        result = CliRunner().invoke(
            cli,
            ["--env-file", str(env_file), "maintenance", "value-backfill"],
        )

    assert result.exit_code != 0
    assert "Warning:" in result.output
    assert "Disable ROUTE_TO_BACKEND" in result.output
    mock_backfill.assert_not_called()


def test_map_values_requires_database_url(tmp_path):
    """A direct database URL is required."""
    env_file = tmp_path / ".env"
    env_file.write_text("ROUTE_TO_BACKEND=false\n")

    result = CliRunner().invoke(
        cli,
        ["--env-file", str(env_file), "maintenance", "value-backfill"],
    )

    assert result.exit_code != 0
    assert "DATABASE_URL must be configured" in result.output


def test_map_values_forwards_resolved_options(tmp_path):
    """CLI options are resolved and forwarded to the backfill implementation."""
    env_file = tmp_path / ".env"
    env_file.write_text("ROUTE_TO_BACKEND=false\nDATABASE_URL=postgresql://db/test\n")

    with patch("opensampl.helpers.convert_value.run_backfill", return_value=0) as mock_backfill:
        result = CliRunner().invoke(
            cli,
            [
                "--env-file",
                str(env_file),
                "maintenance",
                "value-backfill",
                "--workers",
                "3",
                "--batch-size",
                "12h",
                "--vacuum-every-batches",
                "0",
            ],
        )

    assert result.exit_code == 0
    mock_backfill.assert_called_once_with(
        "postgresql://db/test",
        3,
        timedelta(hours=12),
        0,
    )


def test_map_values_derives_vacuum_cadence(tmp_path):
    """Vacuum cadence defaults to twice the resolved worker count."""
    env_file = tmp_path / ".env"
    env_file.write_text("ROUTE_TO_BACKEND=false\nDATABASE_URL=postgresql://db/test\n")

    with patch("opensampl.helpers.convert_value.run_backfill", return_value=0) as mock_backfill:
        result = CliRunner().invoke(
            cli,
            [
                "--env-file",
                str(env_file),
                "maintenance",
                "value-backfill",
                "--workers",
                "5",
            ],
        )

    assert result.exit_code == 0
    assert mock_backfill.call_args.args[3] == 10


def test_run_backfill_stops_when_no_metric_types_exist():
    """An empty metric selection exits without creating batches or vacuuming."""
    engine = Mock()
    engine.url = "postgresql://db/test"

    schema_connection = Mock()
    schema_connection.execute.return_value.scalars.return_value.all.return_value = ["value_jsonb", "value_float"]
    schema_context = MagicMock()
    schema_context.__enter__.return_value = schema_connection

    metric_connection = Mock()
    metric_connection.execute.return_value.scalars.return_value.all.return_value = []
    metric_context = MagicMock()
    metric_context.__enter__.return_value = metric_connection

    engine.connect.side_effect = [schema_context, metric_context]
    engine_factory = Mock(return_value=engine)

    updated = run_backfill(
        "postgresql://db/test",
        workers=2,
        batch_size=timedelta(days=1),
        vacuum_every_batches=4,
        engine_factory=engine_factory,
    )

    assert updated == 0
    engine.execution_options.assert_not_called()
    engine.dispose.assert_called_once_with()


def test_run_backfill_updates_windows_and_vacuums_once():
    """A zero cadence processes all windows before one final vacuum."""
    engine = Mock()
    engine.url = "postgresql://db/test"

    schema_connection = Mock()
    schema_connection.execute.return_value.scalars.return_value.all.return_value = ["value_jsonb", "value_float"]
    schema_context = MagicMock()
    schema_context.__enter__.return_value = schema_connection

    metric_connection = Mock()
    metric_connection.execute.return_value.scalars.return_value.all.return_value = ["metric-uuid"]
    metric_context = MagicMock()
    metric_context.__enter__.return_value = metric_connection

    time_range = Mock(start_time=datetime(2026, 1, 1), end_time=datetime(2026, 1, 2))
    range_connection = Mock()
    range_connection.execute.return_value.one.return_value = time_range
    range_context = MagicMock()
    range_context.__enter__.return_value = range_connection
    engine.connect.side_effect = [schema_context, metric_context, range_context]

    transaction_contexts = []
    for row_count in (2, 3):
        transaction_connection = Mock()
        transaction_connection.execute.side_effect = [Mock(), Mock(rowcount=row_count)]
        transaction_context = MagicMock()
        transaction_context.__enter__.return_value = transaction_connection
        transaction_contexts.append(transaction_context)
    engine.begin.side_effect = transaction_contexts

    vacuum_connection = Mock()
    vacuum_context = MagicMock()
    vacuum_context.__enter__.return_value = vacuum_connection
    vacuum_engine = Mock()
    vacuum_engine.connect.return_value = vacuum_context
    engine.execution_options.return_value = vacuum_engine

    updated = run_backfill(
        "postgresql://db/test",
        workers=1,
        batch_size=timedelta(days=1),
        vacuum_every_batches=0,
        engine_factory=Mock(return_value=engine),
    )

    assert updated == 5
    assert engine.begin.call_count == 2
    vacuum_connection.execute.assert_called_once()
    engine.dispose.assert_called_once_with()


def test_run_backfill_propagates_batch_failure_and_disposes_engine():
    """A failed batch aborts the run while still disposing the engine."""
    engine = Mock()
    engine.url = "postgresql://db/test"

    schema_connection = Mock()
    schema_connection.execute.return_value.scalars.return_value.all.return_value = ["value_jsonb", "value_float"]
    schema_context = MagicMock()
    schema_context.__enter__.return_value = schema_connection

    metric_connection = Mock()
    metric_connection.execute.return_value.scalars.return_value.all.return_value = ["metric-uuid"]
    metric_context = MagicMock()
    metric_context.__enter__.return_value = metric_connection

    time_range = Mock(start_time=datetime(2026, 1, 1), end_time=datetime(2026, 1, 1, 1))
    range_connection = Mock()
    range_connection.execute.return_value.one.return_value = time_range
    range_context = MagicMock()
    range_context.__enter__.return_value = range_connection
    engine.connect.side_effect = [schema_context, metric_context, range_context]

    transaction_connection = Mock()
    transaction_connection.execute.side_effect = [Mock(), RuntimeError("batch failed")]
    transaction_context = MagicMock()
    transaction_context.__enter__.return_value = transaction_connection
    engine.begin.return_value = transaction_context
    engine.execution_options.return_value = Mock()

    with pytest.raises(RuntimeError, match="batch failed"):
        run_backfill(
            "postgresql://db/test",
            workers=1,
            batch_size=timedelta(days=1),
            vacuum_every_batches=2,
            engine_factory=Mock(return_value=engine),
        )

    engine.dispose.assert_called_once_with()
