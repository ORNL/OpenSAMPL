# Quickstart

This quickstart uses the packaged Docker-backed server stack.

## Start the stack

Install the server extra first:

```bash
pip install "opensampl[server]"
```

Then start the default stack:

```bash
opensampl-server up
```

That starts:

1. PostgreSQL / TimescaleDB on `localhost:5415`
2. the backend API on `http://localhost:8015`
3. Grafana on `http://localhost:3015`

When `opensampl-server up` completes, it also updates your local OpenSAMPL environment so future `opensampl load ...` commands route through the backend API by default.

## Initialize and load data

Create the schema if needed:

```bash
opensampl init
```

Load a probe file:

```bash
opensampl load ADVA ./path/to/file.txt.gz
```

Or load a directory:

```bash
opensampl load ADVA ./path/to/data-dir
```

The loaded data should then be visible through Grafana.

## Inspect and stop

Check service status:

```bash
opensampl-server ps
```

Follow logs:

```bash
opensampl-server logs
```

Stop the stack:

```bash
opensampl-server down
```

See the [Configuration](../guides/configuration.md#opensampl-server) and [Server guide](../guides/opensampl-server.md) pages for environment customization and compose overrides.
