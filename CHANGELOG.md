# Changelog

All notable changes to this project will be documented in this file in [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.  
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [1.2.0] - Unreleased
### Added
- 🔥 NTP vendor probe family (`NtpProbe`) with JSON snapshot format, filename convention, and `ntp_metadata` ORM table
- 🔥 `opensampl-collect ntp` entry point: local chrony/ntpq/timedatectl-style collection and remote UDP queries via `ntplib`
- 🔥 NTP-focused metrics in `METRICS` (phase offset, delay, jitter, stratum, reachability, dispersion, root delay/dispersion, poll interval, sync health)
- 🔥 Idempotent database bootstrap after schema creation: seed `reference_type`, `metric_type`, default `reference` and `defaults` rows from `REF_TYPES` / `METRICS`; `public.get_default_uuid_for()` for `ProbeData` defaults; `castdb.campus_locations` view for geospatial dashboards backed by `locations.geom`
- 🔥 Grafana: NTP probes dashboard (`ntp-opensampl`), public geospatial timing dashboard updates, datasource/dashboard provisioning alignment
- 🔥 Grafana table panels joining stored `probe_metadata`, `ntp_metadata`, `locations`, and `reference` / `reference_type` for probe reference & source context (no runtime geolocation in panels)
- 🔥 Remote NTP snapshot identity overrides (`probe_id`, `probe_ip`, `probe_name`, optional lab `geolocation` hints) for stable ingest keys

### Changed
- ⚡ Grafana timing panel titles and dashboard copy to **reference-safe** wording (NTP / configured reference vs implying GNSS truth where not applicable); extensible for future GNSS-backed probes
- ⚡ `METRICS.NTP_JITTER` description to distinguish measured jitter (local parsers) from conservative remote estimates
- ⚡ Remote `query_ntp_server`: emit `jitter_s` for time series using a documented delay/root-dispersion bound when RFC peer jitter is unavailable from a single packet
- ⚡ `load_probe_metadata`: NTP path attaches stored `locations` rows for dashboard geospatial joins (one-time at metadata load; not repeated in Grafana queries)

### Fixed
- 🩹 `opensampl init` / `create_new_tables` leaving lookup tables empty (load path now seeds baseline rows and defaults)
- 🩹 Grafana PostgreSQL variables and panel filters: text-safe UUID handling for `varchar` `probe_metadata.uuid` (avoid `varchar = uuid` / empty `IN ()` failures)
- 🩹 Public geospatial dashboard map layer using the provisioned `castdb-datasource` UID consistently

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
## [Unreleased] - YYYY-MM-DD
### Added
- 🔥 Moved alembic migration code into openSAMPL along with Docker image information
- 🔥 Moved backend api code into openSAMPL along with Docker image information
- 🔥 Docker-compose for developers which installs openSAMPL as editable on backend image

### Fixed
- 🩹 Bug which caused random data duration to always be 1 hour

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
