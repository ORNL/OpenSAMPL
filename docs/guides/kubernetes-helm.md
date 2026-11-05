# Deploying on Kubernetes with Helm

The chart deploys TimescaleDB, the backend API, Grafana, and a migration Job. A Kubernetes cluster, Helm 3, and access to GHCR images are required.

## Install

Copy `helm/values.yaml` into a private values file and configure database credentials, Grafana credentials, storage class, and ingress. The defaults are intended for local evaluation. For a cluster example, see `helm/values-cluster-overrides.yaml` in the repository.

```bash
helm lint ./helm -f my-values.yaml
helm template opensampl ./helm -f my-values.yaml
helm install opensampl ./helm --namespace opensampl --create-namespace \
  -f my-values.yaml --wait --wait-for-jobs --timeout 15m
```

For published charts, replace `./helm` with `oci://ghcr.io/ornl/charts/opensampl` and pass `--version <chart-version>`. Read the version from `helm/Chart.yaml` for the release being installed.

Migrations run as post-install and post-upgrade hooks. The backend waits for the database port, but callers should wait for the migration hook to finish before loading data. A failed Job is retained for inspection with `kubectl logs job/<release-fullname>-migrations`.

## Configuration

- `db.persistence.enabled` defaults to true. Claim templates use `db.persistence.size` and `db.persistence.storageClass`; false uses ephemeral `emptyDir` storage.
- `backend.useApiKey` enables authentication. Set `API_KEYS` through `backend.env`, preferably using a Kubernetes Secret reference. Clients send one key through the `access-key` header.
- `db.grafanaPassword` is the read-only datasource role password. `grafana.adminPassword` controls the Grafana administrator separately.
- `grafana.rootUrl` optionally sets the external Grafana URL. For `/grafana` ingress paths, also set `grafana.serveFromSubPath: true`.
- Configure ingress through `ingress.enabled`, `ingress.className`, `ingress.hosts`, and optional `ingress.tls`, as demonstrated in the cluster example.

The datasource receives the release-specific database service address automatically.

## Upgrade and storage

Back up PostgreSQL before upgrading. Use `helm upgrade` with the same release name, namespace, and values; migrations rerun on upgrade. Existing StatefulSet and database claim names are preserved.

Changing persistence mode, claim size, or storage class may require a controlled StatefulSet recreation or storage-provider procedure. Do not delete existing claims: stop writers, back up and verify the database, follow your storage provider's migration procedure, then restore and verify data before resuming writers.

Chart 0.2.4 removes an unused standalone PVC; database data remains in StatefulSet-managed claims. Confirm claim usage before upgrading customized installations. Grafana's internal database is PostgreSQL; imported dashboards and datasource configuration should be verified after deployment.
