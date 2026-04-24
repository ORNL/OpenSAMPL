# Server API Reference

The `opensampl[server]` extra includes a packaged FastAPI backend that the
`opensampl-server` compose stack uses for routed loads and dashboard support.

At the moment this documentation set does not publish a generated endpoint-by-endpoint API
reference page. For practical usage:

* use the [server guide](guides/opensampl-server.md) to start the packaged stack
* use `opensampl load ...` once the stack is running and routing is enabled
* inspect `opensampl/server/backend/main.py` in the source tree for the current FastAPI application entry point

The backend is an implementation detail for most users; the supported interface remains the
`opensampl` and `opensampl-server` CLIs.
