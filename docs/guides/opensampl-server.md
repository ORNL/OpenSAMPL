# openSAMPL Server CLI Usage Guide

The `opensampl-server` CLI is a thin wrapper around the packaged Docker Compose stack in `opensampl.server`.

It is useful when you want a local database, backend API, migrations container, and Grafana instance without managing the compose arguments yourself.

## Prerequisites

- Docker with either `docker compose` or `docker-compose`
- OpenSAMPL installed with the server extra

```bash
pip install "opensampl[server]"
```

## What `opensampl-server up` does

Running:

```bash
opensampl-server up
```

starts the packaged compose stack in detached mode and updates your local OpenSAMPL environment so future `opensampl load ...` commands route through the backend API.

Specifically, it writes:

- `ROUTE_TO_BACKEND=true`
- `BACKEND_URL=http://localhost:8015`
- `DATABASE_URL=postgresql://...@localhost:5415/...`

The default stack exposes:

- PostgreSQL / TimescaleDB on `localhost:5415`
- the backend API on `localhost:8015`
- Grafana on `localhost:3015`

## Commands

### Start all services

```bash
opensampl-server up
```

### Start only selected services

Additional arguments after `up` are passed through to Docker Compose. For example:

```bash
opensampl-server up grafana
opensampl-server up db backend
```

### Stop services

```bash
opensampl-server down
```

### Show logs

```bash
opensampl-server logs
```

### Show service status

```bash
opensampl-server ps
```

### Run a one-off compose command

```bash
opensampl-server run backend python -m opensampl.cli init
```

This maps directly to `docker compose run --rm ...`.

## Using a custom env file

`--env-file` is a top-level CLI option, so it must appear before the subcommand:

```bash
opensampl-server --env-file ./dev.env up
opensampl-server --env-file ./dev.env ps
```

By default, the server wrapper uses the packaged `default.env` values through `ServerConfig`.

The shipped defaults include:

```dotenv
COMPOSE_PROJECT_NAME=opensampl
POSTGRES_DB=castdb
POSTGRES_USER=castuser
POSTGRES_PASSWORD=castpassword
GF_SECURITY_ADMIN_PASSWORD=secret
BACKEND_LOG_LEVEL=DEBUG
USE_API_KEY=false
API_KEYS=changeme123
```

## Advanced configuration

The server wrapper can be redirected to other compose files or docker env files with the server-specific environment variables described in the [configuration guide](configuration.md#opensampl-server):

- `OPENSAMPL_SERVER__COMPOSE_FILE`
- `OPENSAMPL_SERVER__OVERRIDE_FILE`
- `OPENSAMPL_SERVER__DOCKER_ENV_FILE`

## Troubleshooting

1. Confirm Docker is installed and running.
2. Run `opensampl-server ps` to see whether services came up.
3. Run `opensampl-server logs` to inspect startup failures.
4. If you changed compose or env settings, confirm the files exist and are readable.

## Example workflow

```bash
opensampl-server up
opensampl-server ps
opensampl load ADVA ./data
opensampl-server down
```
