# Configuration Guide

Configuration settings are stored as environment variables to ensure portability and security. 
Internally, openSAMPL uses the [python-dotenv](https://pypi.org/project/python-dotenv/) package to load variables from a `.env` file.  

## Core openSAMPL Configuration 
There are several environment variables used by the main openSAMPL cli to configure behavior. You can add them to a .env where you are running, 
or use the `opensampl config` cli command to configure. 

- `ROUTE_TO_BACKEND`: Whether to route database operations through the backend api or apply directly to db
- `DATABASE_URL`: URL for direct database connections (formatted like `postgresql://{user}:{password}@{host}:{port}/{database}`)
- `BACKEND_URL`: URL of the backend api service
- `ARCHIVE_PATH`: Default path that files are moved to after they have been processed. Default: `./archive`
- `LOG_LEVEL`: Log level for openSAMPL cli. Choice of `DEBUG`, `INFO`, `WARNING`, `ERROR`, from most information to least. Default: `INFO`

When you run `opensampl-server up`, the environment sets `ROUTE_TO_BACKEND=true` and sets the `BACKEND_URL` and `DATABASE_URL` to those created by the server. 

You can manually set `ROUTE_TO_BACKEND=false` using `opensampl config set ROUTE_TO_BACKEND false` if you prefer to avoid using the backend api. 


## opensampl-server
To customize your server, specify a new env file when running any command with `--env-file`
Here is what the default environment has configured:
```dotenv
COMPOSE_PROJECT_NAME=opensampl

POSTGRES_DB=castdb
POSTGRES_USER=castuser
POSTGRES_PASSWORD=castpassword

GF_SECURITY_ADMIN_PASSWORD=secret

BACKEND_LOG_LEVEL=DEBUG
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