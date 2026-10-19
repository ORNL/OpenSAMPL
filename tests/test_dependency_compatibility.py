"""Compatibility checks for dependencies upgraded during security remediation."""

import gzip
import importlib
import ssl
import sys
import threading
import time
import zlib
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import anyio
import markdown
import pytest
import urllib3
from alembic.config import Config
from alembic.script import ScriptDirectory
from anyio import to_process
from anyio._core._sockets import idna2008_resolve
from mako import exceptions
from mako.lookup import TemplateLookup
from mako.template import Template
from packaging.version import Version
from urllib3.util import Retry, Timeout


PATCHED_MINIMUMS = {
    "anyio": "4.14.2",
    "urllib3": "2.8.0",
    "pymdown-extensions": "11.0.1",
    "Mako": "1.4.2",
    "mkdocs-material": "9.7.7",
}


def _write_large_stderr() -> str:
    """Exercise AnyIO's process-pool stderr handling beyond a pipe buffer."""
    sys.stderr.write("dependency-security-check\n" * 65536)
    sys.stderr.flush()
    return "completed"


class _CompatibilityHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    retry_count = 0

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/plain":
            self._send_body(b"plain-http-ok")
            return

        if self.path == "/gzip":
            body = gzip.compress(b"compressed-response-ok")
            self._send_body(body, content_encoding="gzip")
            return

        if self.path == "/chunked-deflate":
            payload = zlib.compress(b"streamed-deflate-ok" * 64) + b"trailing-data"
            self.send_response(200)
            self.send_header("Content-Encoding", "deflate")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for start in range(0, len(payload), 7):
                chunk = payload[start : start + 7]
                self.wfile.write(f"{len(chunk):x}\r\n".encode())
                self.wfile.write(chunk + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
            return

        if self.path == "/retry":
            type(self).retry_count += 1
            if type(self).retry_count < 3:
                self._send_body(b"", status=503)
            else:
                self._send_body(b"retry-ok")
            return

        if self.path == "/timeout":
            time.sleep(0.2)
            self._send_body(b"late")
            return

        self._send_body(b"not found", status=404)

    def _send_body(self, body: bytes, *, status: int = 200, content_encoding: str | None = None) -> None:
        self.send_response(status)
        if content_encoding:
            self.send_header("Content-Encoding", content_encoding)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@pytest.fixture
def http_origin() -> Generator[str, None, None]:
    _CompatibilityHandler.retry_count = 0
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _CompatibilityHandler,  # ty: ignore[invalid-argument-type]
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_security_minimum_versions_are_installed() -> None:
    """The resolved environment must not contain any addressed vulnerable version."""
    for package, minimum in PATCHED_MINIMUMS.items():
        assert Version(version(package)) >= Version(minimum)


def test_anyio_uses_idna_2008_for_internationalized_tls_names() -> None:
    """IDNA 2008 must preserve sharp-s instead of applying the unsafe IDNA 2003 mapping."""
    assert idna2008_resolve("faß.de") == b"xn--fa-hia.de"


def test_anyio_process_pool_drains_or_redirects_stderr() -> None:
    """A worker writing more than a pipe buffer to stderr must still complete."""

    async def run_worker() -> str:
        with anyio.fail_after(10):
            return await to_process.run_sync(_write_large_stderr, cancellable=True)

    assert anyio.run(run_worker) == "completed"


def test_urllib3_http_compression_streaming_retries_and_timeouts(http_origin: str) -> None:
    """Exercise OpenSAMPL's urllib3/requests transport behaviors against a local origin."""
    manager = urllib3.PoolManager(
        retries=Retry(total=2, status_forcelist={503}, backoff_factor=0),
        timeout=Timeout(connect=1, read=1),
    )

    assert manager.request("GET", f"{http_origin}/plain").data == b"plain-http-ok"
    assert manager.request("GET", f"{http_origin}/gzip").data == b"compressed-response-ok"
    assert manager.request("GET", f"{http_origin}/retry").data == b"retry-ok"

    response = manager.request("GET", f"{http_origin}/chunked-deflate", preload_content=False)
    try:
        assert b"".join(response.stream(amt=16, decode_content=True)) == b"streamed-deflate-ok" * 64
    finally:
        response.release_conn()

    with pytest.raises(urllib3.exceptions.ReadTimeoutError):
        manager.request(
            "GET",
            f"{http_origin}/timeout",
            retries=False,
            timeout=Timeout(connect=1, read=0.05),
        )


def test_urllib3_keeps_proxy_and_destination_tls_configuration_separate() -> None:
    """HTTPS proxy verification settings must remain distinct from destination settings."""
    proxy_context = ssl.create_default_context()
    destination_context = ssl.create_default_context()
    manager = urllib3.ProxyManager(
        "https://proxy.invalid:443",
        proxy_ssl_context=proxy_context,
        proxy_assert_hostname="proxy.invalid",
        ssl_context=destination_context,
    )

    proxy_config = manager.proxy_config
    assert proxy_config is not None
    assert proxy_config.ssl_context is proxy_context
    assert proxy_config.assert_hostname == "proxy.invalid"
    assert manager.connection_pool_kw["ssl_context"] is destination_context
    assert proxy_context.verify_mode == ssl.CERT_REQUIRED
    assert destination_context.verify_mode == ssl.CERT_REQUIRED


def test_pymdown_rendering_extensions_and_admonitions() -> None:
    """PyMdown 11+ must render the documentation constructs retained by OpenSAMPL."""
    rendered = markdown.markdown(
        """!!! note
    Security note.

```python
print("safe")
```

~~deleted~~ ^superscript^ https://example.com
""",
        extensions=[
            "admonition",
            "pymdownx.caret",
            "pymdownx.magiclink",
            "pymdownx.superfences",
            "pymdownx.tilde",
        ],
    )

    assert 'class="admonition note"' in rendered
    assert "highlight" in rendered
    assert "<del>deleted</del>" in rendered
    assert "<sup>superscript</sup>" in rendered
    assert 'href="https://example.com"' in rendered


def test_mako_templates_and_alembic_migration_discovery(tmp_path: Path) -> None:
    """Mako rendering and the packaged Alembic revision chain remain usable."""
    assert Template("hello ${name}").render(name="OpenSAMPL") == "hello OpenSAMPL"

    templates = tmp_path / "templates"
    templates.mkdir()
    (tmp_path / "secret.txt").write_text("not renderable", encoding="utf-8")
    lookup = TemplateLookup(directories=[str(templates)])
    with pytest.raises(exceptions.TemplateLookupException):
        lookup.get_template("C:/../../secret.txt")

    migration_root = Path("opensampl/server/migrations").resolve()
    config = Config(str(migration_root / "alembic.ini"))
    config.set_main_option("script_location", str(migration_root / "_migrations"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() is not None
    assert list(scripts.walk_revisions())


def test_backend_initializes_with_supported_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The backend app and unauthenticated health route must initialize on supported Python versions."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    backend = cast(Any, importlib.import_module("opensampl.server.backend.main"))

    assert backend.app.title == "openSAMPL Backend"
    assert backend.healthcheck() == {"status": "OK"}
    assert backend.healthcheck_db() == {"status": "OK"}
