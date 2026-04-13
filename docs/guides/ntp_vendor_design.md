# NTP vendor design (OpenSAMPL)

This note defines the NTP clock-probe family: identity, storage, local vs remote collection, and lab-demo caveats.

## Vendor identity

| Item | Value |
|------|--------|
| Vendor name | `NTP` |
| Probe class | `NtpProbe` |
| Module | `opensampl.vendors.ntp` |
| Metadata ORM / table | `NtpMetadata` / `ntp_metadata` |

## Probe identity (`ProbeKey`)

- **`ip_address`**: For `remote_server`, the target server IP or a placeholder derived from the hostname. For `local_host`, typically `127.0.0.1` or the host’s primary IPv4 used for labeling.
- **`probe_id`**: Stable slug per logical probe (e.g. `local-chrony`, `mock-a`, `remote-pool-1`).

Snapshot files use a strict filename pattern so the loader can derive `ProbeKey` without opening the file (see `NtpProbe` docstring).

## Modes

| Mode | Meaning |
|------|--------|
| `local_host` | Collector runs on the machine whose NTP client state is observed (Raspberry Pi friendly). |
| `remote_server` | Collector issues NTP client requests to `target_host`:`target_port` (default UDP **123**; high ports supported for demos). |

## Metadata vs time series

- **`ntp_metadata`**: Latest normalized fields from the most recent observation (sync/leap/stratum/reach/reference/poll/root metrics, mode, targets, `observation_source`, etc.) plus `additional_metadata` JSONB for raw command output snippets and parser notes.
- **`probe_data`**: One OpenSAMPL row per `(time × metric_type × reference)` as elsewhere. NTP uses dedicated metrics (offset, delay, jitter, stratum, etc.) with `REF_TYPES.UNKNOWN` unless a future reference model is introduced.

Offset is stored in seconds; Grafana panels may scale to nanoseconds for consistency with existing timing dashboards.

## Local fallback chain

Tools are tried in order until one yields usable structured data:

1. `chronyc tracking`
2. `chronyc -m 'sources -v'` or `chronyc sources -v`
3. `ntpq -p`
4. `timedatectl show-timesync --all` / `timedatectl status`
5. `systemctl show systemd-timesyncd` / `systemctl status systemd-timesyncd`

Missing binaries are skipped without failing the snapshot; `sync_status` and `observation_source` record partial or unavailable state.

## Remote collection

Standard NTP client requests over UDP (default port **123**, configurable). Timeouts and non-responses produce degraded samples and metadata rather than crashing the loader.

## Failure semantics

- Loaders and collectors catch per-step failures; snapshots are still written when possible.
- Missing numeric fields omit that metric series for that timestamp or use absent rows only—never rely on invalid JSON (`NaN` is avoided in stored values).

## Demo vs production NTP

- **Lab mock servers** often listen on **high UDP ports** so containers do not require `CAP_NET_BIND_SERVICE`. Real deployments typically use **UDP/123**.
- **Simulated drift / unhealthy behavior** in containers is implemented by manipulating **NTP response fields** (stratum, delay, dispersion, etc.), not by true physical clock Allan deviation. Comparison panels show **protocol-level** differences between mock instances.
