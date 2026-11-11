"""Regression coverage for repository review findings."""

import asyncio
import importlib
import io
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import psycopg2
import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from opensampl import load_data
from opensampl.db.access_orm import APIAccessKey, Base
from opensampl.metrics import METRICS
from opensampl.references import REF_TYPES
from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import ProbeKey


@pytest.fixture
def access_session():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS access")
        Base.metadata.create_all(connection)
        connection.commit()
        with Session(connection) as session:
            yield session
    engine.dispose()


@pytest.mark.parametrize("aware", [False, True])
def test_expiration_accepts_stored_and_aware_timestamps(aware):
    now = datetime.now(UTC)
    if not aware:
        now = now.replace(tzinfo=None)
    assert APIAccessKey(expires_at=now - timedelta(days=1)).is_expired()
    assert not APIAccessKey(expires_at=now + timedelta(days=1)).is_expired()
    assert not APIAccessKey().is_expired()


@pytest.mark.parametrize("duplicate", [False, True])
def test_failed_integrity_insert_is_not_archived(tmp_path, duplicate):
    source = tmp_path / "probe.txt"
    source.write_text("data")
    probe = Mock()
    error_type = psycopg2.errors.UniqueViolation if duplicate else psycopg2.errors.ForeignKeyViolation
    probe.process_time_data.side_effect = IntegrityError("insert", {}, error_type())

    class TestProbe(BaseProbe):
        def __new__(cls, *args, **kwargs):
            return probe

    args = dict(
        filepath=source,
        archive_dir=tmp_path / "archive",
        no_archive=False,
        metadata=False,
        time_data=True,
        chunk_size=None,
    )
    if duplicate:
        TestProbe.process_single_file(**args)
        probe.archive_file.assert_called_once()
    else:
        with pytest.raises(IntegrityError):
            TestProbe.process_single_file(**args)
        probe.archive_file.assert_not_called()
        assert source.exists()


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    return importlib.import_module("opensampl.server.backend.main")


def test_environment_and_active_database_keys_are_accepted(backend, access_session, monkeypatch):
    access_session.add_all(
        [
            APIAccessKey(key="database"),
            APIAccessKey(key="expired", expires_at=datetime.now(UTC) - timedelta(days=1)),
        ]
    )
    access_session.commit()
    monkeypatch.setenv("API_KEYS", "environment, second")
    monkeypatch.setattr(backend, "engine", access_session.get_bind())
    assert set(backend.get_keys()) == {"environment", "second", "database"}


def test_auth_lookup_failure_cannot_bootstrap(backend, monkeypatch):
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(backend, "USE_API_KEY", True)
    with patch.object(backend, "sessionmaker", side_effect=RuntimeError("offline")):
        with pytest.raises(HTTPException) as exc:
            backend.require_api_key(bootstrap=True)(None)
    assert exc.value.status_code == 503


def test_environment_key_survives_database_outage_and_legacy_fallback(backend, monkeypatch):
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("API_KEY", "legacy")
    with patch.object(backend, "sessionmaker", side_effect=RuntimeError("offline")):
        assert backend.get_keys() == ["legacy"]
        monkeypatch.setenv("API_KEYS", "current")
        assert backend.get_keys() == ["current"]


def test_bootstrap_and_invalid_key_behavior(backend, monkeypatch):
    monkeypatch.setattr(backend, "USE_API_KEY", True)
    with patch.object(backend, "get_keys", return_value=[]):
        assert backend.require_api_key(bootstrap=True)(None) is None
        with pytest.raises(HTTPException) as exc:
            backend.require_api_key()(None)
        assert exc.value.status_code == 403
    with patch.object(backend, "get_keys", return_value=["valid"]):
        assert backend.require_api_key()("valid") == "valid"
        with pytest.raises(HTTPException):
            backend.require_api_key(bootstrap=True)("invalid")


def test_generated_key_is_returned(backend, access_session):
    response = backend.generate_api_key(expire_after=1, api_key=None, session=access_session)
    payload = json.loads(response.body)
    assert payload["key"] == access_session.query(APIAccessKey).one().key
    assert payload["message"] == "Succeeded in creating new access key"


@pytest.mark.parametrize("strict", [False, True])
def test_routed_time_payload_preserves_strict(strict):
    config = Mock(ROUTE_TO_BACKEND=True)
    payload = load_data.load_time_data.__wrapped__(
        probe_key=ProbeKey(probe_id="test", ip_address="127.0.0.1"),
        metric_type=METRICS.UNKNOWN,
        reference_type=REF_TYPES.UNKNOWN,
        data=Mock(),
        _config=config,
        strict=strict,
    )
    assert payload["data"]["strict"] == str(strict).lower()


@pytest.mark.parametrize("strict", [False, True])
def test_backend_forwards_strict(backend, strict):
    upload = UploadFile(filename="time.csv", file=io.BytesIO(b"time,value\n2026-01-01,1\n"))
    with patch.object(backend.load_data, "load_time_data") as load:
        response = asyncio.run(
            backend.load_time_data(
                probe_key_str='{"probe_id":"test","ip_address":"127.0.0.1"}',
                metric_type_str=None,
                reference_type_str=None,
                compound_key_str=None,
                file=upload,
                strict=strict,
                api_key=None,
                session=Mock(),
            )
        )
    assert response.status_code == 200
    assert load.call_args.kwargs["strict"] is strict
    assert (
        backend.app.openapi()["components"]["schemas"]["Body_load_time_data_load_time_data_post"]["properties"][
            "strict"
        ]["default"]
        is True
    )


@pytest.mark.parametrize("key_name", ["API_KEYS", "API_KEY"])
def test_server_up_configures_client_key(key_name):
    from click.testing import CliRunner
    from opensampl.server import cli as server_cli

    config = Mock(LOG_LEVEL="INFO")
    config.docker_env_values = {"USE_API_KEY": "TRUE", key_name: "first,second"}
    config.build_docker_compose_base.return_value = ["docker", "compose"]
    process = Mock(stdout=[])
    with (
        patch.object(server_cli, "ensure_docker"),
        patch.object(server_cli, "load_config", return_value=config),
        patch.object(server_cli.subprocess, "Popen", return_value=process),
    ):
        result = CliRunner().invoke(server_cli.cli, ["up"])
    assert result.exit_code == 0, result.output
    assert config.API_KEY == "first"
    config.save_config.assert_called_once()
