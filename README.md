# OpenSAMPL

<div align="center">
<!-- PyPI → version -->
<a href="https://pypi.org/project/opensampl/"><img src="https://img.shields.io/pypi/v/opensampl?logo=pypi" alt="PyPI"></a>
<!-- MIT licence -->
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-lightgrey.svg" alt="MIT licence"></a>
<!-- Supported Python versions (will show “missing” until you add the trove classifiers) -->
<a href="https://pypi.org/project/opensampl/"><img src="https://img.shields.io/pypi/pyversions/opensampl?logo=python" alt="python versions"></a>
<!-- Universal wheel? -->
<a href="https://pypi.org/project/opensampl/"><img src="https://img.shields.io/pypi/wheel/opensampl" alt="wheel"></a>
<!-- Monthly downloads -->
<a href="https://pypistats.org/packages/opensampl"><img src="https://img.shields.io/pypi/dm/opensampl?label=downloads%20%28month%29" alt="downloads per month"></a>
<!-- GitHub Actions CI -->
<a href="https://github.com/ORNL/OpenSAMPL/actions/workflows/publish.yml"><img src="https://github.com/ORNL/OpenSAMPL/actions/workflows/publish.yml/badge.svg" alt="PyPi Publishing"></a>
<a href="https://github.com/ORNL/OpenSAMPL/actions/workflows/lint.yml"><img src="https://github.com/ORNL/OpenSAMPL/actions/workflows/lint.yml/badge.svg" alt="ruff Formating and Linting"></a>
<a href="https://github.com/ORNL/OpenSAMPL/actions/workflows/tests.yml"><img src="https://github.com/ORNL/OpenSAMPL/actions/workflows/tests.yml/badge.svg" alt="PyTest Testing"></a>
<!-- Docs on GitHub Pages -->
<a href="https://ornl.github.io/OpenSAMPL/"><img src="https://img.shields.io/website?url=https%3A%2F%2Fornl.github.io%2FOpenSAMPL%2F&label=docs&logo=github" alt="docs"></a>
</div>


