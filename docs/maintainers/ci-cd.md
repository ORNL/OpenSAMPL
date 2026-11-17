# CI/CD and Releases

## Pull request checks

- `tests.yml` installs all extras and development groups, runs pytest on Python 3.11–3.14, checks CLI imports, and builds distributions. Integration tests require PostgreSQL and PostGIS tooling.
- `lint.yml` checks Ruff linting and formatting, generates API documentation, and builds documentation in strict mode.
- `helm-checks.yml` builds local images, lints and renders the chart, requires a chart version bump when chart files change, and installs the chart into minikube. Deployment checks query backend database health and the Grafana datasource.
- `dependency-security.yml` checks dependencies using its configured security tools.

Local checks:

```bash
uv sync --locked --all-extras --all-groups
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mkdocs build --strict
helm lint ./helm
helm lint ./helm -f ./helm/values-cluster-overrides.yaml
```

## Publishing

Update the package version in `pyproject.toml` before a package release. Keep container Dockerfile version defaults and `helm/Chart.yaml` appVersion aligned with the package. Bump the chart version whenever chart contents change.

`publish.yml` builds and publishes distributions to PyPI on pushes to `main` or manual dispatch. It uses the configured PyPI publishing credential. Avoid manually dispatching it for an already-published version.

`publish-artifacts.yml` publishes images and the Helm chart from `main`. The reusable `build-images.yml` builds a wheel and injects it into the backend and migration images, then tags images with the package version and `latest`. The chart is pushed to `oci://ghcr.io/ornl/charts` after image builds succeed.

`static.yml` generates API pages, builds documentation strictly, and deploys GitHub Pages from `main`. A successful package publish alone does not verify image deployment; check the test and Helm workflows before releasing.
