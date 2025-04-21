# CLI

The CLI tool provides several commands. You can use `opensampl --help` (or, any deeper `opensampl [command] --help`) to get details

## Load Data

### Probe Data
Command: `opensampl load <PROBE TYPE> <INPUT PATH> [OPTIONS]` <br>
Arguments: 

* `PROBE TYPE`: Specify the probe type, which defines how to process the data files 
    * currently only `ADVA` is officially supported. We have plans to incorporate Microsemi TSWFT clock readings. 
    * You can also try the experimental `create` method, described [below](#create), to define your own probe type.
* `INPUT PATH`: The path to the input. Can be a single file, or a directory of files. 

Options: 

* `--metadata` (`-m`): Only load probe metadata
* `--time-data` (`-t`): Only load time series data
* `--no-archive` (`-n`): Don't archive processed files
* `--archive-path` (`-a`): Override default archive directory
* `--max-workers` (`-w`): Maximum number of worker threads (default: 4)
* `--chunk-size` (`-c`): Number of time data entries per batch (default: 10000)

#### ADVA
The tool currently supports ADVA probe data files with the following naming convention: 
> `<ip_address>CLOCK_PROBE-<probe_id>-YYYY-MM-DD-HH-MM-SS.txt.gz` 

Example: 
> `10.0.0.121CLOCK_PROBE-1-1-2024-01-02-18-24-56.txt.gz`

With the file format of having metadata at the beginning (on lines starting with `#`), followed by 
tab separated `time value` measurements. 

As ADVA probes have all their metadata and their time data in each file, there is no need to use the `-m` or `-t` options, though if you want to skip loading one or the other it becomes useful!

### Direct Table Entries
Load data directly into a database table from a file, whose format can be yaml or json. 

The file should contain either one dictionary (for one entry) or a list of dictionaries (for many entries)

Command: `opensampl load table <TABLE NAME> <INPUT PATH> [OPTIONS]` <br>
Arguments: 

* `TABLE NAME`: Which table to write to. 
* `INPUT PATH`: The path to the input file, whose format can be yaml or json. See the [page on expected formatting for writing to table](expected_table_format.md) to ensure the provided file matches the table's expected format.

Options:

* `--if-exists` (`-i`): How to handle conflicts:
    - `update`: Insert non-primary-key fields that are `NULL` in existing entry (default)
    - `error`: Raise an error if entry exists
    - `replace`: Replace all non-primary-key fields with new values
    - `ignore`: Skip if entry exists

## Configuration
See the [configuration](configuration.md) page for details on how the config command works

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
** <mark>Experimental</mark> ** <br>
Create a new probe type with scaffolding, based on a config file.
See the [Create page](create_probe_type.md) for how to use

Command: `opensampl create <CONFIG PATH> [OPTIONS]` <br>
Arguments: 

* `CONFIG PATH`: The path to the config file defining the new probe type

Options:

* `--update-db` (`-u`):  Update the database with the new probe type