OpenSAMPL was created to provide a set of Python tools for managing clock data in a TimescaleDB database, specifically designed for synchronization analytics and monitoring.
This project came out of [**CAST**](https://cast.ornl.gov), the **C**enter for **A**lternative **S**yncrhonization and **T**iming, a research group at Oak Ridge National Laboratory (ORNL).
The name OpenSAMPL stands for **O**pen **S**ynchronization **A**nalytics and **M**onitoring **PL**atform, and provides the code and logic for uploading, managing, and visualizing clock data from various sources, including ADVA probes and Microchip TWST data files,
with the goal of this project being to provide a comprehensive and open-source solution for clock data management and analysis. 
Visualizations are provided via [grafana](https://grafana.com/), and the data is stored in a [TimescaleDB](https://www.timescale.com/) database, which is a time-series database built on PostgreSQL.

**NTP clock probes** are supported end-to-end: YAML-driven vendor scaffolding (`opensampl create`), JSON snapshots, `opensampl load ntp`, and `opensampl-collect ntp` (local chrony/ntpq-style chain or remote UDP via optional `ntplib`). NTP observations use the same metric/reference tables as other vendors; **“Reference”** in Grafana means the OpenSAMPL reference dimension for SQL joins, **not** GNSS ground truth for NTP-only demos.

**Database bootstrap**: first-time setup should run **`opensampl init`**, which creates schema and seeds lookup tables (`reference_type`, `metric_type`, `reference`, `defaults`) plus PostgreSQL helpers expected by the load path (see `opensampl/db/bootstrap.py`). Skipping init leads to obscure failures on first load.

**Documentation**: [published docs](https://ornl.github.io/OpenSAMPL/) — start with *Guides*. For NTP specifically, see *NTP vendor design* and *NTP extension (walkthrough)* (generator, geolocation at ingest, bootstrap, Grafana query notes).

### (**O**pen **S**ynchronization **A**nalytics and **M**onitoring **PL**atform)

Python tools for adding clock data to a TimescaleDB-backed database.

## CLI TOOL

### Installation

1. Ensure you have Python 3.9 or higher installed
2. Pip install the latest version of opensampl: 
```bash
pip install opensampl
# Remote NTP collection also needs extras, e.g. pip install 'opensampl[collect]'
```

### Development Setup
```bash
uv venv
uv sync --extra all
source .venv/bin/activate
```
This will create a virtual environment and install the development dependencies.

### Environment Setup

The tool requires several environment variables. Create a `.env` file in your project root:

When routing through a backend:
```bash
ROUTE_TO_BACKEND=true  # Set to true if using backend service
BACKEND_URL=http://localhost:8000  # Only needed if ROUTE_TO_BACKEND is true

# Archive configuration
ARCHIVE_PATH=/path/to/archive  # Where processed files are stored
```
When directly accessing db: 
```bash
# Database connection
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<database>

# Archive configuration
ARCHIVE_PATH=/path/to/archive  # Where processed files are stored
```

### Basic Usage

The CLI tool provides several commands. You can use `opensampl --help` (or, any deeper `opensampl [command] --help`) to get details

#### Load Probe Data

Load data from ADVA probes:

```bash
# Load single file
opensampl load probe adva path/to/file.txt.gz

# Load directory of files
opensampl load probe adva path/to/directory/
```
ADVA probes have all their metadata and their time data in each file, so no need to use the `-m` or `-t` options, though if you want to skip loading one or the other it becomes useful! 

options:
- `--metadata` (`-m`): Only load probe metadata
- `--time-data` (`-t`): Only load time series data
- `--no-archive` (`-n`): Don't archive processed files
- `--archive-path` (`-a`): Override default archive directory
- `--max-workers` (`-w`): Maximum number of worker threads (default: 4)
- `--chunk-size` (`-c`): Number of time data entries per batch (default: 10000)

#### Load Direct Table Data

Load data directly into a database table. Format can be yaml or json. Can be a list of dictionaries or a single dictionary.

you do not have to specify schema, is assumed to be castdb. 

The --if-exists option controls how to handle conflicts:
  - update: Only update fields that are provided and non-default (default)
  - error: Raise an error if entry exists
  - replace: Replace all non-primary-key fields with new values
  - ignore: Skip if entry exists

```bash
opensampl load table table_name path/to/data.yaml
```

So, you can do things like the following  
```bash
opensampl load table locations --if-exists replace updated_location.yaml
```
Where this is the updated_location
```yaml
name: EPB Chattanooga
lat: 35.9311256
lon: -84.3292469
```
And it will overwrite the existing entry for EPB Chattanooga, or create a new one if it doesn't exist yet.


### View Configuration

Display current environment configuration:

```bash
# Show all variables
uv run opensampl config show

# Show with descriptions
uv run opensampl config show --explain

# Show specific variable
uv run opensampl config show --var DATABASE_URL
```

Configuration resolution: explicit `--env-file`, then `OPENSAMPL_ENV_FILE`, then `python-dotenv`’s search for `.env`. **Process environment variables override values from the env file** (pydantic-settings precedence).

### Set Configuration

Update environment variables:

```bash
uv run opensampl config set VARIABLE_NAME value
```

## File Format Support

The tool currently supports:

ADVA probe data files with the following naming convention:
`<ip_address>CLOCK_PROBE-<probe_id>-YYYY-MM-DD-HH-MM-SS.txt.gz`

Example: `10.0.0.121CLOCK_PROBE-1-1-2024-01-02-18-24-56.txt.gz`

Microchip TWST Data Files as generated by the script available. 

# Contributing
We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to get started.

# CAST Database Schema Documentation

## castdb.locations
Stores geographic locations with their coordinates and metadata. Supports both 2D and 3D point geometries.

```yaml
name: "Lab A"  # Unique name for the location
lat: 35.93  # Latitude coordinate
lon: -84.31  # Longitude coordinate
z: 100  # Optional elevation in meters
projection: 4326  # Optional SRID/projection (defaults to 4326/WGS84)
public: true  # Optional boolean for public visibility
```

## castdb.test_metadata
Tracks testing periods and experiments with start and end timestamps.

```yaml
name: "Holdover Test 1"  # Unique name for the test
start_date: "2024-01-01T00:00:00"  # Test start timestamp
end_date: "2024-01-07T00:00:00"  # Test end timestamp
```

## castdb.probe_metadata
Contains information about timing probes, including their network location and associated metadata. Insertion handled by `opensampl load probe`.

```yaml
probe_id: "1-1"  # Probe identifier
ip_address: "10.0.0.121"  # IP address of the probe
vendor: "ADVA"  # Vendor type
model: "OSA 5422"  # Model number
name: "GMC1"  # Human-readable name
public: true  # Optional boolean for public visibility
location_uiid: "123e4567-e89b-12d3-a456-426614174000"  # Optional reference to location
test_uiid: "123e4567-e89b-12d3-a456-426614174001"  # Optional reference to test
```

## castdb.probe_data
Time series data from probes, storing timestamps and measured values. Insertion handled by `opensampl load probe`.
```yaml
time: "2024-01-01T00:00:00"  # Timestamp of measurement
probe_uuid: "123e4567-e89b-12d3-a456-426614174000"  # Reference to probe
value: 1.234e-09  # Measured value
```

## castdb.adva_metadata
ADVA-specific configuration and status information for probes. Insertion handled by `opensampl load probe`.

```yaml
probe_uuid: "123e4567-e89b-12d3-a456-426614174000"  # Reference to probe
type: "Phase"  # Measurement type
start: "2024-01-01T00:00:00"  # Start timestamp
frequency: 1  # Sampling frequency
timemultiplier: 1  # Time multiplier
multiplier: 1  # Value multiplier
title: "ClockProbe1"  # Probe title
adva_probe: "ClockProbe"  # Probe type
adva_reference: "GPS"  # Reference source
adva_reference_expected_ql: "QL-NONE"  # Expected quality level
adva_source: "TimeClock"  # Source type
adva_direction: "NA"  # Direction
adva_version: 1.0  # Version number
adva_status: "RUNNING"  # Operating status
adva_mtie_mask: "G823-PDH"  # MTIE mask type
adva_mask_margin: 0  # Mask margin
```

## Notes

- All tables use UUIDs as primary keys which are automatically generated.
- Table relationships are maintained through UUID references
- Geographic coordinates use WGS84 projection (SRID 4326) by default
- Boolean fields (public) are optional and can be null

