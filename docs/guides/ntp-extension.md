# NTP Extension Guide

This guide explains how NTP support was added to OpenSAMPL, what behaviors are specific to the NTP probe family, and what assumptions the dashboards and loader make when visualizing NTP-backed timing data.

## Overview

The NTP work adds a first-class `NTP` vendor family to OpenSAMPL rather than treating NTP snapshots as an external pre-processing concern.

That includes:

- a vendor/probe implementation in `opensampl.vendors.ntp`
- local and remote collection paths
- `ntp_metadata` rows for probe-specific metadata
- NTP-specific metric loading into `probe_data`
- dashboard and query changes so NTP-backed references are handled safely

## Probe model

NTP uses two related probe identities:

- the target probe, which represents the NTP server or local host being measured
- the collection probe, which represents the host performing the observation

Time-series rows are written for the target probe and use the collection probe as the reference dimension. This keeps NTP data aligned with existing OpenSAMPL reference semantics without pretending the reference is GNSS-grounded.

## Collection modes

The NTP probe supports two collection modes:

- `local`
  Uses locally available tools such as `chronyc`, `ntpq`, `timedatectl`, and `systemctl` to infer synchronization state and measured metrics where available.
- `remote`
  Sends a single NTP query to a remote host using `ntplib` and extracts values such as offset, delay, stratum, and root dispersion.

The main CLI path is:

```bash
opensampl collect ntp --mode remote --host time.cloudflare.com --probe-id public-time --output-dir ./ntp-out
opensampl collect ntp --mode local --probe-id local-chrony --load
```

## Metadata and loading

Each NTP artifact contains:

- file header metadata describing the target and collection probe relationship
- time-series rows for each collected metric

During load:

1. the collection probe is inserted into `probe_metadata` with `reference: true`
2. the target probe is inserted into `probe_metadata`
3. NTP-specific metadata is written into `ntp_metadata`
4. each collected metric is written into `probe_data` using the collection probe as the reference

This design keeps NTP aligned with the existing OpenSAMPL loading model and allows dashboards to filter across vendors using the same reference tables.

## Jitter semantics

Remote NTP responses do not always provide a true measured peer jitter value from a single sample. When OpenSAMPL has only a single remote response, it stores a documented estimate/bound derived from delay and root dispersion rather than leaving jitter empty.

Local `chronyc` and `ntpq` paths continue to use measured jitter when those tools expose it.

The dashboards and docs should therefore distinguish between:

- measured jitter from local/system tooling
- estimated jitter from single-response remote NTP queries

## Geolocation behavior

NTP geolocation happens at metadata ingest time, not in Grafana.

The loader uses `ENABLE_GEOLOCATE` and the geolocation helper to decide whether to create `locations` rows:

- if an explicit override is provided, that override wins
- if geolocation is enabled and the host resolves to a public IP, OpenSAMPL can look up coordinates through `ip-api.com`
- if the host resolves to a private or loopback IP, default lab coordinates can be used
- if there is not enough information to name and place a location, location creation is skipped

This keeps external lookup behavior isolated to ingest time and makes the resulting dashboard state reproducible from the database alone.

## Dashboard semantics

For NTP-backed demo paths, the word `Reference` is intentional.

It means:

- the OpenSAMPL reference dimension used for joins and variable resolution

It does not mean:

- a claim that the underlying timing source is GNSS-truth-backed

The backend model still preserves GNSS extensibility for future probe families. The NTP work only makes the current semantics safer and more explicit.

## Testing and CI

The NTP work added:

- collector tests for local and remote parsing behavior
- metadata/load tests for `ntp_metadata` and collection-probe creation
- geolocator unit tests that mock outbound lookup behavior
- integration-style seeded database tests using MockDB

The CI workflow also installs PostgreSQL/PostGIS tooling so environments that rely on `pytest-postgresql` can still be provisioned when needed, while the default suite remains stable on developer machines that cannot easily run a local PostGIS-backed PostgreSQL instance.
