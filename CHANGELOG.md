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
