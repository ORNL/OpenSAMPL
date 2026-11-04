# openSAMPL Documentation

Python tools for loading, storing, and visualizing clock data in PostgreSQL / TimescaleDB.

## Overview

`opensampl` is an Oak Ridge National Laboratory (ORNL) project for synchronization analytics and monitoring data.

The package provides:

- a CLI for loading probe files and direct table data
- collection tooling for supported probe families
- optional Docker-backed server helpers
- Grafana dashboards and supporting backend components

OpenSAMPL currently supports probe families including ADVA, Microchip TWST, Microchip TP4100, and NTP.

## Getting started

- [Installation](getting-started/installation.md)
- [Quickstart](getting-started/quickstart.md)

## Guides

- [Configuration](guides/configuration.md)
- [Using the `opensampl` CLI](guides/opensampl-cli.md)
- [Using the `opensampl-server` CLI](guides/opensampl-server.md)
- [Collection Guide](guides/collection.md)
- [Random Data Guide](guides/random-data-generation.md)
- [NTP Extension Guide](guides/ntp-extension.md)

## API references

- [openSAMPL API Reference](api/index.md)

## Repository

```bash
git clone git@github.com:ORNL/OpenSAMPL.git
```
