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
## [1.2.0] - Unreleased
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
