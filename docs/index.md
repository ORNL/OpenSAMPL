# openSAMPL Documentation
python tools for adding clock data to a timescale db. 

## Overview

`opensampl` is a package released by the Oak Ridge National Laboratory (ORNL) that provides tools for adding clock 
data to a postgres database. 

The package includes a CLI tool that allows users to load data from ADVA probes into a 
PostgreSQL database (preferably a [TimescaleDB](https://www.timescale.com/) flavor of PostgreSQL, but it can work with 
any PostgreSQL-based databases) 

The tool supports loading both metadata and time series data from files, with options to
skip loading one or the other. It also provides features for archiving processed files and setting the maximum number 
of worker threads for parallel processing, and helper functions for easily adding additional clocks to the database.

There is also an optional `server` extra which can be used to set your environment up more easily. 

## Getting Started

If you're new here, start your journey:

- **Installation:** Follow the steps in [Installation](getting-started/installation.md) to arm yourself with the essentials.
- **Quickstart:** For a rapid initiation, dive into our [Quickstart](getting-started/quickstart.md) guide.

## Guides

Master the art of customization and configuration:

[//]: # (* [Configuration]&#40;guides/configuration.md&#41; – Learn how to set up and tweak `opensampl` to your liking.)
* [Customization](guides/configuration) – Discover advanced tweaks that put you in complete control.
* [Using the `opensampl` CLI](guides/opensampl-cli.md) – A comprehensive guide to using the `opensampl` CLI tool.
* [Using the `opensampl-server` CLI](guides/opensampl-server.md) – A comprehensive guide to using the `opensampl-server` CLI tool.

## API Reference

Dare to explore our API:

* [openSAMPL API Reference](python-api-reference.md) – A comprehensive look into every function, class, and module that defines `opensampl`
* [Server API Reference](server-api-reference.md) – A detailed breakdown of the Python API that powers `opensampl`.
---

Each word here is designed to illuminate your path through the codebase. If you find yourself lost, refer back to this
document for guidance. And remember, the journey of a thousand commits begins with a single `git clone`. 🚀
```
git clone git@github.com:ORNL/OpenSAMPL.git
```
