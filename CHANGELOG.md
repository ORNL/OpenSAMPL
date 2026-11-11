# Changelog

All notable changes to this project will be documented in this file in [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.  
This project adheres to [Semantic Versioning](https://semver.org/).

---

<!--

## [Unreleased] - YYYY-MM-DD
### Added
- 🔥 Placeholder for newly summoned features.
- 🔥 …

### Changed
- ⚡ Placeholder for ominous refactors and twisted rewrites.
- ⚡ …

### Deprecated
- ☠️ Placeholder for features about to vanish into the void.
- ☠️ …

### Removed
- 🗡️ Placeholder for chopped-off code.
- 🗡️ …

### Fixed
- 🩹 Placeholder for bugs crushed under your boot.
- 🩹 …

### Security
- 🔐 Placeholder for vulnerabilities sealed shut.
- 🔐 …

---

*Unreleased* versions radiate potential—-and dread. Once you merge an infernal PR, move its bullet under a new version heading with the actual release date.*



-->


## [1.2.7] = YYYY-MM-DD
### Added
- 🔥 Helm chart for deploying TimescaleDB, the backend API, Grafana, and database migrations on Kubernetes, with configurable storage, credentials, and ingress.
- 🔥 Reusable container image build workflow that builds the OpenSAMPL wheel once and installs it into backend and migration images.
- 🔥 OCI artifact publishing workflow for versioned container images and Helm charts on GHCR.
- 🔥 Helm pull request checks covering chart linting, template rendering, chart version bumps, and installation into minikube using locally built images.
- 🔥 Deployment smoke checks for backend database health and Grafana datasource connectivity after Helm installation.
- 🔥 Regression tests for access management, authentication failures, ingestion errors, backend option forwarding, and deployment configuration.
- 🔥 Probe loader tests covering every supported probe type, file and directory dispatch, option defaults, case-insensitive type selection, and invalid CLI arguments.
- 🔥 Kubernetes deployment and CI/CD guides covering installation, release workflows, configuration, and storage upgrade procedures.

### Changed
- ⚡ Document probe loading consistently as `opensampl load <PROBE_TYPE> <INPUT PATH> [OPTIONS]` for all supported probe types. Existing direct probe-type commands remain supported without deprecation warnings.
- ⚡ Updated README, quickstart, CLI, automatic ingestion, and table-format examples to distinguish shared probe loading behavior from vendor-specific file formats.
- ⚡ Corrected schema examples to use `location_uuid`, `test_uuid`, and `value_float`, and clarified composite keys in `probe_data`.
- ⚡ Aligned installation instructions and tox environments with Python 3.11 through 3.14, and clarified that the Docker-backed server launcher is included in the base package.
- ⚡ Simplified tox linting and formatting to use Ruff, and updated package build and publishing documentation to match the current workflows.
- ⚡ Enabled strict documentation builds in linting, GitHub Pages publishing, and the documentation container build; completed return annotations needed by generated API documentation.
- ⚡ Updated the Helm chart to version 0.2.4 and aligned its application version with OpenSAMPL 1.2.7.
- ⚡ Made the Grafana datasource host and password configurable independently of the Grafana administrator password, and replaced the chart's hardcoded external Grafana URL with `grafana.rootUrl`.
- ⚡ Production and development Compose stacks now wait for successful database migrations before starting the backend.
- ⚡ Added persistent Grafana storage to production Compose and documented how to preserve existing container data when adopting the volume.

### Fixed
- 🩹 Prevented non-duplicate database integrity errors during time-series ingestion from being swallowed and allowing failed input files to be archived.
- 🩹 Preserved the `strict` setting when time-series data is routed through the backend; requests that omit the field retain the default of `true`.
- 🩹 Handled both naive UTC and timezone-aware API key expiry timestamps without comparison errors, and replaced deprecated UTC timestamp generation.
- 🩹 Returned the generated API key in the `/gen_api_key` response while retaining its existing message field.
- 🩹 Corrected `opensampl-server up` API key configuration so it copies the first configured server key into the client settings when authentication is enabled.
- 🩹 Corrected Helm backend environment ordering so database credentials are available when Kubernetes expands `DATABASE_URL`.
- 🩹 Supplied Grafana with the release-specific database service address, database name, and datasource role password in Helm deployments.
- 🩹 Made `db.persistence.enabled` control StatefulSet storage: persistent claim templates when enabled and ephemeral storage when disabled, preserving existing database claim names.
- 🩹 Restored missing Kubernetes and CI/CD documentation pages referenced by navigation and guide links.
- 🩹 Corrected the documented chunk-size default to match the loader, which sends all records at once when no chunk size is specified.
- 🩹 Added Alembic's `path_separator` setting to avoid the legacy path-splitting deprecation warning.
- 🩹 Allowed optional Compose chunk interval and retention variables to remain unset without interpolation warnings.

### Removed
- 🗡️ Removed the unused standalone Helm database PVC; persistent database storage continues to use StatefulSet-managed claims.

### Security
- 🔐 Accepted both configured environment keys and active database keys, so configuring environment keys no longer prevents generated database keys from authenticating.
- 🔐 Prevented database lookup failures from being interpreted as an empty API key store eligible for unauthenticated bootstrap; unavailable lookups return HTTP 503 when no environment keys are available.
- 🔐 Standardized server configuration on `API_KEYS` with a legacy `API_KEY` fallback, while retaining the client's single-key `API_KEY` setting.

## [1.2.6] = 2026-10-26
### Security
- 🔐 Remediated Dependabot alerts by raising python minor and patch groups
- 🔐 Bumps the container-minor-and-patch group with 1 update in the / directory: astral-sh/uv.
- 🔐 Updates astral-sh/uv from 0.13.1 to 0.13.4 in the docs Dockerfile
- 🔐 Updates sqlalchemy from 2.0.54 to 2.0.55 
- 🔐 Updates fastapi from 0.143.3 to 0.146.0
- 🔐 Updates pytest-mock from 3.16.0 to 3.17.0
- 🔐 Updates telnet3 from 2.0.4 to 5.0.1
- 🔐 Updates Pillow to 13.0.0

### Changed
- ⚡ updated `OPENSAMPL_VERSION` in the Dockerfiles
- ⚡ updated workflows so Ubuntu 26.0.4 has access to Postgres 16
- ⚡ updated Ruff in lint action to 0.17.1

### Removed
- 🗡️  Removed support for EOL Python 3.10


## [1.2.5] = 2026-10-21
### Security
- 🔐 Remediated Dependabot alerts by raising python minor and patch groups
- 🔐 Updated pull_request target for Dependabot PRs to `bugfix/dependabot`
- 🔐 Added weekly Dependabot updates and CI dependency auditing to prevent vulnerable dependency regressions.

### Changed
- ⚡ updated `OPENSAMPL_VERSION` in the Dockerfiles

### Added
- 🔥 ensure_branch job to the dependabot security review workflow

## [1.2.4] = 2026-10-12
### Security
- 🔐 Remediated nine Dependabot alerts by raising the secure minimum versions of AnyIO, urllib3, PyMdown Extensions, Mako, and Material for MkDocs.
- 🔐 Added weekly Dependabot updates and CI dependency auditing to prevent vulnerable dependency regressions.

### Fixed
- 🩹 Preserved backend and documentation compatibility across supported Python 3.10 through 3.14 environments after the security upgrades.

## [1.2.3] = 2026-10-07
### Changed
- ⚡ updated database drivers to use psycopg2 in server
- ⚡ pinned geoalchemy2 to `>=0.18.0,<1` to comply with sqlalchemy requirements

### Added
- 🔥 docker bake definition file for migrations and backend
- 🔥 value backfill to migrate numeric `value_jsonb` to `value_float` for existing data in `probe_data` table

### Fixed
- 🩹 Bug in load data related to metric_type
- 🩹 Bug in server/backend for loading api keys

## [1.2.2] = 2026-09-30
### Changed
- ⚡ `probe_data` table now has `value_float` and `value_jsonb` columns instead of one `value` (jsonb type) column. 

## [1.2.1] - 2026-07-08
### Fixed
- 🩹 Addressed CVEs by updating minimum package versions for urllib3 2.7.0, pillow 12.3.0, mako 1.3.12, starlette 1.3.1, fastapi 0.139.0, idna 3.18, pytest 9.1.1, python-dotenv 1.2.2, fonttools 4.63.0, requests 2.34.2, markdown 3.10.2, pymdown-extensions 10.21.3, pygments 2.20.0, and python-multipart 0.0.32.


## [1.2.0] - 2026-04-29
### Added
- 🔥 First-class NTP vendor and probe support using the existing OpenSAMPL extension model
- 🔥 Local and remote NTP collection paths, including `ntp_metadata` loading behavior
- 🔥 NTP-focused metrics such as jitter, delay, stratum, reachability, root delay, root dispersion, poll interval, and sync health
- 🔥 Additional NTP metadata handling for collector/target probe relationships and reference-backed loading
- 🔥 Compact reference/source metadata views in dashboards to improve interpretation of NTP-backed timing data
- 🔥 Documentation covering the NTP extension path, collection semantics, and geolocation behavior
- 🔥 Additional unit and integration-style tests for NTP collection, loading, geolocation helpers, and seeded database defaults
- 🔥 Moved alembic migration code into openSAMPL along with Docker image information
- 🔥 Moved backend api code into openSAMPL along with Docker image information
- 🔥 Docker-compose for developers which installs openSAMPL as editable on backend image

### Changed
- ⚡ Hardened dashboard queries and variables to avoid brittle empty-filter handling and varchar-versus-UUID failures
- ⚡ Updated timing dashboards and wording to use reference-safe terminology for NTP-backed demo paths
- ⚡ Reworked integration-style tests to use the project MockDB harness instead of requiring a locally spawned PostgreSQL instance
- ⚡ Updated CI to install PostgreSQL/PostGIS tooling so the workflow can support `pytest-postgresql`-style environments when needed

### Fixed
- 🩹 Seeded default metric UUID handling in the MockDB test harness now points to the UNKNOWN metric as intended
- 🩹 Bug which caused random data duration to always be 1 hour
- 🩹 Issue with CI order causing linting to fail
- 🩹 Fixed variable assignment for mkdocs-click integration

## [1.1.5] - 2025-09-22
### Fixed
- 🩹 More durable timestamp extrapolation in time data insertion
- 🩹 Using shutil.move instead of pathlib.Path.rename to allow for differing file systems 
- 🩹 Broken path in docs 

### Changed
- ⚡ Added additional safeguards in TWST Collection to prevent zombie processes   
- ⚡ How random data uses the load/send when used as a class method for more durability

### Added
- 🔥 Better probe identification in logs
- 🔥 Filter on files being ingested by ADVA probes to only attempt files which match expected naming convention from input directory

### Removed
- 🗡️ static version of openSAMPL in docs instructions

## [1.1.4] - 2025-08-22
### Added
- 🔥 Random data generation for all supported probes
- 🔥 Public and "all" view in Grafana Dashboards

### Fixed
- 🩹 Autopopulation of unnamed probe identifiers in Grafana Dashboards

## [1.1.3] - 2025-08-18
### Added
- 🔥 Microchip TP4100 Load
- 🔥 Microchip TP4100 Collection
- 🔥 BaseProbe now has optional filter for directory load for vendor specific implementations

## [1.1.2] - 2025-07-24
### Added
- 🔥 README badges 
- 🧪 Added testing CI/CD
- 🏛️ Added classifiers for easier discovery
- 🔥 opensampl-server2 which passes everything directly to docker compose with correct compose and env
- 🔥 opensampl-collect entry point for accessing the collection scripts

### Changed
- ⚡ MicrochipTWST collection script takes all data by default rather than specific readings
- ⚡ MicrochipTWST collection script can take optional server and control ports 
- ⚡ MicrochipTWST probe object measurement logic updated to reflect collection

### Fixed
- 🩹 Dataframe insertion of time data more durable against single row collisions


## [1.1.1] - 2025-07-09
### Fixed
- 🩹 Added tabulate dependency to pyproject.toml
- 🩹 Corrected logic for differentiating between universal probe metadata and vendor specifics.

## [1.1.0] - 2025-07-02
### Added
- 🔥 Microsemi TWST Probe Support
- 🔥 Microsemi TWST 6502 modem data parser script
- 🔥 Data characteristic specification in database & code
- 🔥 `[collect]` package extra for dependencies relating to collecting data from probes
- 🔥 MockDB to facilitate testing
- 🔥 License Information 
- 🧪 Additional tests for vendors, CLI, config, and load data

### Changed
- ⚡ Now using Pydantic-settings for environment variable management
- ⚡ More thorough error handling around duplicate entries

### Removed
- 🗡️ `black` removed as dependency, probe type creation no longer depends on it 

### Fixed
- 🩹 Updated create functionality for adding new vendors


## [1.0.3] - 2025-06-02
### Added
- 🔥 Environment variable OPENSAMPL_COMPOSE_FILE used to identify compose file used for opensampl-server 

### Changed
- ⚡ Order of changelog, newest on top

### Fixed
- 🩹 Bugs in load_data introduced by ty type checking changes


## [1.0.2] - 2025-05-12
### Added
- 🔥 `black` added as a dependency for auto-creation of probe types
- 🔥 `ty` added as a dependency for type-checking

### Fixed
- 🩹 `ty` type checking errors addressed

### Changed
- ⚡ linting github action now confirms that the documentation can be built

## [1.0.1] - 2025-05-09
### Added
- 🔥 pytest as a dev dependency, used for running tests
- 🔥 pytest-cov as a dev dependency, used for measuring test coverage
- 🔥 pytest-mock as a dev dependency, used for mocking in tests
- 🔥 added a multitude of linting rules
- 🔥 added a lint and format checking GitHub Action
- 🔥 added development instructions in the README

### Fixed
- 🩹 Fix URL for the CHANGELOG
- 🩹 Reformatted files to be ruff format compliant
- 🩹 Fixed some typing annotation errors

### Removed
- 🗡️ Remove version specification in README.md
- 🗡️ Remove references to old indexes in pyproject.toml
- 🗡️ Remove kwargs in `__init__` method of `BaseProbe`
- 🗡️ Remove unused imports from many files
- 🗡️ Remove commented-out code in some classes

## [1.0.0] - 2025-05-09
- Initial commit
