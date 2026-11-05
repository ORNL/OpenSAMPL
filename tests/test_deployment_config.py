"""Check deployment behavior beyond YAML syntax and Helm linting."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("helm") is None, reason="Helm is required to render chart templates")
@pytest.mark.parametrize("release", ["opensampl", "review-custom"])
@pytest.mark.parametrize("persistent", [False, True])
def test_chart_connectivity_and_storage(release, persistent):
    rendered = subprocess.check_output(
        [
            "helm",
            "template",
            release,
            str(ROOT / "helm"),
            "--set",
            f"db.persistence.enabled={str(persistent).lower()}",
            "--set",
            "grafana.rootUrl=https://example.org/grafana",
        ],
        text=True,
    )
    resources = list(yaml.safe_load_all(rendered))
    deployments = [r for r in resources if r["kind"] == "Deployment"]
    backend = next(r for r in deployments if r["metadata"]["name"].endswith("-backend"))
    env = backend["spec"]["template"]["spec"]["containers"][0]["env"]
    names = [item["name"] for item in env]
    assert names.index("DATABASE_URL") > names.index("POSTGRES_USER")
    assert names.index("DATABASE_URL") > names.index("POSTGRES_PASSWORD")
    grafana = next(r for r in deployments if r["metadata"]["name"].endswith("-grafana"))
    env = {item["name"]: item for item in grafana["spec"]["template"]["spec"]["containers"][0]["env"]}
    db_service = next(r for r in resources if r["kind"] == "Service" and r["metadata"]["name"].endswith("-db"))
    assert env["OPENSAMPL_DATASOURCE_HOST"]["value"] == db_service["metadata"]["name"] + ":5432"
    assert env["POSTGRES_DB"]["value"] == "opensampl"
    assert env["OPENSAMPL_DATASOURCE_PASSWORD"]["valueFrom"]["secretKeyRef"]["key"] == "GF_SECURITY_ADMIN_PASSWORD"
    assert env["GF_SERVER_ROOT_URL"]["value"] == "https://example.org/grafana"
    stateful = next(r for r in resources if r["kind"] == "StatefulSet")
    assert bool(stateful["spec"].get("volumeClaimTemplates")) is persistent
    volumes = stateful["spec"]["template"]["spec"]["volumes"]
    assert any(v.get("name") == "db-storage" and "emptyDir" in v for v in volumes) is not persistent
    assert not any(r["kind"] == "PersistentVolumeClaim" for r in resources)


@pytest.mark.parametrize("filename", ["docker-compose.yaml", "docker-compose.dev.yaml"])
def test_compose_migrations_auth_and_grafana_storage(filename):
    config = yaml.safe_load((ROOT / "opensampl/server" / filename).read_text())
    services = config["services"]
    assert services["backend"]["depends_on"]["migrations"]["condition"] == "service_completed_successfully"
    assert any(e.startswith("API_KEYS=") for e in services["backend"]["environment"])
    assert "grafana-data:/var/lib/grafana" in services["grafana"]["volumes"]
    assert "OPENSAMPL_DATASOURCE_HOST=db:5432" in services["grafana"]["environment"]
