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


OpenSAMPL provides Python tools for collecting, loading, and visualizing clock data in a
TimescaleDB-backed synchronization analytics stack.
This project came out of [**CAST**](https://cast.ornl.gov), the **C**enter for
**A**lternative **S**ynchronization and **T**iming at Oak Ridge National Laboratory (ORNL).
The name OpenSAMPL stands for **O**pen **S**ynchronization **A**nalytics and
**M**onitoring **PL**atform.

The current codebase supports loading and analysis workflows for ADVA, Microchip TWST,
Microchip TP4100, and NTP-derived probe data. Visualization is provided through
[Grafana](https://grafana.com/), and the data is stored in
[TimescaleDB](https://www.timescale.com/), which is built on PostgreSQL.


### (**O**pen **S**ynchronization **A**nalytics and **M**onitoring **PL**atform)

Python tools for adding clock and timing data to a TimescaleDB database.

## Installation

1. Ensure you have Python 3.10 or higher installed.
2. Install the latest release:

```bash
pip install opensampl
```

### Development Setup

```bash
uv venv
uv sync --all-extras --dev
source .venv/bin/activate
```
This creates a virtual environment and installs the development dependencies.

### Environment Setup

The CLI reads configuration from environment variables or a local `.env` file.

When routing through a backend service:
```bash
ROUTE_TO_BACKEND=true
BACKEND_URL=http://localhost:8000

ARCHIVE_PATH=/path/to/archive
```

When connecting directly to PostgreSQL / TimescaleDB:
```bash
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<database>
ARCHIVE_PATH=/path/to/archive
```

Use `opensampl config show` to inspect the current resolved configuration.

## CLI

The main CLI exposes `collect`, `config`, `create`, `init`, and `load`.
Use `opensampl --help` and `opensampl <command> --help` for current options.

If you plan to use the NTP, Microchip TWST, or Microchip TP4100 collectors, install the optional collection dependencies:

```bash
pip install "opensampl[collect]"
```

### Load Probe Data

Load data with the probe type name directly:

```bash
opensampl load ADVA path/to/file.txt.gz
opensampl load ADVA path/to/directory/
```

ADVA files bundle metadata and time-series data in a single file, so the split flags are
usually not needed.

```bash
opensampl load MicrochipTWST path/to/twst-output
opensampl load MicrochipTP4100 path/to/tp4100-output
```

NTP data is collected first and then loaded from the output directory:

```bash
opensampl collect ntp --mode remote --server pool.ntp.org --output-path ./ntp-out
opensampl load NTP ./ntp-out
```

Load options:

- `--metadata` / `-m`: load only probe metadata
- `--time-data` / `-t`: load only time-series data
- `--no-archive` / `-n`: skip archiving processed files
- `--archive-path` / `-a`: override the archive directory
- `--max-workers` / `-w`: set the worker count
- `--chunk-size` / `-c`: set the batch size for time-series inserts

### Load Direct Table Data

Load YAML or JSON directly into a table:

```bash
opensampl load table locations updated_location.yaml
```

Conflict handling is controlled by `--if-exists`:

- `update`: fill null fields in an existing row
- `error`: raise if the row exists
- `replace`: replace non-primary-key values
- `ignore`: skip existing rows

Example input:

```yaml
name: EPB Chattanooga
lat: 35.9311256
lon: -84.3292469
```

### View Configuration

```bash
opensampl config show
opensampl config show --explain
opensampl config show --var DATABASE_URL
```

### Set Configuration

```bash
opensampl config set VARIABLE_NAME value
```

## File Format Support

The loaders currently support:

- ADVA probe files named like
  `<ip_address>CLOCK_PROBE-<probe_id>-YYYY-MM-DD-HH-MM-SS.txt.gz>`
- Microchip TWST and TP4100 output produced by the collector tooling
- NTP snapshot output produced by `opensampl collect ntp`

Example ADVA file:
`10.0.0.121CLOCK_PROBE-1-1-2024-01-02-18-24-56.txt.gz`

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
