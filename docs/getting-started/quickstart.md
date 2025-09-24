# Quick Start using Server 

By running `opensampl-server up`, you get a full stack ready to receive your time data. 

This creates: 

1. A TimescaleDB instance, with schema already fully formatted
1. A BackendAPI ready to be used to ingest data
    * Complete with Swagger documentation at: [http://localhost:8015](http://localhost:8015)
1. A [Grafana](https://grafana.com/) server with a dashboard already built to visualize clock data. 
    * Accessible at [http://localhost:3015](http://localhost:3015)

In order to ingest data, you simply have to run `opensampl load` with appropriate arguments, and it will go straight into your new TimescaleDB
instance and become visible on Grafana. 

See the [Configuration](../guides/configuration.md#opensampl-server) page on configuring your server instance. 