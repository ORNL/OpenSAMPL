# Value backfill

Migration `b88042bae240` changes how OpenSAMPL stores numeric probe values in
`castdb.probe_data`. It renames the original `value` column to `value_jsonb` and
adds an optimized `value_float` column. The migration only changes the schema;
it intentionally does not rewrite historical data because that can take much
longer than a normal deployment migration.

The value backfill performs that historical rewrite as a separate maintenance
operation. It:

- finds metric types whose `value_type` is `float` or `int`;
- converts their scalar `value_jsonb` values to double precision and stores the
  result in `value_float`;
- processes the table in newest-first time windows using independent
  transactions and configurable parallel workers; and
- vacuums `castdb.probe_data` periodically during the backfill.

Only rows where `value_float IS NULL` and `value_jsonb IS NOT NULL` are updated.
This makes the value backfill resumable. If it stops or fails, correct the
problem and run the same command again; previously backfilled rows are skipped.

## Before running

Run the value backfill only after the deployment's Alembic migrations have
completed. The command verifies that both `value_jsonb` and `value_float` exist
before starting.

The value backfill requires a direct database connection through
`DATABASE_URL`. It does not use the OpenSAMPL backend API. If
`ROUTE_TO_BACKEND=true`, it prints a warning and exits without connecting.
Explicitly set `ROUTE_TO_BACKEND=false` for the maintenance run.

Updates and vacuum operations can generate substantial database I/O. For a
large deployment:

- verify that a recent backup is available;
- run during a maintenance or low-traffic period;
- begin with a conservative worker count; and
- do not run multiple value backfills concurrently.

## Run through the OpenSAMPL CLI

With `DATABASE_URL` configured and `ROUTE_TO_BACKEND=false`, run:

```bash
opensampl maintenance value-backfill
```

To select a particular OpenSAMPL environment file:

```bash
opensampl --env-file ./maintenance.env maintenance value-backfill
```

The required settings can also be supplied for a one-off shell invocation:

```bash
ROUTE_TO_BACKEND=false \
DATABASE_URL='postgresql+psycopg2://user:password@database:5432/castdb' \
opensampl maintenance value-backfill
```

## Tune the value backfill

```bash
opensampl maintenance value-backfill \
  --workers 4 \
  --batch-size 12h \
  --vacuum-every-batches 8
```

The options are:

- `--workers INTEGER`: number of concurrent database workers. If omitted, the
  command uses `WORKERS`, then the local CPU count, then `4` as a fallback.
- `--batch-size DURATION`: time covered by each transaction. The default is
  `1d`. Positive minute, hour, day, and week values are accepted, such as
  `30m`, `12h`, `1d`, and `2w`.
- `--vacuum-every-batches INTEGER`: run `VACUUM` after this many completed
  batches. The default is twice the resolved worker count. Use `0` to process
  all batches first and vacuum once at the end.

Smaller time windows reduce the amount of work lost if a transaction fails but
create more transactions. More workers may finish sooner, but increase database
CPU, I/O, connection usage, and write-ahead log activity.

## Run in the packaged Compose deployment

The packaged stack defines an opt-in `value-backfill` service. It uses the same
database and migration image as the rest of the deployment and is excluded from
normal `opensampl-server up` operations.

After starting or upgrading the deployment, run it explicitly:

```bash
opensampl-server run value-backfill
```

The service waits for a healthy database and successful migration completion.
It sets `ROUTE_TO_BACKEND=false` and supplies the container's direct
`DATABASE_URL`.

To override the defaults, replace the service command while retaining its
environment and dependencies:

```bash
opensampl-server run -- value-backfill \
  opensampl maintenance value-backfill \
  --workers 4 \
  --batch-size 12h \
  --vacuum-every-batches 8
```

## Monitor and recover

Each committed window is logged with its start time, end time, and updated row
count. Vacuum operations and the final total are also logged. A configuration,
schema, database, or worker error produces a nonzero exit status.

If the value backfill fails, rerun it after correcting the error. You may retain
the same batch settings or lower the worker count to reduce database load.
Committed windows remain committed, and populated `value_float` rows are
skipped, so no manual checkpoint or cleanup is required. Running the command
after completion is safe; it exits when no values remain to be backfilled.
