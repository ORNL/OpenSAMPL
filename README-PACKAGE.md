# Package builds and publishing

Package metadata and the release version live in `pyproject.toml`. Update the version before publishing a new release.

The `publish.yml` workflow builds distributions and publishes to PyPI on pushes to `main` or manual runs. The test workflow builds distributions on its supported Python matrix. Container images and the Helm chart are published separately by `publish-artifacts.yml`.

Ruff linting and formatting are configured in `pyproject.toml` and enforced by `lint.yml`. Run `uv run ruff check .` and `uv run ruff format --check .` locally. The equivalent tox environment is `tox -e lint`.

See [CI/CD and Releases](docs/maintainers/ci-cd.md) for validation and release steps.
