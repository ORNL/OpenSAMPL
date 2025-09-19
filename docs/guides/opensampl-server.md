# openSAMPL Server CLI Usage Guide

This guide explains how to use the openSAMPL Server command-line interface (CLI) tool to manage your openSAMPL server deployment.

## Overview

The openSAMPL Server CLI provides commands for managing a Docker Compose deployment of the openSAMPL server infrastructure. It handles:

- Starting and stopping services
- Viewing logs
- Checking service status
- Running custom commands

## Prerequisites

- Docker and Docker Compose installed
- The openSAMPL Python package installed

Install openSAMPL as normal: 
```
pip install opensampl
```

## Basic Commands

### Starting the Server

To start the openSAMPL server:

```bash
opensampl-server up
```

This command:
- Starts all services defined in the Docker Compose file
- Runs containers in detached mode (`-d`)
- Sets local environment variables to route `opensampl load` commands via the backend

**Starting a specific service:**

```bash
opensampl-server up --service grafana
```
this will start up just the specified container, choices are: 
- db
- backend
- grafana
- migrations

**Using a custom .env file:**

```bash
opensampl-server up --env-file /path/to/custom.env
```
uses default.env with values: 
```dotenv
COMPOSE_PROJECT_NAME=opensampl

POSTGRES_DB=castdb
POSTGRES_USER=castuser
POSTGRES_PASSWORD=castpassword

DB_URI="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
GF_SECURITY_ADMIN_PASSWORD=secret

BACKEND_LOG_LEVEL=DEBUG
```
### Stopping the Server

To stop all services:

```bash
opensampl-server down
```

**Stopping a specific service:**

```bash
opensampl-server down --service db
```

### Viewing Logs

To view logs from all containers:

```bash
opensampl-server logs
```

This command follows the logs (`-f`), showing new log entries as they arrive.

### Checking Service Status

To see the status of all services:

```bash
opensampl-server ps
```

This displays:
- Container names
- Status (running, stopped, etc.)
- Ports
- Other container information

### Running Custom Commands

The `run` command allows you to execute commands in a service container:

```bash
opensampl-server run backend python -m opensampl.cli init
```

This example:
- Creates a temporary container for the `backend` service
- Runs the specified command
- Removes the container after completion (`--rm`)

## Environment Configuration

By default, the CLI uses the packaged `default.env` file for configuration. You can specify a custom environment file with the `--env-file` option for any command:

```bash
opensampl-server up --env-file ./my-custom-env.env
```

## Technical Details

- The CLI automatically detects whether to use `docker-compose` or `docker compose` based on your system configuration
- When starting the server, it configures your local environment to use the backend by setting:
  - `BACKEND_URL=http://localhost:8015`
  - `ROUTE_TO_BACKEND=true`

## Power users 

For those who are more familiar with docker, there is a `opensampl-server2` which corresponds to the following, more directly 
exposing the docker to users.
`OPENSAMPL_SERVER__COMPOSE_FILE` is set in your .env file or environment.

```bash
opensampl-server2 --env-file ENV_FILE args
docker compose --env-file ${ENV_FILE} -f ${OPENSAMPL_SERVER__COMPOSE_FILE} $@
```

## Troubleshooting

If you encounter issues:

1. Check that Docker and Docker Compose are installed and running
2. Verify your environment file contains the necessary configuration
3. Check the logs for specific error messages: `opensampl-server logs`

## Examples

**Full development workflow:**

```bash
# Start the entire stack
opensampl-server up

# Check that all services are running
opensampl-server ps

# View logs to ensure everything started correctly
opensampl-server logs

# load clock data into the db
opensampl load probe ADVA ./data

# When finished, shut down the stack
opensampl-server down
```

**Development with custom environment:**

```bash
# Create a custom environment file
cp $(opensampl-server get-default-env) ./dev.env

# Edit the file with custom settings
nano ./dev.env

# Start the server with custom environment
opensampl-server up --env-file ./dev.env
```


