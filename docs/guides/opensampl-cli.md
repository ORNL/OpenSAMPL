# CLI

Use `opensampl --help` to see the top-level commands, or `opensampl <command> --help`
for subcommand-specific options.

## Load Data

### Probe Data
Command: `opensampl load <PROBE TYPE> <INPUT PATH> [OPTIONS]`  
Arguments:

* `PROBE TYPE`: The loader implementation to use for the input files
* `INPUT PATH`: A single file or a directory of files

Supported probe types currently exposed by the CLI include `ADVA`, `MicrochipTWST`,
`MicrochipTP4100`, `NTP`, and `random`.

Options:

* `--metadata` (`-m`): Only load probe metadata
* `--time-data` (`-t`): Only load time series data
* `--no-archive` (`-n`): Don't archive processed files
* `--archive-path` (`-a`): Override default archive directory
* `--max-workers` (`-w`): Maximum number of worker threads (default: 4)
* `--chunk-size` (`-c`): Number of time data entries per batch (default: 10000)

#### ADVA
The CLI supports ADVA probe data files with the following naming convention:
> `<ip_address>CLOCK_PROBE-<probe_id>-YYYY-MM-DD-HH-MM-SS.txt.gz` 

Example:
> `10.0.0.121CLOCK_PROBE-1-1-2024-01-02-18-24-56.txt.gz`

The file format contains metadata at the beginning on lines starting with `#`, followed by
tab-separated `time value` measurements.

As ADVA probes have metadata and time-series data in each file, there is usually no need
to split metadata and time-data loading.

#### Microchip 
Microchip TWST and TP4100 files are supported. Collection for those devices is still done
through the dedicated `opensampl-collect` entry point, while loading is handled through
`opensampl load MicrochipTWST ...` or `opensampl load MicrochipTP4100 ...`.

#### NTP
NTP data can be collected with the main CLI and then loaded with the `NTP` probe type.

```bash
opensampl collect ntp --mode remote --server pool.ntp.org --output-path ./ntp-out
opensampl load NTP ./ntp-out
```

For local collection, point the collector at an `ntpq` output file or let it inspect the
local system directly, depending on your deployment. See the [collection guide](collection.md)
for the current collection modes and configuration options.

### Direct Table Entries
Load data directly into a database table from a file. The file format can be YAML or JSON.

The file should contain either one dictionary or a list of dictionaries.

Command: `opensampl load table <TABLE NAME> <INPUT PATH> [OPTIONS]`  
Arguments:

* `TABLE NAME`: Which table to write to
* `INPUT PATH`: The path to the input file, whose format can be yaml or json. See the [page on expected formatting for writing to table](expected_table_format.md) to ensure the provided file matches the table's expected format.

Options:

* `--if-exists` (`-i`): How to handle conflicts:
  - `update`: Insert non-primary-key fields that are `NULL` in an existing entry (default)
  - `error`: Raise an error if the entry already exists
  - `replace`: Replace all non-primary-key fields with new values
  - `ignore`: Skip the entry if it already exists

## Configuration
See the [configuration](configuration.md) page for how `opensampl config` reads and writes
environment-backed settings.

### View

Display current environment configuration

Command: `opensampl config show [OPTIONS]` <br>
Options:
* `--explain` (`-e`): Include description of each configuration variable
* `--var` (`-v`): Restrict the output to a specific variable

```bash
opensampl config show  # Show all variables and their current values
opensampl config show --explain  # Show all variables with descriptions
opensampl config show --var BACKEND_URL  # Show specific variable
opensampl config show -e -v BACKEND_URL  # Show specific variable with description
```

### Set

Command: `opensampl config set <VAR NAME> <VAR VALUE>` <br>
Arguments:

* `VAR NAME`: the env var you want to change
* `VAR VALUE`: the new value to set it as

## Create
**<mark>Experimental</mark>**  
Create a new probe type scaffold from a configuration file. See the
[Create page](create_probe_type.md) for the current workflow and limitations.

Command: `opensampl create <CONFIG PATH> [OPTIONS]` <br>
Arguments: 

* `CONFIG PATH`: The path to the config file defining the new probe type

Options:

* `--update-db` (`-u`): Update the database with the new probe type

