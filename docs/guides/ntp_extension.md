# NTP vendor extension (implementation walkthrough)

This document describes how the **NTP** clock-probe family was added to OpenSAMPL, how it fits the **vendor generator** model, and which pieces remain **manual integration** work. It also separates **upstream OpenSAMPL** behavior from the **syncscope-at-home** demo appliance.

For field-level design (modes, metadata vs series, local tool chain), see [NTP vendor design](ntp_vendor_design.md).

---

## 1. Why NTP is modeled as a vendor / probe family

OpenSAMPL organizes ingest around **vendors** (`VendorType`), **probe identity** (`ProbeKey`), **vendor-specific metadata tables**, and **normalized time series** in `probe_data`. NTP sources are not GNSS truth references; they are **network clock observations** (local client state or remote server responses). Modeling NTP as its own vendor keeps:

- A dedicated **`ntp_metadata`** table for sync/leap/stratum/targets and parser provenance.
- Stable **`ProbeKey`** derivation from snapshot filenames and JSON payloads.
- Metrics and references aligned with the rest of the platform (`metric_type`, `reference`) without pretending NTP stratum implies a calibrated physical reference.

---

## 2. Role of the vendor generator (`opensampl create`)

The CLI command `opensampl create <config.yaml>` uses `opensampl.create.create_vendor.VendorConfig` to:

- Generate or refresh **probe parser scaffolding** and **SQLAlchemy metadata ORM** from YAML.
- Update **`opensampl.vendors.constants`** so the new vendor is registered for routing and CLI.

The generator is **scaffolding**: it does not implement protocol logic, collectors, or Grafana panels by itself.

---

## 3. `ntp_vendor.yaml` and generated artifacts

The canonical input is `opensampl/ntp_vendor.yaml` in the package source tree. It declares:

- `name`, `parser_class` / `parser_module`, `metadata_orm`, `metadata_table`
- `metadata_fields`: typed columns on `ntp_metadata` (mode, targets, sync fields, dispersion, etc.)

Running `opensampl create` against this file produces/updates generated modules under `opensampl/vendors/` and wires the vendor into constants. Treat **`ntp_vendor.yaml` as the contract** between schema and hand-written Python (`ntp.py`, collectors).

---

## 4. Manual steps after generation

Typical follow-through (as done for NTP):

1. **Implement the probe class** (`NtpProbe`): parse snapshot JSON, normalize metadata, emit series rows with correct metric keys.
2. **Implement collectors** (`opensampl-collect ntp`):  
   - **Local**: shell out to chrony/ntpq/timedatectl with a defined fallback order.  
   - **Remote**: UDP client via `ntplib` (`opensampl/vendors/ntp_remote.py`), optional probe/geo overrides.
3. **Load path hooks**: `write_to_table` / probe load pipeline must attach NTP-specific behavior (e.g. **geolocation** before `probe_metadata` insert—see below).
4. **Metrics**: register NTP metrics in `opensampl/metrics` so bootstrap seeds `metric_type`.
5. **References**: NTP demos use **`REF_TYPES.UNKNOWN`**; dashboards label **“Reference”** for SQL joins, **not** as GNSS ground truth.
6. **ORM / migrations**: ensure `opensampl init` (or Alembic, if used) creates `ntp_metadata` and related objects consistently with generated code.

---

## 5. Metrics and reference choices

- **Offset, delay, stratum, poll, root delay/dispersion**, etc. are stored as first-class metrics where applicable.
- **Jitter**: a **single** remote NTP client response does not expose RFC5905 peer jitter; `ntp_remote` may emit a **positive bound** derived from delay and root dispersion so dashboards have a value—this is an **estimate**, not a sampled Allan deviation. Local chrony/ntpq paths may still expose **measured** jitter when available.
- **Reference**: use **`UNKNOWN`** unless a future model maps NTP reference IDs to calibrated references. Do **not** describe NTP-only demos as validating against **GNSS truth**.

---

## 6. Local vs remote collection

| Path | Mechanism | Notes |
|------|-----------|--------|
| **Local** | Subprocess chain (chronyc, ntpq, timedatectl, …) | Best-effort; records `observation_source` and partial state when tools are missing. |
| **Remote** | `ntplib` UDP request | High ports supported for lab mocks; production often uses UDP **123**. Timeouts produce degraded metadata, not process crashes. |

---

## 7. Metadata and geolocation

**Geolocation is applied at metadata ingest** (when building rows for `locations` / `probe_metadata`), not inside Grafana:

- **`attach_ntp_location`** (`opensampl/load/ntp_geolocation.py`) resolves coordinates from YAML `geo_override`, lab defaults, or **public IP → HTTP** lookup (e.g. ip-api.com) when enabled.
- Grafana maps read **`castdb.locations`** / **`castdb.campus_locations`**; panels do **not** call external geo APIs at query time.

Disable enrichment with env **`NTP_GEO_ENABLED=false`** if you want probes without new location rows.

---

## 8. Bootstrap and seed requirements

`opensampl init` and/or load bootstrap (`opensampl/db/bootstrap.py` → `seed_lookup_tables`) must ensure:

- **`reference_type`** / **`metric_type`** rows exist (including **UNKNOWN**).
- A **`reference`** row and **`defaults`** entries so ORM defaults and `ProbeData` triggers resolve UUIDs.
- **`public.get_default_uuid_for(text)`** exists on PostgreSQL (used by probe data insertion).
- **`castdb.campus_locations`** view (PostGIS lat/lon from `locations.geom`) for **reference-safe** geospatial dashboards when PostGIS is present.

Skipping bootstrap causes obscure failures during first load; always run **`opensampl init`** against a fresh database before loading probes.

---

## 9. Grafana and SQL hardening

- Dashboards use **text** template variables aligned with `probe_metadata.uuid` (varchar UUID strings)—avoid numeric formatting that strips leading zeroes.
- Prefer queries that tolerate **empty** or **single-probe** deployments (e.g. NTP-only stacks without legacy GNSS rows).
- **“Reference”** in titles means **OpenSAMPL reference dimension** for joins/filters, not a claim of absolute timing truth.
- **Metadata panels** may **collapse** JSON into compact rows for readability; that is presentation-only.

---

## 10. OpenSAMPL vs syncscope-at-home

| Concern | OpenSAMPL (library) | syncscope-at-home (demo) |
|--------|---------------------|---------------------------|
| Vendor YAML, parsers, collectors, load hooks, bootstrap | Yes | Consumes as submodule |
| Docker Compose, custom **PostGIS + Timescale** DB image, **ntp-ingest** loop | No | Yes (`docker-compose.yaml`, `demo/db`, `demo/ntp-ingest`) |
| Default **NTP targets**, **interval**, spool paths | No | `config/ntp-ingest.yaml`, env `NTP_INGEST_CONFIG` |
| Lab **mock NTP** UDP services | No | Compose services `mock-ntp-*` |
| Opinionated Grafana **dashboards** shipped in repo | Optional / examples | `demo/` Grafana image and provisioning |

Treat **syncscope-at-home** as an **appliance-style** illustration: it shows how to run continuous collect+load with sane defaults, not a mandatory deployment topology for upstream OpenSAMPL.

---

## See also

- [NTP vendor design](ntp_vendor_design.md) — probe identity, modes, failure semantics  
- [Collection](collection.md) — `opensampl-collect` overview  
- [Configuration](configuration.md) — env files and CLI config  
- API: [`create_vendor`](../api/helpers/create_vendor.md)
