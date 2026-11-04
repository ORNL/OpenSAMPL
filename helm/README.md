# openSAMPL Helm chart

Deploys openSAMPL (TimescaleDB, backend API, Grafana, and a migrations hook job) on Kubernetes.

Full instructions: [Deploying on Kubernetes with Helm](../docs/guides/kubernetes-helm.md).

## Quick start

```bash
# Find the latest version in Chart.yaml or on the GHCR packages page
helm install opensampl \
  oci://ghcr.io/ornl/charts/opensampl \
  --version <chart-version> \
  --namespace opensampl \
  --create-namespace
```

Preview first with `--dry-run --debug`; override settings with `-f my-values.yaml`
(see `values.yaml` and the cluster example in `values-cluster-overrides.yaml`).

## Layout

```
helm/
├── Chart.yaml
├── values.yaml                    # defaults
├── values-cluster-overrides.yaml  # example overrides for the ORNL cluster
└── templates/
    ├── _helpers.tpl
    ├── NOTES.txt
    ├── ingress.yaml               # optional
    ├── backend/                   # deployment, service
    ├── db/                        # statefulset, service, pvc, secret, configmaps
    ├── grafana/                   # deployment, service
    └── migrations/                # post-install/post-upgrade hook job
```

Charts and images are published to GHCR from `main`; see `docs/maintainers/ci-cd.md`.
