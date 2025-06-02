# Configuration Guide

Configuration settings are stored as environment variables to ensure portability and security. 
Internally, openSAMPL uses the [python-dotenv](https://pypi.org/project/python-dotenv/) package to load variables from a `.env` file.  

## Specifying the location of variables

For all the cli entrypoints, you can use --env-file to specify where to get these configurations from, if they are not in the environment currently.

OR, you can `export OPENSAMPL_ENV_FILE='full/path/to/.env` to use it each time, rather than adding the flag to your cli command.

## Core openSAMPL Configuration 
There are several environment variables used by the main openSAMPL cli to configure behavior. You can add them to a .env where you are running, 
or use the `opensampl config` cli command to configure. 

- `ROUTE_TO_BACKEND`: Whether to route database operations through the backend api or apply directly to db
- `DATABASE_URL`: URL for direct database connections (formatted like `postgresql://{user}:{password}@{host}:{port}/{database}`)
- `BACKEND_URL`: URL of the backend api service
- `ARCHIVE_PATH`: Default path that files are moved to after they have been processed. Default: `./archive`
- `LOG_LEVEL`: Log level for openSAMPL cli. Choice of `DEBUG`, `INFO`, `WARNING`, `ERROR`, from most information to least. Default: `INFO`
- `API_KEY`: Api key to use for validation when routing through a backend, which has `USE_API_KEY` = True
- `INSECURE_REQUESTS`: Bool, set = True when you wish to allow your requests to the backend to have no verification.

When you run `opensampl-server up`, the environment sets `ROUTE_TO_BACKEND=true` and sets the `BACKEND_URL` and `DATABASE_URL` to those created by the server. 

You can manually set `ROUTE_TO_BACKEND=false` using `opensampl config set ROUTE_TO_BACKEND false` if you prefer to avoid using the backend api. 


## opensampl-server
By default, the server will be created using the `docker-compose.yaml` found in opensampl/server/. If you wish to set a different compose to further control
your server, you can export the `OPENSAMPL_SERVER__COMPOSE_FILE` env var to be the full path to your own compose file. 

To customize your server, specify a new env file using the `OPENSAMPL_SERVER__DOCKER_ENV_FILE` env var. It will default to the one found in opensampl/server/default.env
Here is what the default environment has configured:
```dotenv
COMPOSE_PROJECT_NAME=opensampl

POSTGRES_DB=castdb
POSTGRES_USER=castuser
POSTGRES_PASSWORD=castpassword

GF_SECURITY_ADMIN_PASSWORD=secret

BACKEND_LOG_LEVEL=DEBUG

USE_API_KEY=false
# If USE_API_KEY=true, configure the API_KEYS below. Comma separated list for multiple.
API_KEYS=changeme123
```

* `COMPOSE_PROJECT_NAME` - Controls the prefix on docker container names. (so, `project-db-1`, `project-grafana-1`, etc)
* `POSTGRES_DB` - The database name in your postgres instance.
* `POSTGRES_USER` - The master user for the db
* `POSTGRES_PASSWORD` - The password for the `POSTGRES_USER` role in the `POSTGRES_DB` database
* `GF_SECURITY_ADMIN_PASSWORD` - The password for the grafana user in the `POSTGRES_DB` database. The grafana account is a view only role that the dashboards use
to access the db. 
* `BACKEND_LOG_LEVEL` - How verbose the logs on the backend api are
    * `DEBUG` - all logs, with frequent variable dumps to trouble shoot issues. (default)
    * `INFO` - informative logs about progress
    * `WARNING` - high level notifications that indicate potential problems
    * `ERROR` - only when something breaks
* `USE_API_KEY` - Whether to validate incoming requests to the backend API
* `API_KEYS` - If `USE_API_KEY`=true, then you can provide a list of valid keys at startup. 

