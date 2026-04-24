# Probe Abstractions

OpenSAMPL no longer exposes a standalone `opensampl.load.probe` module.

Probe-specific loading behavior is currently split across:

* [`opensampl.vendors.base_probe`](../vendors/base_probe.md) for the common probe interface
* [`opensampl.load_data`](../load_data.md) for the load orchestration entry points
* the individual vendor modules under [`vendors/`](../vendors/adva.md)

Use those pages for the current implementation details.
